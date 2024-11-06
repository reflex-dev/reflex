"""CLI for creating custom components."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Tuple

import httpx
import tomlkit
import typer
from tomlkit.exceptions import TOMLKitError

from reflex import constants
from reflex.config import environment, get_config
from reflex.constants import CustomComponents
from reflex.utils import console

config = get_config()
custom_components_cli = typer.Typer()

POST_CUSTOM_COMPONENTS_GALLERY_ENDPOINT = (
    f"{config.cp_backend_url}/custom-components/gallery"
)

GET_CUSTOM_COMPONENTS_GALLERY_BY_NAME_ENDPOINT = (
    f"{config.cp_backend_url}/custom-components/gallery"
)

POST_CUSTOM_COMPONENTS_GALLERY_TIMEOUT = 15


@contextmanager
def set_directory(working_directory: str | Path):
    """Context manager that sets the working directory.

    Args:
        working_directory: The working directory to change to.

    Yields:
        Yield to the caller to perform operations in the working directory.
    """
    current_directory = Path.cwd()
    working_directory = Path(working_directory)
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

    pyproject = Path(CustomComponents.PYPROJECT_TOML)
    pyproject.write_text(
        templates.CUSTOM_COMPONENTS_PYPROJECT_TOML.render(
            module_name=module_name,
            package_name=package_name,
            reflex_version=constants.Reflex.VERSION,
        )
    )


def _get_package_config(exit_on_fail: bool = True) -> dict:
    """Get the package configuration from the pyproject.toml file.

    Args:
        exit_on_fail: Whether to exit if the pyproject.toml file is not found.

    Returns:
        The package configuration.

    Raises:
        Exit: If the pyproject.toml file is not found.
    """
    pyproject = Path(CustomComponents.PYPROJECT_TOML)
    try:
        return dict(tomlkit.loads(pyproject.read_bytes()))
    except (OSError, TOMLKitError) as ex:
        console.error(f"Unable to read from {pyproject} due to {ex}")
        if exit_on_fail:
            raise typer.Exit(code=1) from ex
        raise


def _create_readme(module_name: str, package_name: str):
    """Create a package README file.

    Args:
        module_name: The name of the module.
        package_name: The name of the python package to be published.
    """
    from reflex.compiler import templates

    readme = Path(CustomComponents.PACKAGE_README)
    readme.write_text(
        templates.CUSTOM_COMPONENTS_README.render(
            module_name=module_name,
            package_name=package_name,
        )
    )


def _write_source_and_init_py(
    custom_component_src_dir: Path,
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

    module_path = custom_component_src_dir / f"{module_name}.py"
    module_path.write_text(
        templates.CUSTOM_COMPONENTS_SOURCE.render(
            component_class_name=component_class_name, module_name=module_name
        )
    )

    init_path = custom_component_src_dir / CustomComponents.INIT_FILE
    init_path.write_text(
        templates.CUSTOM_COMPONENTS_INIT_FILE.render(module_name=module_name)
    )


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
        _init(name=demo_app_name, template=constants.Templates.DEFAULT)
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
    current_dir_name = Path.cwd().name

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

    custom_component_module_dir = Path(f"reflex_{module_name}")
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

    if CustomComponents.PYPROJECT_TOML.exists():
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


def _make_pyi_files():
    """Create pyi files for the custom component."""
    from reflex.utils.pyi_generator import PyiGenerator

    package_name = _get_package_config()["project"]["name"]

    for dir, _, _ in os.walk(f"./{package_name}"):
        if "__pycache__" in dir:
            continue
        PyiGenerator().scan_all([dir])


def _run_build():
    """Run the build command.

    Raises:
        Exit: If the build fails.
    """
    console.print("Building custom component...")

    _make_pyi_files()

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

    Returns:
        The version to publish.
    """
    return _get_package_config()["project"]["version"]


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
                    choices=["y", "n"],
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
        environment.TWINE_USERNAME.get(),
        "-u",
        "--username",
        show_default="TWINE_USERNAME environment variable value if set",
        help="The username to use for authentication on python package repository. Username and password must both be provided.",
    ),
    password: Optional[str] = typer.Option(
        environment.TWINE_PASSWORD.get(),
        "-p",
        "--password",
        show_default="TWINE_PASSWORD environment variable value if set",
        help="The password to use for authentication on python package repository. Username and password must both be provided.",
    ),
    build: bool = typer.Option(
        True,
        help="Whether to build the package before publishing. If the package is already built, set this to False.",
    ),
    share: bool = typer.Option(
        True,
        help="Whether to prompt to share more details on the published package. Only applicable when published to PyPI. Defaults to True.",
    ),
    validate_project_info: bool = typer.Option(
        True,
        help="Whether to interactively validate the project information in the pyproject.toml file.",
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
        share: Whether to prompt to share more details on the published package. Defaults to True.
        validate_project_info: whether to interactively validate the project information in the pyproject.toml file. Defaults to True.
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

    # Minimal Validation of the pyproject.toml.
    _min_validate_project_info()

    # Get the version to publish from the pyproject.toml.
    version_to_publish = _get_version_to_publish()

    # Validate the distribution directory.
    _ensure_dist_dir(version_to_publish=version_to_publish, build=build)

    if validate_project_info and (
        console.ask(
            "Would you like to interactively review the package information?",
            choices=["y", "n"],
            default="y",
        )
        == "y"
    ):
        _validate_project_info()

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

    # Only prompt to share more details on the published package if it is published to PyPI.
    if repository != "pypi" or not share:
        return

    # Ask user to share more details on the published package.
    if (
        console.ask(
            "Would you like to include your published component on our gallery?",
            choices=["y", "n"],
            default="y",
        )
        == "n"
    ):
        console.print(
            "If you decide to do this later, you can run `reflex component share` command. Thank you!"
        )
        return

    _collect_details_for_gallery()


def _process_entered_list(input: str | None) -> list | None:
    """Process the user entered comma separated list into a list if applicable.

    Args:
        input: the user entered comma separated list

    Returns:
        The list of items or None.
    """
    return [t.strip() for t in (input or "").split(",") if t if input] or None


def _min_validate_project_info():
    """Ensures minimal project information in the pyproject.toml file.

    Raises:
        Exit: If the pyproject.toml file is ill-formed.
    """
    pyproject_toml = _get_package_config()

    project = pyproject_toml.get("project")
    if project is None:
        console.error(
            f"The project section is not found in {CustomComponents.PYPROJECT_TOML}"
        )
        raise typer.Exit(code=1)

    if not project.get("name"):
        console.error(
            f"The project name is not found in {CustomComponents.PYPROJECT_TOML}"
        )
        raise typer.Exit(code=1)

    if not project.get("version"):
        console.error(
            f"The project version is not found in {CustomComponents.PYPROJECT_TOML}"
        )
        raise typer.Exit(code=1)


def _validate_project_info():
    """Validate the project information in the pyproject.toml file.

    Raises:
        Exit: If the pyproject.toml file is ill-formed.
    """
    pyproject_toml = _get_package_config()
    project = pyproject_toml["project"]
    console.print(
        f'Double check the information before publishing: {project["name"]} version {project["version"]}'
    )

    console.print("Update or enter to keep the current information.")
    project["description"] = console.ask(
        "short description", default=project.get("description", "")
    )
    # PyPI only shows the first author.
    author = project.get("authors", [{}])[0]
    author["name"] = console.ask("Author Name", default=author.get("name", ""))
    author["email"] = console.ask("Author Email", default=author.get("email", ""))

    console.print(f'Current keywords are: {project.get("keywords") or []}')
    keyword_action = console.ask(
        "Keep, replace or append?", choices=["k", "r", "a"], default="k"
    )
    new_keywords = []
    if keyword_action == "r":
        new_keywords = (
            _process_entered_list(
                console.ask("Enter new set of keywords separated by commas")
            )
            or []
        )
        project["keywords"] = new_keywords
    elif keyword_action == "a":
        new_keywords = (
            _process_entered_list(
                console.ask("Enter new set of keywords separated by commas")
            )
            or []
        )
        project["keywords"] = project.get("keywords", []) + new_keywords

    if not project.get("urls"):
        project["urls"] = {}
    project["urls"]["homepage"] = console.ask(
        "homepage URL", default=project["urls"].get("homepage", "")
    )
    project["urls"]["source"] = console.ask(
        "source code URL", default=project["urls"].get("source", "")
    )
    pyproject_toml["project"] = project
    try:
        with open(CustomComponents.PYPROJECT_TOML, "w") as f:
            tomlkit.dump(pyproject_toml, f)
    except (OSError, TOMLKitError) as ex:
        console.error(f"Unable to write to pyproject.toml due to {ex}")
        raise typer.Exit(code=1) from ex


def _collect_details_for_gallery():
    """Helper to collect details on the custom component to be included in the gallery.

    Raises:
        Exit: If pyproject.toml file is ill-formed or the request to the backend services fails.
    """
    from reflex.reflex import _login

    console.rule("[bold]Authentication with Reflex Services")
    console.print("First let's log in to Reflex backend services.")
    access_token = _login()

    console.rule("[bold]Custom Component Information")
    params = {}
    package_name = None
    try:
        package_name = _get_package_config(exit_on_fail=False)["project"]["name"]
    except (TOMLKitError, KeyError) as ex:
        console.debug(
            f"Unable to read from pyproject.toml in current directory due to {ex}"
        )
        package_name = console.ask("[ Published python package name ]")
    console.print(f"[ Custom component package name ] : {package_name}")
    params["package_name"] = package_name

    # Check the backend services if the user is allowed to update information of this package is already shared.
    try:
        console.debug(
            f"Checking if user has permission to upsert information for {package_name} by POST."
        )
        # Send a POST request to achieve two things at once:
        # 1. Check if the package is already shared by the user. If not, the backend will return 403.
        # 2. If this package is not shared before, this request records the package name in the backend.
        response = httpx.post(
            POST_CUSTOM_COMPONENTS_GALLERY_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            data=params,
        )
        if response.status_code == httpx.codes.FORBIDDEN:
            console.error(
                f"{package_name} is owned by another user. Unable to update the information for it."
            )
            raise typer.Exit(code=1)
        response.raise_for_status()
    except httpx.HTTPError as he:
        console.error(f"Unable to complete request due to {he}.")
        raise typer.Exit(code=1) from he

    files = []
    if (image_file_and_extension := _get_file_from_prompt_in_loop()) is not None:
        files.append(
            ("files", (image_file_and_extension[1], image_file_and_extension[0]))
        )

    demo_url = None
    while True:
        demo_url = (
            console.ask(
                "[ Full URL of deployed demo app, e.g. `https://my-app.reflex.run` ] (enter to skip)"
            )
            or None
        )
        if _validate_url_with_protocol_prefix(demo_url):
            break
    if demo_url:
        params["demo_url"] = demo_url

    # Now send the post request to Reflex backend services.
    try:
        console.debug(f"Sending custom component data: {params}")
        response = httpx.post(
            POST_CUSTOM_COMPONENTS_GALLERY_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            data=params,
            files=files,
            timeout=POST_CUSTOM_COMPONENTS_GALLERY_TIMEOUT,
        )
        response.raise_for_status()

    except httpx.HTTPError as he:
        console.error(f"Unable to complete request due to {he}.")
        raise typer.Exit(code=1) from he

    console.info("Custom component information successfully shared!")


def _validate_url_with_protocol_prefix(url: str | None) -> bool:
    """Validate the URL with protocol prefix. Empty string is acceptable.

    Args:
        url: the URL string to check.

    Returns:
        Whether the entered URL is acceptable.
    """
    return not url or (url.startswith("http://") or url.startswith("https://"))


def _get_file_from_prompt_in_loop() -> Tuple[bytes, str] | None:
    image_file = file_extension = None
    while image_file is None:
        image_filepath = console.ask(
            "Upload a preview image of your demo app (enter to skip)"
        )
        if not image_filepath:
            break
        file_extension = image_filepath.split(".")[-1]
        try:
            with open(image_filepath, "rb") as f:
                image_file = f.read()
                return image_file, file_extension
        except OSError as ose:
            console.error(f"Unable to read the {file_extension} file due to {ose}")
            raise typer.Exit(code=1) from ose

    console.debug(f"File extension detected: {file_extension}")
    return None


@custom_components_cli.command(name="share")
def share_more_detail(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Collect more details on the published package for gallery.

    Args:
        loglevel: The log level to use.
    """
    console.set_log_level(loglevel)

    _collect_details_for_gallery()


@custom_components_cli.command()
def install(
    loglevel: constants.LogLevel = typer.Option(
        config.loglevel, help="The log level to use."
    ),
):
    """Install package from this local custom component in editable mode.

    Args:
        loglevel: The log level to use.

    Raises:
        Exit: If unable to install the current directory in editable mode.
    """
    console.set_log_level(loglevel)

    if _pip_install_on_demand(package_name=".", install_args=["-e"]):
        console.info("Package installed successfully!")
    else:
        raise typer.Exit(code=1)
