"""CLI for creating custom components."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from contextlib import contextmanager
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
        package_name: The name of the package.
    """
    from reflex.compiler import templates

    with open(CustomComponents.PYPROJECT_TOML, "w") as f:
        f.write(
            templates.CUSTOM_COMPONENTS_PYPROJECT_TOML.render(
                module_name=module_name, package_name=package_name
            )
        )


def _create_readme(module_name: str):
    """Create a package README file.

    Args:
        module_name: The name of the module.
    """
    from reflex.compiler import templates

    with open(CustomComponents.PACKAGE_README, "w") as f:
        f.write(templates.CUSTOM_COMPONENTS_README.render(module_name=module_name))


def _write_source_py(
    custom_component_src_dir: str,
    component_class_name: str,
    module_name: str,
):
    """Write the source code template for the custom component.

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


def _populate_demo_app(
    demo_app_dir: str, app_name: str, custom_component_src_dir: str, module_name: str
):
    """Populate the demo app that imports the custom components.

    Args:
        demo_app_dir: The name of the demo app directory.
        app_name: The name of the demo app.
        custom_component_src_dir: The name of the custom component source directory.
        module_name: The name of the module.
    """
    from reflex import constants
    from reflex.compiler import templates
    from reflex.reflex import _init

    with set_directory(demo_app_dir):
        # We do not want a template in this demo
        # TODO: might be nice to add imports to the demo app
        _init(name=app_name, template=constants.Templates.Kind.BLANK)
        # TODO: below is a hack to overwrite the app source file with the one we want for testing custom components
        with open(f"{app_name}/{app_name}.py", "w") as f:
            f.write(
                templates.CUSTOM_COMPONENTS_DEMO_APP.render(
                    custom_component_src_dir=custom_component_src_dir,
                    module_name=module_name,
                )
            )


def _get_default_library_name_parts() -> list[str]:
    """Get the default library name. Based on the current directory name, remove any non-alphanumeric characters.

    Raises:
        ValueError: If the current directory name is suitable for python, and we cannot find a valid library name based off it.

    Returns:
        The parts of default library name.
    """
    current_dir_name = os.getcwd().split(os.path.sep)[-1]

    cleaned_dir_name = re.sub("[^0-9a-zA-Z-_]+", "", current_dir_name)
    parts = re.split("-|_", cleaned_dir_name)
    if not parts:
        # Likely a folder not suitable for python files in general either
        raise ValueError(
            f"Could not find a valid library name based on the current directory: got {current_dir_name}."
        )
    return parts


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

    # TODO: define pyproject.toml as constants
    if os.path.exists(CustomComponents.PYPROJECT_TOML):
        console.error(f"A {CustomComponents.PYPROJECT_TOML} already exists. Aborting.")
        typer.Exit(code=1)

    # Show system info
    exec.output_system_info()

    # TODO: check the picked name follows the convention
    if library_name is not None and not re.match(
        r"^[a-zA-Z-]+[a-zA-Z0-9-]*$", library_name
    ):
        console.error(
            f"Please use only alphanumeric characters or dashes: got {library_name}"
        )
        raise typer.Exit(code=1)

    # if not specified, use the current directory name to form the module name
    name_parts = (
        [part.lower() for part in library_name.split("-")]
        if library_name
        else _get_default_library_name_parts()
    )
    if not library_name:
        library_name = "-".join(name_parts)

    component_class_name = "".join([part.capitalize() for part in name_parts])
    console.info(f"Component class name: {component_class_name}")
    package_name = f"reflex-{library_name}"
    console.info(f"Package name: {package_name}")
    module_name = "_".join(name_parts)
    custom_component_src_dir = f"rx_{module_name}"
    console.info(f"Custom component source directory: {custom_component_src_dir}")
    # Use the same name for the directory and the app
    demo_app_dir = demo_app_name = f"{module_name}_demo"
    console.info(f"Demo app directory: {demo_app_dir}")

    console.info(f"Populating pyproject.toml with package name: {package_name}")
    # write pyproject.toml, README.md, etc.
    _create_package_config(module_name=library_name, package_name=package_name)
    _create_readme(module_name=library_name)

    console.info(
        f"Initializing the component source directory: {CustomComponents.SRC_DIR}/{custom_component_src_dir}"
    )
    os.makedirs(CustomComponents.SRC_DIR)
    with set_directory(CustomComponents.SRC_DIR):
        os.makedirs(custom_component_src_dir)
        _write_source_py(
            custom_component_src_dir=custom_component_src_dir,
            component_class_name=component_class_name,
            module_name=module_name,
        )

    console.info(f"Creating app for testing: {demo_app_dir}")
    os.makedirs(demo_app_dir)
    _populate_demo_app(
        demo_app_dir=demo_app_dir,
        app_name=demo_app_name,
        custom_component_src_dir=custom_component_src_dir,
        module_name=module_name,
    )

    # Initialize the .gitignore.
    prerequisites.initialize_gitignore()

    if install:
        console.info(f"Installing {package_name} in editable mode.")

        cmds = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-e",
            ".",
        ]
        console.info(f"Install package in editable mode: {' '.join(cmds)}")
        try:
            result = subprocess.run(cmds, capture_output=True, text=True, check=True)
            console.debug(result.stdout)
            console.info(f"Package {package_name} installed!")
        except subprocess.CalledProcessError as cpe:
            console.error(cpe.stderr)
            raise typer.Exit(code=cpe.returncode) from cpe


def _pip_install_on_demand(package_name: str) -> bool:
    install_cmds = [
        sys.executable,
        "-m",
        "pip",
        "install",
        package_name,
    ]
    try:
        result = subprocess.run(
            install_cmds, capture_output=True, text=True, check=True
        )
        console.debug(result.stdout)
        return True
    except subprocess.CalledProcessError as cpe:
        console.error(cpe.stderr)
        return False


@custom_components_cli.command(name="build")
def build(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Build a custom component.

    Args:
        loglevel: The log level to use.

    Raises:
        Exit: If the build fails.
    """
    console.set_log_level(loglevel)
    console.print("Building custom component...")
    try:
        pass  # type: ignore
    except (ImportError, ModuleNotFoundError) as ex:
        if not _pip_install_on_demand("build"):
            raise typer.Exit(code=1) from ex

    cmds = [sys.executable, "-m", "build", "."]
    console.debug(f"Running command: {' '.join(cmds)}")
    try:
        # TODO: below subprocess is not printing errors/debug
        result = subprocess.run(cmds, capture_output=True, text=True, check=True)
        console.debug(result.stdout)
        console.info("Custom component built successfully!")
    except subprocess.CalledProcessError as cpe:
        console.error(cpe.stderr)
        raise typer.Exit(code=cpe.returncode) from cpe


@custom_components_cli.command(name="test")
def test(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Test a custom component.

    Args:
        loglevel: The log level to use.
    """
    console.set_log_level(loglevel)
    console.print("Testing custom component... Not yet implemented")
    # TODO: figure out a way to get the demo app folder properly
    # maybe we need more fields in the config?
    # with set_directory(the_right_folder):
    #     reflex.run()


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
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Publish a custom component.

    Args:
        repository: The name of the Python package repository, such pypi, testpypi.
        token: The token to use for authentication on python package repository. If token is provided, no username/password should be provided at the same time.
        username: The username to use for authentication on python package repository.
        password: The password to use for authentication on python package repository.
        loglevel: The log level to use.

    Raises:
        Exit: If arguments provided are not correct or the publish fails.
    """
    console.set_log_level(loglevel)
    if repository is None:
        repository = "pypi"
    elif repository not in CustomComponents.REPO_URLS:
        console.error(
            f"Unsupported repository name. Allow {CustomComponents.REPO_URLS.keys()}, got {repository}"
        )
        raise typer.Exit(code=1)

    console.print(f"Publishing custom component to {repository}...")
    if token is not None and (username is not None or password is not None):
        console.error("Cannot use token and username/password at the same time.")
        raise typer.Exit(code=1)
    elif token is None and (username is None or password is None):
        console.error(
            "Must provide both username and password for authentication if not using a token."
        )
        raise typer.Exit(code=1)

    if token is not None:
        username = "__token__"
        password = token

    if not os.path.exists(CustomComponents.DIST_DIR):
        console.error(
            f"{CustomComponents.DIST_DIR} does not exist. Please build it first: `reflex custom-components build`"
        )
        raise typer.Exit(code=1)

    # TODO: dist needs to be a directory with certain file types expected
    # combine this with above into a helper _ensure_dist_dir().

    # We install twine with pip on the fly so it is not a stable dependency of reflex
    try:
        pass  # type: ignore
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
        f"{CustomComponents.DIST_DIR}/*",
    ]
    console.debug(f"Running command: {' '.join(publish_cmds)}")
    try:
        # TODO: below subprocess is not printing errors/debug
        result = subprocess.run(
            publish_cmds, capture_output=True, text=True, check=True
        )
        console.debug(result.stdout)
        console.info("Custom component published successfully!")
    except subprocess.CalledProcessError as cpe:
        console.error(cpe.stderr)
        raise typer.Exit(code=cpe.returncode) from cpe
