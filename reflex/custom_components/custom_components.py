"""CLI for creating custom components."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import click
import httpx

from reflex import constants
from reflex.constants import CustomComponents
from reflex.utils import console


def set_loglevel(ctx: Any, self: Any, value: str | None):
    """Set the log level.

    Args:
        ctx: The click context.
        self: The click command.
        value: The log level to set.
    """
    if value is not None:
        loglevel = constants.LogLevel.from_string(value)
        console.set_log_level(loglevel)


@click.group
def custom_components_cli():
    """CLI for creating custom components."""


loglevel_option = click.option(
    "--loglevel",
    type=click.Choice(
        [loglevel.value for loglevel in constants.LogLevel],
        case_sensitive=False,
    ),
    callback=set_loglevel,
    is_eager=True,
    expose_value=False,
    help="The log level to use.",
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

    demo_app_dir = Path(name_variants.demo_app_dir)
    demo_app_name = name_variants.demo_app_name

    console.info(f"Creating app for testing: {demo_app_dir!s}")

    demo_app_dir.mkdir(exist_ok=True)

    with set_directory(demo_app_dir):
        # We start with the blank template as basis.
        _init(name=demo_app_name, template=constants.Templates.DEFAULT)
        # Then overwrite the app source file with the one we want for testing custom components.
        # This source file is rendered using jinja template file.
        demo_file = Path(f"{demo_app_name}/{demo_app_name}.py")
        demo_file.write_text(
            templates.CUSTOM_COMPONENTS_DEMO_APP.render(
                custom_component_module_dir=name_variants.custom_component_module_dir,
                module_name=name_variants.module_name,
            )
        )
        # Append the custom component package to the requirements.txt file.
        with Path(f"{constants.RequirementsTxt.FILE}").open(mode="a") as f:
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
            raise click.exceptions.Exit(code=1)
    if not parts:
        # The folder likely has a name not suitable for python paths.
        console.error(
            f"Could not find a valid library name based on the current directory: got {current_dir_name}."
        )
        raise click.exceptions.Exit(code=1)
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
        raise click.exceptions.Exit(code=1)

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
        f"Initializing the component directory: {CustomComponents.SRC_DIR / name_variants.custom_component_module_dir}"
    )
    CustomComponents.SRC_DIR.mkdir(exist_ok=True)
    with set_directory(CustomComponents.SRC_DIR):
        module_dir = Path(name_variants.custom_component_module_dir)
        module_dir.mkdir(exist_ok=True, parents=True)
        _write_source_and_init_py(
            custom_component_src_dir=module_dir,
            component_class_name=name_variants.component_class_name,
            module_name=name_variants.module_name,
        )


@custom_components_cli.command(name="init")
@click.option(
    "--library-name",
    default=None,
    help="The name of your library. On PyPI, package will be published as `reflex-{library-name}`.",
)
@click.option(
    "--install/--no-install",
    default=True,
    help="Whether to install package from this local custom component in editable mode.",
)
@loglevel_option
def init(
    library_name: str | None,
    install: bool,
):
    """Initialize a custom component.

    Args:
        library_name: The name of the library.
        install: Whether to install package from this local custom component in editable mode.

    Raises:
        Exit: If the pyproject.toml already exists.
    """
    from reflex.utils import exec, prerequisites

    if CustomComponents.PYPROJECT_TOML.exists():
        console.error(f"A {CustomComponents.PYPROJECT_TOML} already exists. Aborting.")
        click.exceptions.Exit(code=1)

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
            raise click.exceptions.Exit(code=1)

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
    except subprocess.CalledProcessError as cpe:
        console.error(cpe.stdout)
        console.error(cpe.stderr)
        return False
    else:
        console.debug(result.stdout)
        return True


def _make_pyi_files():
    """Create pyi files for the custom component."""
    from reflex.utils.pyi_generator import PyiGenerator

    for top_level_dir in Path.cwd().iterdir():
        if not top_level_dir.is_dir() or top_level_dir.name.startswith("."):
            continue
        for dir, _, _ in top_level_dir.walk():
            if "__pycache__" in dir.name:
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
        raise click.exceptions.Exit(code=1)


@custom_components_cli.command(name="build")
@loglevel_option
def build():
    """Build a custom component. Must be run from the project root directory where the pyproject.toml is."""
    _run_build()


def _collect_details_for_gallery():
    """Helper to collect details on the custom component to be included in the gallery.

    Raises:
        Exit: If pyproject.toml file is ill-formed or the request to the backend services fails.
    """
    from reflex_cli.utils import hosting

    console.rule("[bold]Authentication with Reflex Services")
    console.print("First let's log in to Reflex backend services.")
    access_token, _ = hosting.authenticated_token()

    if not access_token:
        console.error(
            "Unable to authenticate with Reflex backend services. Make sure you are logged in."
        )
        raise click.exceptions.Exit(code=1)

    console.rule("[bold]Custom Component Information")
    params = {}

    package_name = console.ask("[ Published python package name ]")
    console.print(f"[ Custom component package name ] : {package_name}")
    params["package_name"] = package_name

    post_custom_components_gallery_endpoint = (
        "https://gallery-backend.reflex.dev/custom-components/gallery"
    )

    # Check the backend services if the user is allowed to update information of this package is already shared.
    try:
        console.debug(
            f"Checking if user has permission to upsert information for {package_name} by POST."
        )
        # Send a POST request to achieve two things at once:
        # 1. Check if the package is already shared by the user. If not, the backend will return 403.
        # 2. If this package is not shared before, this request records the package name in the backend.
        response = httpx.post(
            post_custom_components_gallery_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
            data=params,
        )
        if response.status_code == httpx.codes.FORBIDDEN:
            console.error(
                f"{package_name} is owned by another user. Unable to update the information for it."
            )
            raise click.exceptions.Exit(code=1)
        response.raise_for_status()
    except httpx.HTTPError as he:
        console.error(f"Unable to complete request due to {he}.")
        raise click.exceptions.Exit(code=1) from he

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
            post_custom_components_gallery_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
            data=params,
            files=files,
            timeout=POST_CUSTOM_COMPONENTS_GALLERY_TIMEOUT,
        )
        response.raise_for_status()

    except httpx.HTTPError as he:
        console.error(f"Unable to complete request due to {he}.")
        raise click.exceptions.Exit(code=1) from he

    console.info("Custom component information successfully shared!")


def _validate_url_with_protocol_prefix(url: str | None) -> bool:
    """Validate the URL with protocol prefix. Empty string is acceptable.

    Args:
        url: the URL string to check.

    Returns:
        Whether the entered URL is acceptable.
    """
    return not url or (url.startswith(("http://", "https://")))


def _get_file_from_prompt_in_loop() -> tuple[bytes, str] | None:
    image_file = file_extension = None
    while image_file is None:
        image_path_str = console.ask(
            "Upload a preview image of your demo app (enter to skip)"
        )
        if not image_path_str:
            break
        image_file_path = Path(image_path_str)
        if not image_file_path:
            break
        if not image_file_path.exists():
            console.error(f"File {image_file_path} does not exist.")
            continue
        file_extension = image_file_path.suffix
        try:
            image_file = image_file_path.read_bytes()
        except OSError as ose:
            console.error(f"Unable to read the {file_extension} file due to {ose}")
            raise click.exceptions.Exit(code=1) from ose
        else:
            return image_file, file_extension

    console.debug(f"File extension detected: {file_extension}")
    return None


@custom_components_cli.command(name="share")
@loglevel_option
def share_more_detail():
    """Collect more details on the published package for gallery."""
    _collect_details_for_gallery()


@custom_components_cli.command(name="install")
@loglevel_option
def install():
    """Install package from this local custom component in editable mode.

    Raises:
        Exit: If unable to install the current directory in editable mode.
    """
    if _pip_install_on_demand(package_name=".", install_args=["-e"]):
        console.info("Package installed successfully!")
    else:
        raise click.exceptions.Exit(code=1)
