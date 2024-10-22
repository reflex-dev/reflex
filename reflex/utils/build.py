"""Building the app and initializing all prerequisites."""

from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path

from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn

from reflex import constants
from reflex.config import get_config
from reflex.utils import console, path_ops, prerequisites, processes


def set_env_json():
    """Write the upload url to a REFLEX_JSON."""
    path_ops.update_json_file(
        str(prerequisites.get_web_dir() / constants.Dirs.ENV_JSON),
        {endpoint.name: endpoint.get_url() for endpoint in constants.Endpoint},
    )


def generate_sitemap_config(deploy_url: str, export=False):
    """Generate the sitemap config file.

    Args:
        deploy_url: The URL of the deployed app.
        export: If the sitemap are generated for an export.
    """
    # Import here to avoid circular imports.
    from reflex.compiler import templates

    config = {
        "siteUrl": deploy_url,
        "generateRobotsTxt": True,
    }

    if export:
        config["outDir"] = constants.Dirs.STATIC

    config = json.dumps(config)

    sitemap = prerequisites.get_web_dir() / constants.Next.SITEMAP_CONFIG_FILE
    sitemap.write_text(templates.SITEMAP_CONFIG(config=config))


def _zip(
    component_name: constants.ComponentName,
    target: str | Path,
    root_dir: str | Path,
    exclude_venv_dirs: bool,
    upload_db_file: bool = False,
    dirs_to_exclude: set[str] | None = None,
    files_to_exclude: set[str] | None = None,
    top_level_dirs_to_exclude: set[str] | None = None,
) -> None:
    """Zip utility function.

    Args:
        component_name: The name of the component: backend or frontend.
        target: The target zip file.
        root_dir: The root directory to zip.
        exclude_venv_dirs: Whether to exclude venv directories.
        upload_db_file: Whether to include local sqlite db files.
        dirs_to_exclude: The directories to exclude.
        files_to_exclude: The files to exclude.
        top_level_dirs_to_exclude: The top level directory names immediately under root_dir to exclude. Do not exclude folders by these names further in the sub-directories.

    """
    target = Path(target)
    root_dir = Path(root_dir)
    dirs_to_exclude = dirs_to_exclude or set()
    files_to_exclude = files_to_exclude or set()
    files_to_zip: list[str] = []
    # Traverse the root directory in a top-down manner. In this traversal order,
    # we can modify the dirs list in-place to remove directories we don't want to include.
    for root, dirs, files in os.walk(root_dir, topdown=True):
        root = Path(root)
        # Modify the dirs in-place so excluded and hidden directories are skipped in next traversal.
        dirs[:] = [
            d
            for d in dirs
            if (basename := Path(d).resolve().name) not in dirs_to_exclude
            and not basename.startswith(".")
            and (not exclude_venv_dirs or not _looks_like_venv_dir(root / d))
        ]
        # If we are at the top level with root_dir, exclude the top level dirs.
        if top_level_dirs_to_exclude and root == root_dir:
            dirs[:] = [d for d in dirs if d not in top_level_dirs_to_exclude]
        # Modify the files in-place so the hidden files and db files are excluded.
        files[:] = [
            f
            for f in files
            if not f.startswith(".") and (upload_db_file or not f.endswith(".db"))
        ]
        files_to_zip += [
            str(root / file) for file in files if file not in files_to_exclude
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
            zipf.write(file, Path(file).relative_to(root_dir))


def zip_app(
    frontend: bool = True,
    backend: bool = True,
    zip_dest_dir: str | Path = Path.cwd(),
    upload_db_file: bool = False,
):
    """Zip up the app.

    Args:
        frontend: Whether to zip up the frontend app.
        backend: Whether to zip up the backend app.
        zip_dest_dir: The directory to export the zip file to.
        upload_db_file: Whether to upload the database file.
    """
    zip_dest_dir = Path(zip_dest_dir)
    files_to_exclude = {
        constants.ComponentName.FRONTEND.zip(),
        constants.ComponentName.BACKEND.zip(),
    }

    if frontend:
        _zip(
            component_name=constants.ComponentName.FRONTEND,
            target=zip_dest_dir / constants.ComponentName.FRONTEND.zip(),
            root_dir=prerequisites.get_web_dir() / constants.Dirs.STATIC,
            files_to_exclude=files_to_exclude,
            exclude_venv_dirs=False,
        )

    if backend:
        _zip(
            component_name=constants.ComponentName.BACKEND,
            target=zip_dest_dir / constants.ComponentName.BACKEND.zip(),
            root_dir=Path("."),
            dirs_to_exclude={"__pycache__"},
            files_to_exclude=files_to_exclude,
            top_level_dirs_to_exclude={"assets"},
            exclude_venv_dirs=True,
            upload_db_file=upload_db_file,
        )


def build(
    deploy_url: str | None = None,
    for_export: bool = False,
):
    """Build the app for deployment.

    Args:
        deploy_url: The deployment URL.
        for_export: Whether the build is for export.
    """
    wdir = prerequisites.get_web_dir()

    # Clean the static directory if it exists.
    path_ops.rm(str(wdir / constants.Dirs.STATIC))

    # The export command to run.
    command = "export"

    checkpoints = [
        "Linting and checking ",
        "Creating an optimized production build",
        "Route (pages)",
        "prerendered as static HTML",
        "Collecting page data",
        "Finalizing page optimization",
        "Collecting build traces",
    ]

    # Generate a sitemap if a deploy URL is provided.
    if deploy_url is not None:
        generate_sitemap_config(deploy_url, export=for_export)
        command = "export-sitemap"

        checkpoints.extend(["Loading next-sitemap", "Generation completed"])

    # Start the subprocess with the progress bar.
    process = processes.new_process(
        [prerequisites.get_package_manager(), "run", command],
        cwd=wdir,
        shell=constants.IS_WINDOWS,
    )
    processes.show_progress("Creating Production Build", process, checkpoints)


def setup_frontend(
    root: Path,
    disable_telemetry: bool = True,
):
    """Set up the frontend to run the app.

    Args:
        root: The root path of the project.
        disable_telemetry: Whether to disable the Next telemetry.
    """
    # Create the assets dir if it doesn't exist.
    path_ops.mkdir(constants.Dirs.APP_ASSETS)

    # Copy asset files to public folder.
    path_ops.cp(
        src=str(root / constants.Dirs.APP_ASSETS),
        dest=str(root / prerequisites.get_web_dir() / constants.Dirs.PUBLIC),
    )

    # Set the environment variables in client (env.json).
    set_env_json()

    # update the last reflex run time.
    prerequisites.set_last_reflex_run_time()

    # Disable the Next telemetry.
    if disable_telemetry:
        processes.new_process(
            [
                prerequisites.get_package_manager(),
                "run",
                "next",
                "telemetry",
                "disable",
            ],
            cwd=prerequisites.get_web_dir(),
            stdout=subprocess.DEVNULL,
            shell=constants.IS_WINDOWS,
        )


def setup_frontend_prod(
    root: Path,
    disable_telemetry: bool = True,
):
    """Set up the frontend for prod mode.

    Args:
        root: The root path of the project.
        disable_telemetry: Whether to disable the Next telemetry.
    """
    setup_frontend(root, disable_telemetry)
    build(deploy_url=get_config().deploy_url)


def _looks_like_venv_dir(dir_to_check: str | Path) -> bool:
    dir_to_check = Path(dir_to_check)
    return (dir_to_check / "pyvenv.cfg").exists()
