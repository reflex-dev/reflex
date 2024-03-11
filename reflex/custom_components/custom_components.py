"""CLI for creating custom components."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import typer

from reflex import constants
from reflex.config import get_config
from reflex.constants import CustomComponents
from reflex.utils import console

config = get_config()
custom_components_cli = typer.Typer()


@contextmanager
def set_directory(working_directory: str):
    """Context manager that sets the working directory.

    Args:
        working_directory: The working directory to change to.

    Yields:
        Yield to the caller to perform operations in the working directory.
    """
    current_directory = os.getcwd()
    try:
        os.chdir(working_directory)
        yield
    finally:
        os.chdir(current_directory)


def _create_package_config(module_name: str, package_name: str):
    """Create a package config pyproject.toml file.

    Args:
        module_name: The name of the module.
        package_name: The name of the package typically constructed with `reflex-` prefix and a meaningful library name.
    """
    from reflex.compiler import templates

    with open(CustomComponents.PYPROJECT_TOML, "w") as f:
        f.write(
            templates.CUSTOM_COMPONENTS_PYPROJECT_TOML.render(
                module_name=module_name, package_name=package_name
            )
        )


def _create_readme(module_name: str, package_name: str):
    """Create a package README file.

    Args:
        module_name: The name of the module.
        package_name: The name of the python package to be published.
    """
    from reflex.compiler import templates

    with open(CustomComponents.PACKAGE_README, "w") as f:
        f.write(
            templates.CUSTOM_COMPONENTS_README.render(
                module_name=module_name,
                package_name=package_name,
            )
        )


def _write_source_and_init_py(
    custom_component_src_dir: str,
    component_class_name: str,
    module_name: str,
):
    """Write the source code and init file from templates for the custom component.

    Args:
        custom_component_src_dir: The name of the custom component source directory.
        component_class_name: The name of the component class.
        module_name: The name of the module.
    """
    from reflex.compiler import templates

    with open(
        os.path.join(
            custom_component_src_dir,
            f"{module_name}.py",
        ),
        "w",
    ) as f:
        f.write(
            templates.CUSTOM_COMPONENTS_SOURCE.render(
                component_class_name=component_class_name, module_name=module_name
            )
        )

    with open(
        os.path.join(
            custom_component_src_dir,
            CustomComponents.INIT_FILE,
        ),
        "w",
    ) as f:
        f.write(templates.CUSTOM_COMPONENTS_INIT_FILE.render(module_name=module_name))


def _populate_demo_app(name_variants: NameVariants):
    """Populate the demo app that imports the custom components.

    Args:
        name_variants: the tuple including various names such as package name, class name needed for the project.
    """
    from reflex import constants
    from reflex.compiler import templates
    from reflex.reflex import _init

    demo_app_dir = name_variants.demo_app_dir
    demo_app_name = name_variants.demo_app_name

    console.info(f"Creating app for testing: {demo_app_dir}")

    os.makedirs(demo_app_dir)

    with set_directory(demo_app_dir):
        # We start with the blank template as basis.
        _init(name=demo_app_name, template=constants.Templates.Kind.BLANK)
        # Then overwrite the app source file with the one we want for testing custom components.
        # This source file is rendered using jinja template file.
        with open(f"{demo_app_name}/{demo_app_name}.py", "w") as f:
            f.write(
                templates.CUSTOM_COMPONENTS_DEMO_APP.render(
                    custom_component_module_dir=name_variants.custom_component_module_dir,
                    module_name=name_variants.module_name,
                )
            )
        # Append the custom component package to the requirements.txt file.
        with open(f"{constants.RequirementsTxt.FILE}", "a") as f:
            f.write(f"{name_variants.package_name}\n")


def _get_default_library_name_parts() -> list[str]:
    """Get the default library name. Based on the current directory name, remove any non-alphanumeric characters.

    Raises:
        Exit: If the current directory name is not suitable for python projects, and we cannot find a valid library name based off it.

    Returns:
        The parts of default library name.
    """
    current_dir_name = os.getcwd().split(os.path.sep)[-1]

    cleaned_dir_name = re.sub("[^0-9a-zA-Z-_]+", "", current_dir_name).lower()
    parts = [part for part in re.split("-|_", cleaned_dir_name) if part]
    if parts and parts[0] == constants.Reflex.MODULE_NAME:
        # If the directory name already starts with "reflex", remove it from the parts.
        parts = parts[1:]
        # If no parts left, cannot find a valid library name, exit.
        if not parts:
            # The folder likely has a name not suitable for python paths.
            console.error(
                f"Based on current directory name {current_dir_name}, the library name is {constants.Reflex.MODULE_NAME}. This package already exists. Please use --library-name to specify a different name."
            )
            raise typer.Exit(code=1)
    if not parts:
        # The folder likely has a name not suitable for python paths.
        console.error(
            f"Could not find a valid library name based on the current directory: got {current_dir_name}."
        )
        raise typer.Exit(code=1)
    return parts


NameVariants = namedtuple(
    "NameVariants",
    [
        "library_name",
        "component_class_name",
        "package_name",
        "module_name",
        "custom_component_module_dir",
        "demo_app_dir",
        "demo_app_name",
    ],
)


def _validate_library_name(library_name: str | None) -> NameVariants:
    """Validate the library name.

    Args:
        library_name: The name of the library if picked otherwise None.

    Raises:
        Exit: If the library name is not suitable for python projects.

    Returns:
        A tuple containing the various names such as package name, class name, etc., needed for the project.
    """
    if library_name is not None and not re.match(
        r"^[a-zA-Z-]+[a-zA-Z0-9-]*$", library_name
    ):
        console.error(
            f"Please use only alphanumeric characters or dashes: got {library_name}"
        )
        raise typer.Exit(code=1)

    # If not specified, use the current directory name to form the module name.
    name_parts = (
        [part.lower() for part in library_name.split("-")]
        if library_name
        else _get_default_library_name_parts()
    )
    if not library_name:
        library_name = "-".join(name_parts)

    # Component class name is the camel case.
    component_class_name = "".join([part.capitalize() for part in name_parts])
    console.debug(f"Component class name: {component_class_name}")

    # Package name is commonly kebab case.
    package_name = f"reflex-{library_name}"
    console.debug(f"Package name: {package_name}")

    # Module name is the snake case.
    module_name = "_".join(name_parts)

    custom_component_module_dir = f"reflex_{module_name}"
    console.debug(f"Custom component source directory: {custom_component_module_dir}")

    # Use the same name for the directory and the app.
    demo_app_dir = demo_app_name = f"{module_name}_demo"
    console.debug(f"Demo app directory: {demo_app_dir}")

    return NameVariants(
        library_name=library_name,
        component_class_name=component_class_name,
        package_name=package_name,
        module_name=module_name,
        custom_component_module_dir=custom_component_module_dir,
        demo_app_dir=demo_app_dir,
        demo_app_name=demo_app_name,
    )


def _populate_custom_component_project(name_variants: NameVariants):
    """Populate the custom component source directory. This includes the pyproject.toml, README.md, and the code template for the custom component.

    Args:
        name_variants: the tuple including various names such as package name, class name needed for the project.
    """
    console.info(
        f"Populating pyproject.toml with package name: {name_variants.package_name}"
    )
    # write pyproject.toml, README.md, etc.
    _create_package_config(
        module_name=name_variants.library_name, package_name=name_variants.package_name
    )
    _create_readme(
        module_name=name_variants.library_name, package_name=name_variants.package_name
    )

    console.info(
        f"Initializing the component directory: {CustomComponents.SRC_DIR}/{name_variants.custom_component_module_dir}"
    )
    os.makedirs(CustomComponents.SRC_DIR)
    with set_directory(CustomComponents.SRC_DIR):
        os.makedirs(name_variants.custom_component_module_dir)
        _write_source_and_init_py(
            custom_component_src_dir=name_variants.custom_component_module_dir,
            component_class_name=name_variants.component_class_name,
            module_name=name_variants.module_name,
        )


@custom_components_cli.command(name="init")
def init(
    library_name: Optional[str] = typer.Option(
        None,
        help="The name of your library. On PyPI, package will be published as `reflex-{library-name}`.",
    ),
    install: bool = typer.Option(
        True,
        help="Whether to install package from this local custom component in editable mode.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Initialize a custom component.

    Args:
        library_name: The name of the library.
        install: Whether to install package from this local custom component in editable mode.
        loglevel: The log level to use.

    Raises:
        Exit: If the pyproject.toml already exists.
    """
    from reflex.utils import exec, prerequisites

    console.set_log_level(loglevel)

    if os.path.exists(CustomComponents.PYPROJECT_TOML):
        console.error(f"A {CustomComponents.PYPROJECT_TOML} already exists. Aborting.")
        typer.Exit(code=1)

    # Show system info.
    exec.output_system_info()

    # Check the name follows the convention if picked.
    name_variants = _validate_library_name(library_name)

    console.rule(f"[bold]Initializing {name_variants.package_name} project")

    _populate_custom_component_project(name_variants)

    _populate_demo_app(name_variants)

    # Initialize the .gitignore.
    prerequisites.initialize_gitignore(
        gitignore_file=CustomComponents.FILE, files_to_ignore=CustomComponents.DEFAULTS
    )

    if install:
        package_name = name_variants.package_name
        console.rule(f"[bold]Installing {package_name} in editable mode.")
        if _pip_install_on_demand(package_name=".", install_args=["-e"]):
            console.info(f"Package {package_name} installed!")
        else:
            raise typer.Exit(code=1)

    console.print("[bold]Custom component initialized successfully!")
    console.rule("[bold]Project Summary")
    console.print(
        f"[ {CustomComponents.PACKAGE_README} ]: Package description. Please add usage examples."
    )
    console.print(
        f"[ {CustomComponents.PYPROJECT_TOML} ]: Project configuration file. Please fill in details such as your name, email, homepage URL."
    )
    console.print(
        f"[ {CustomComponents.SRC_DIR}/ ]: Custom component code template. Start by editing it with your component implementation."
    )
    console.print(
        f"[ {name_variants.demo_app_dir}/ ]: Demo App. Add more code to this app and test."
    )


def _pip_install_on_demand(
    package_name: str,
    install_args: list[str] | None = None,
) -> bool:
    """Install a package on demand.

    Args:
        package_name: The name of the package.
        install_args: The additional arguments for the pip install command.

    Returns:
        True if the package is installed successfully, False otherwise.
    """
    install_args = install_args or []

    install_cmds = [
        sys.executable,
        "-m",
        "pip",
        "install",
        *install_args,
        package_name,
    ]
    console.debug(f"Install package: {' '.join(install_cmds)}")
    return _run_commands_in_subprocess(install_cmds)


def _run_commands_in_subprocess(cmds: list[str]) -> bool:
    """Run commands in a subprocess.

    Args:
        cmds: The commands to run.

    Returns:
        True if the command runs successfully, False otherwise.
    """
    console.debug(f"Running command: {' '.join(cmds)}")
    try:
        result = subprocess.run(cmds, capture_output=True, text=True, check=True)
        console.debug(result.stdout)
        return True
    except subprocess.CalledProcessError as cpe:
        console.error(cpe.stdout)
        console.error(cpe.stderr)
        return False


def _run_build():
    """Run the build command.

    Raises:
        Exit: If the build fails.
    """
    console.print("Building custom component...")

    cmds = [sys.executable, "-m", "build", "."]
    if _run_commands_in_subprocess(cmds):
        console.info("Custom component built successfully!")
    else:
        raise typer.Exit(code=1)


@custom_components_cli.command(name="build")
def build(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Build a custom component. Must be run from the project root directory where the pyproject.toml is.

    Args:
        loglevel: The log level to use.
    """
    console.set_log_level(loglevel)
    _run_build()


def _validate_repository_name(repository: str | None) -> str:
    """Validate the repository name.

    Args:
        repository: The name of the repository.

    Returns:
        The name of the repository.

    Raises:
        Exit: If the repository name is not supported.
    """
    if repository is None:
        return "pypi"
    elif repository not in CustomComponents.REPO_URLS:
        console.error(
            f"Unsupported repository name. Allow {CustomComponents.REPO_URLS.keys()}, got {repository}"
        )
        raise typer.Exit(code=1)
    return repository


def _validate_credentials(
    username: str | None, password: str | None, token: str | None
) -> tuple[str, str]:
    """Validate the credentials.

    Args:
        username: The username to use for authentication on python package repository.
        password: The password to use for authentication on python package repository.
        token: The token to use for authentication on python package repository.

    Raises:
        Exit: If the appropriate combination of credentials is not provided.

    Returns:
        The username and password.
    """
    if token is not None:
        if username is not None or password is not None:
            console.error("Cannot use token and username/password at the same time.")
            raise typer.Exit(code=1)
        username = "__token__"
        password = token
    elif username is None or password is None:
        console.error(
            "Must provide both username and password for authentication if not using a token."
        )
        raise typer.Exit(code=1)

    return username, password


def _get_version_to_publish() -> str:
    """Get the version to publish from the pyproject.toml.

    Raises:
        Exit: If the version is not found in the pyproject.toml.

    Returns:
        The version to publish.
    """
    # Get the version from the pyproject.toml.
    version_to_publish = None
    with open(CustomComponents.PYPROJECT_TOML, "r") as f:
        pyproject_toml = f.read()
        # Note below does not capture non-matching quotes. Not performing full syntax check here.
        match = re.search(r'version\s*=\s*["\'](.*?)["\']', pyproject_toml)
        if match:
            version_to_publish = match.group(1)
            console.debug(f"Version to be published: {version_to_publish}")
    if not version_to_publish:
        console.error(
            f"Could not find the version to be published in {CustomComponents.PYPROJECT_TOML}"
        )
        raise typer.Exit(code=1)

    return version_to_publish


def _ensure_dist_dir(version_to_publish: str, build: bool):
    """Ensure the distribution directory and the expected files exist.

    Args:
        version_to_publish: The version to be published.
        build: Whether to build the package first.

    Raises:
        Exit: If the distribution directory does not exist, or the expected files are not found.
    """
    dist_dir = Path(CustomComponents.DIST_DIR)

    if build:
        # Need to check if the files here are for the version to be published.
        if dist_dir.exists():

            # Check if the distribution files are for the version to be published.
            needs_rebuild = False
            for suffix in CustomComponents.DISTRIBUTION_FILE_SUFFIXES:
                if not list(dist_dir.glob(f"*{version_to_publish}*{suffix}")):
                    console.debug(
                        f"Expected distribution file with suffix {suffix} for version {version_to_publish} not found in directory {dist_dir.name}"
                    )
                    needs_rebuild = True
                    break
        else:
            needs_rebuild = True

        if not needs_rebuild:
            needs_rebuild = (
                console.ask(
                    "Distribution files for the version to be published already exist. Do you want to rebuild?",
                    choices=["n", "y"],
                    default="n",
                )
                == "y"
            )
        if needs_rebuild:
            _run_build()

    # Check if the distribution directory exists.
    if not dist_dir.exists():
        console.error(f"Directory {dist_dir.name} does not exist. Please build first.")
        raise typer.Exit(code=1)

    # Check if the distribution directory is indeed a directory.
    if not dist_dir.is_dir():
        console.error(
            f"{dist_dir.name} is not a directory. If this is a file you added, move it and rebuild."
        )
        raise typer.Exit(code=1)

    # Check if the distribution files exist.
    for suffix in CustomComponents.DISTRIBUTION_FILE_SUFFIXES:
        if not list(dist_dir.glob(f"*{suffix}")):
            console.error(
                f"Expected distribution file with suffix {suffix} in directory {dist_dir.name}"
            )
            raise typer.Exit(code=1)


@custom_components_cli.command(name="publish")
def publish(
    repository: Optional[str] = typer.Option(
        None,
        "-r",
        "--repository",
        help="The name of the repository. Defaults to pypi. Only supports pypi and testpypi (Test PyPI) for now.",
    ),
    token: Optional[str] = typer.Option(
        None,
        "-t",
        "--token",
        help="The API token to use for authentication on python package repository. If token is provided, no username/password should be provided at the same time",
    ),
    username: Optional[str] = typer.Option(
        None,
        "-u",
        "--username",
        help="The username to use for authentication on python package repository. Username and password must both be provided.",
    ),
    password: Optional[str] = typer.Option(
        None,
        "-p",
        "--password",
        help="The password to use for authentication on python package repository. Username and password must both be provided.",
    ),
    build: bool = typer.Option(
        True,
        help="Whether to build the package before publishing. If the package is already built, set this to False.",
    ),
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Publish a custom component. Must be run from the project root directory where the pyproject.toml is.

    Args:
        repository: The name of the Python package repository, such pypi, testpypi.
        token: The token to use for authentication on python package repository. If token is provided, no username/password should be provided at the same time.
        username: The username to use for authentication on python package repository.
        password: The password to use for authentication on python package repository.
        build: Whether to build the distribution files. Defaults to True.
        loglevel: The log level to use.

    Raises:
        Exit: If arguments provided are not correct or the publish fails.
    """
    console.set_log_level(loglevel)

    # Validate the repository name.
    repository = _validate_repository_name(repository)
    console.print(f"Publishing custom component to {repository}...")

    # Validate the credentials.
    username, password = _validate_credentials(username, password, token)

    # Get the version to publish from the pyproject.toml.
    version_to_publish = _get_version_to_publish()

    # Validate the distribution directory.
    _ensure_dist_dir(version_to_publish=version_to_publish, build=build)

    # We install twine on the fly if required so it is not a stable dependency of reflex.
    try:
        import twine  # noqa: F401  # type: ignore
    except (ImportError, ModuleNotFoundError) as ex:
        if not _pip_install_on_demand("twine"):
            raise typer.Exit(code=1) from ex
    publish_cmds = [
        sys.executable,
        "-m",
        "twine",
        "upload",
        "--repository-url",
        CustomComponents.REPO_URLS[repository],
        "--username",
        username,
        "--password",
        password,
        "--non-interactive",
        f"{CustomComponents.DIST_DIR}/*{version_to_publish}*",
    ]
    if _run_commands_in_subprocess(publish_cmds):
        console.info("Custom component published successfully!")
    else:
        raise typer.Exit(1)
