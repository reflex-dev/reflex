"""Building the app and initializing all prerequisites."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path, PosixPath

from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn

from reflex import constants
from reflex.config import get_config
from reflex.utils import console, js_runtimes, path_ops, prerequisites, processes
from reflex.utils.exec import is_in_app_harness


def set_env_json():
    """Write the upload url to a REFLEX_JSON."""
    path_ops.update_json_file(
        str(prerequisites.get_web_dir() / constants.Dirs.ENV_JSON),
        {
            **{endpoint.name: endpoint.get_url() for endpoint in constants.Endpoint},
            "TRANSPORT": get_config().transport,
            "TEST_MODE": is_in_app_harness(),
        },
    )


def _zip(
    *,
    component_name: constants.ComponentName,
    target: Path,
    root_directory: Path,
    exclude_venv_directories: bool,
    include_db_file: bool = False,
    directory_names_to_exclude: set[str] | None = None,
    files_to_exclude: set[Path] | None = None,
    globs_to_include: list[str] | None = None,
) -> None:
    """Zip utility function.

    Args:
        component_name: The name of the component: backend or frontend.
        target: The target zip file.
        root_directory: The root directory to zip.
        exclude_venv_directories: Whether to exclude venv directories.
        include_db_file: Whether to include local sqlite db files.
        directory_names_to_exclude: The directory names to exclude.
        files_to_exclude: The files to exclude.
        globs_to_include: Apply these globs from the root_directory and always include them in the zip.

    """
    target = Path(target)
    root_directory = Path(root_directory).resolve()
    directory_names_to_exclude = directory_names_to_exclude or set()
    files_to_exclude = files_to_exclude or set()
    files_to_zip: list[Path] = []
    # Traverse the root directory in a top-down manner. In this traversal order,
    # we can modify the dirs list in-place to remove directories we don't want to include.
    for directory_path, subdirectories_names, subfiles_names in os.walk(
        root_directory, topdown=True, followlinks=True
    ):
        directory_path = Path(directory_path).resolve()
        # Modify the dirs in-place so excluded and hidden directories are skipped in next traversal.
        subdirectories_names[:] = [
            subdirectory_name
            for subdirectory_name in subdirectories_names
            if subdirectory_name not in directory_names_to_exclude
            and not any(
                (directory_path / subdirectory_name).samefile(exclude)
                for exclude in files_to_exclude
                if exclude.exists()
            )
            and not subdirectory_name.startswith(".")
            and (
                not exclude_venv_directories
                or not _looks_like_venv_directory(directory_path / subdirectory_name)
            )
        ]
        # Modify the files in-place so the hidden files and db files are excluded.
        subfiles_names[:] = [
            subfile_name
            for subfile_name in subfiles_names
            if not subfile_name.startswith(".")
            and (include_db_file or not subfile_name.endswith(".db"))
        ]
        files_to_zip += [
            directory_path / subfile_name
            for subfile_name in subfiles_names
            if not any(
                (directory_path / subfile_name).samefile(excluded_file)
                for excluded_file in files_to_exclude
                if excluded_file.exists()
            )
        ]
    if globs_to_include:
        for glob in globs_to_include:
            files_to_zip += [
                file
                for file in root_directory.glob(glob)
                if file.name not in files_to_exclude
            ]
    # Create a progress bar for zipping the component.
    progress = Progress(
        *Progress.get_default_columns()[:-1],
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )
    task = progress.add_task(
        f"Zipping {component_name.value}:", total=len(files_to_zip)
    )

    with progress, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in files_to_zip:
            console.debug(f"{target}: {file}", progress=progress)
            progress.advance(task)
            zipf.write(file, Path(file).relative_to(root_directory))


def zip_app(
    frontend: bool = True,
    backend: bool = True,
    zip_dest_dir: str | Path | None = None,
    include_db_file: bool = False,
    backend_excluded_dirs: tuple[Path, ...] = (),
):
    """Zip up the app.

    Args:
        frontend: Whether to zip up the frontend app.
        backend: Whether to zip up the backend app.
        zip_dest_dir: The directory to export the zip file to.
        include_db_file: Whether to include the database file.
        backend_excluded_dirs: A tuple of files or directories to exclude from the backend zip.  Defaults to ().
    """
    zip_dest_dir = zip_dest_dir or Path.cwd()
    zip_dest_dir = Path(zip_dest_dir)
    files_to_exclude = {
        Path(constants.ComponentName.FRONTEND.zip()).resolve(),
        Path(constants.ComponentName.BACKEND.zip()).resolve(),
    }

    if frontend:
        _zip(
            component_name=constants.ComponentName.FRONTEND,
            target=zip_dest_dir / constants.ComponentName.FRONTEND.zip(),
            root_directory=prerequisites.get_web_dir() / constants.Dirs.STATIC,
            files_to_exclude=files_to_exclude,
            exclude_venv_directories=False,
        )

    if backend:
        _zip(
            component_name=constants.ComponentName.BACKEND,
            target=zip_dest_dir / constants.ComponentName.BACKEND.zip(),
            root_directory=Path.cwd(),
            directory_names_to_exclude={"__pycache__"},
            files_to_exclude=files_to_exclude | set(backend_excluded_dirs),
            exclude_venv_directories=True,
            include_db_file=include_db_file,
            globs_to_include=[
                str(Path(constants.Dirs.WEB) / constants.Dirs.BACKEND / "*")
            ],
        )


def _duplicate_index_html_to_parent_directory(directory: Path):
    """Duplicate index.html in the child directories to the given directory.

    This makes accessing /route and /route/ work in production.

    Args:
        directory: The directory to duplicate index.html to.
    """
    for child in directory.iterdir():
        if child.is_dir():
            # If the child directory has an index.html, copy it to the parent directory.
            index_html = child / "index.html"
            if index_html.exists():
                target = directory / (child.name + ".html")
                if not target.exists():
                    console.debug(f"Copying {index_html} to {target}")
                    path_ops.cp(index_html, target)
                else:
                    console.debug(f"Skipping {index_html}, already exists at {target}")
            # Recursively call this function for the child directory.
            _duplicate_index_html_to_parent_directory(child)


def build():
    """Build the app for deployment.

    Raises:
        SystemExit: If the build process fails.
    """
    wdir = prerequisites.get_web_dir()

    # Clean the static directory if it exists.
    path_ops.rm(str(wdir / constants.Dirs.BUILD_DIR))

    checkpoints = [
        "building for production",
        "building SSR bundle for production",
        "built in",
    ]

    # Start the subprocess with the progress bar.
    process = processes.new_process(
        [
            *js_runtimes.get_js_package_executor(raise_on_none=True)[0],
            "run",
            "export",
        ],
        cwd=wdir,
        shell=constants.IS_WINDOWS,
        env={
            **os.environ,
            "NO_COLOR": "1",
        },
    )
    processes.show_progress("Creating Production Build", process, checkpoints)
    process.wait()
    if process.returncode != 0:
        console.error(
            "Failed to build the frontend. Please run with --loglevel debug for more information.",
        )
        raise SystemExit(1)
    _duplicate_index_html_to_parent_directory(wdir / constants.Dirs.STATIC)

    spa_fallback = wdir / constants.Dirs.STATIC / constants.ReactRouter.SPA_FALLBACK
    if not spa_fallback.exists():
        spa_fallback = wdir / constants.Dirs.STATIC / "index.html"

    if spa_fallback.exists():
        path_ops.cp(
            spa_fallback,
            wdir / constants.Dirs.STATIC / "404.html",
        )

    config = get_config()

    if frontend_path := config.frontend_path.strip("/"):
        frontend_path = PosixPath(frontend_path)
        first_part = frontend_path.parts[0]
        for child in list((wdir / constants.Dirs.STATIC).iterdir()):
            if child.is_dir() and child.name == first_part:
                continue
            path_ops.mv(
                child,
                wdir / constants.Dirs.STATIC / frontend_path / child.name,
            )


def setup_frontend(
    root: Path,
):
    """Set up the frontend to run the app.

    Args:
        root: The root path of the project.
    """
    # Set the environment variables in client (env.json).
    set_env_json()

    # update the last reflex run time.
    prerequisites.set_last_reflex_run_time()


def setup_frontend_prod(
    root: Path,
):
    """Set up the frontend for prod mode.

    Args:
        root: The root path of the project.
    """
    setup_frontend(root)
    build()


def _looks_like_venv_directory(directory_to_check: str | Path) -> bool:
    directory_to_check = Path(directory_to_check)
    return (directory_to_check / "pyvenv.cfg").exists()
