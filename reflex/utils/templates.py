"""This module provides utilities for managing Reflex app templates."""

import dataclasses
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from reflex import constants
from reflex.config import get_config
from reflex.utils import console, net, path_ops, redir


@dataclasses.dataclass(frozen=True)
class Template:
    """A template for a Reflex app."""

    name: str
    description: str
    code_url: str


def create_config(app_name: str):
    """Create a new rxconfig file.

    Args:
        app_name: The name of the app.
    """
    # Import here to avoid circular imports.
    from reflex.compiler import templates

    console.debug(f"Creating {constants.Config.FILE}")
    constants.Config.FILE.write_text(templates.rxconfig_template(app_name=app_name))


def initialize_app_directory(
    app_name: str,
    template_name: str = constants.Templates.DEFAULT,
    template_code_dir_name: str | None = None,
    template_dir: Path | None = None,
):
    """Initialize the app directory on reflex init.

    Args:
        app_name: The name of the app.
        template_name: The name of the template to use.
        template_code_dir_name: The name of the code directory in the template.
        template_dir: The directory of the template source files.

    Raises:
        SystemExit: If template_name, template_code_dir_name, template_dir combination is not supported.
    """
    console.log("Initializing the app directory.")

    # By default, use the blank template from local assets.
    if template_name == constants.Templates.DEFAULT:
        if template_code_dir_name is not None or template_dir is not None:
            console.error(
                f"Only {template_name=} should be provided, got {template_code_dir_name=}, {template_dir=}."
            )
            raise SystemExit(1)
        template_code_dir_name = constants.Templates.Dirs.CODE
        template_dir = Path(constants.Templates.Dirs.BASE, "apps", template_name)
    else:
        if template_code_dir_name is None or template_dir is None:
            console.error(
                f"For `{template_name}` template, `template_code_dir_name` and `template_dir` should both be provided."
            )
            raise SystemExit(1)

    console.debug(f"Using {template_name=} {template_dir=} {template_code_dir_name=}.")

    # Remove __pycache__ dirs in template directory and current directory.
    for pycache_dir in [
        *template_dir.glob("**/__pycache__"),
        *Path.cwd().glob("**/__pycache__"),
    ]:
        shutil.rmtree(pycache_dir, ignore_errors=True)

    for file in template_dir.iterdir():
        # Copy the file to current directory but keep the name the same.
        path_ops.cp(str(file), file.name)

    # Rename the template app to the app name.
    path_ops.mv(template_code_dir_name, app_name)
    path_ops.mv(
        Path(app_name) / (template_name + constants.Ext.PY),
        Path(app_name) / (app_name + constants.Ext.PY),
    )

    # Fix up the imports.
    path_ops.find_replace(
        app_name,
        f"from {template_name}",
        f"from {app_name}",
    )


def initialize_default_app(app_name: str):
    """Initialize the default app.

    Args:
        app_name: The name of the app.
    """
    create_config(app_name)
    initialize_app_directory(app_name)


def create_config_init_app_from_remote_template(app_name: str, template_url: str):
    """Create new rxconfig and initialize app using a remote template.

    Args:
        app_name: The name of the app.
        template_url: The path to the template source code as a zip file.

    Raises:
        SystemExit: If any download, file operations fail or unexpected zip file format.

    """
    import httpx

    # Create a temp directory for the zip download.
    try:
        temp_dir = tempfile.mkdtemp()
    except OSError as ose:
        console.error(f"Failed to create temp directory for download: {ose}")
        raise SystemExit(1) from None

    # Use httpx GET with redirects to download the zip file.
    zip_file_path: Path = Path(temp_dir) / "template.zip"
    try:
        # Note: following redirects can be risky. We only allow this for reflex built templates at the moment.
        response = net.get(template_url, follow_redirects=True)
        console.debug(f"Server responded download request: {response}")
        response.raise_for_status()
    except httpx.HTTPError as he:
        console.error(f"Failed to download the template: {he}")
        raise SystemExit(1) from None
    try:
        zip_file_path.write_bytes(response.content)
        console.debug(f"Downloaded the zip to {zip_file_path}")
    except OSError as ose:
        console.error(f"Unable to write the downloaded zip to disk {ose}")
        raise SystemExit(1) from None

    # Create a temp directory for the zip extraction.
    try:
        unzip_dir = Path(tempfile.mkdtemp())
    except OSError as ose:
        console.error(f"Failed to create temp directory for extracting zip: {ose}")
        raise SystemExit(1) from None

    try:
        zipfile.ZipFile(zip_file_path).extractall(path=unzip_dir)
        # The zip file downloaded from github looks like:
        # repo-name-branch/**/*, so we need to remove the top level directory.
    except Exception as uze:
        console.error(f"Failed to unzip the template: {uze}")
        raise SystemExit(1) from None

    if len(subdirs := list(unzip_dir.iterdir())) != 1:
        console.error(f"Expected one directory in the zip, found {subdirs}")
        raise SystemExit(1)

    template_dir = unzip_dir / subdirs[0]
    console.debug(f"Template folder is located at {template_dir}")

    # Move the rxconfig file here first.
    path_ops.mv(str(template_dir / constants.Config.FILE), constants.Config.FILE)
    new_config = get_config(reload=True)

    # Get the template app's name from rxconfig in case it is different than
    # the source code repo name on github.
    template_name = new_config.app_name

    create_config(app_name)
    initialize_app_directory(
        app_name,
        template_name=template_name,
        template_code_dir_name=template_name,
        template_dir=template_dir,
    )
    req_file = Path("requirements.txt")
    if req_file.exists() and len(req_file.read_text().splitlines()) > 1:
        console.info(
            "Run `pip install -r requirements.txt` to install the required python packages for this template."
        )
    #  Clean up the temp directories.
    shutil.rmtree(temp_dir)
    shutil.rmtree(unzip_dir)


def validate_and_create_app_using_remote_template(
    app_name: str, template: str, templates: dict[str, Template]
):
    """Validate and create an app using a remote template.

    Args:
        app_name: The name of the app.
        template: The name of the template.
        templates: The available templates.

    Raises:
        SystemExit: If the template is not found.
    """
    # If user selects a template, it needs to exist.
    if template in templates:
        from reflex_cli.v2.utils import hosting

        authenticated_token = hosting.authenticated_token()
        if not authenticated_token or not authenticated_token[0]:
            console.print(
                f"Please use `reflex login` to access the '{template}' template."
            )
            raise SystemExit(3)

        template_url = templates[template].code_url
    else:
        template_parsed_url = urlparse(template)
        # Check if the template is a github repo.
        if template_parsed_url.hostname == "github.com":
            path = template_parsed_url.path.strip("/").removesuffix(".git")
            template_url = f"https://github.com/{path}/archive/main.zip"
        else:
            console.error(f"Template `{template}` not found or invalid.")
            raise SystemExit(1)

    if template_url is None:
        return

    create_config_init_app_from_remote_template(
        app_name=app_name, template_url=template_url
    )


def fetch_app_templates(version: str) -> dict[str, Template]:
    """Fetch a dict of templates from the templates repo using github API.

    Args:
        version: The version of the templates to fetch.

    Returns:
        The dict of templates.
    """

    def get_release_by_tag(tag: str) -> dict | None:
        response = net.get(constants.Reflex.RELEASES_URL)
        response.raise_for_status()
        releases = response.json()
        for release in releases:
            if release["tag_name"] == f"v{tag}":
                return release
        return None

    release = get_release_by_tag(version)
    if release is None:
        console.warn(f"No templates known for version {version}")
        return {}

    assets = release.get("assets", [])
    asset = next((a for a in assets if a["name"] == "templates.json"), None)
    if asset is None:
        console.warn(f"Templates metadata not found for version {version}")
        return {}
    templates_url = asset["browser_download_url"]

    templates_data = net.get(templates_url, follow_redirects=True).json()["templates"]

    for template in templates_data:
        if template["name"] == "blank":
            template["code_url"] = ""
            continue
        template["code_url"] = next(
            (
                a["browser_download_url"]
                for a in assets
                if a["name"] == f"{template['name']}.zip"
            ),
            None,
        )

    filtered_templates = {}
    for tp in templates_data:
        if tp["hidden"] or tp["code_url"] is None:
            continue
        known_fields = {f.name for f in dataclasses.fields(Template)}
        filtered_templates[tp["name"]] = Template(**{
            k: v for k, v in tp.items() if k in known_fields
        })
    return filtered_templates


def fetch_remote_templates(
    template: str,
) -> tuple[str, dict[str, Template]]:
    """Fetch the available remote templates.

    Args:
        template: The name of the template.

    Returns:
        The selected template and the available templates.
    """
    available_templates = {}

    try:
        # Get the available templates
        available_templates = fetch_app_templates(constants.Reflex.VERSION)
    except Exception as e:
        console.warn("Failed to fetch templates. Falling back to default template.")
        console.debug(f"Error while fetching templates: {e}")
        template = constants.Templates.DEFAULT

    return template, available_templates


def prompt_for_template_options(templates: list[Template]) -> str:
    """Prompt the user to specify a template.

    Args:
        templates: The templates to choose from.

    Returns:
        The template name the user selects.

    Raises:
        SystemExit: If the user does not select a template.
    """
    # Show the user the URLs of each template to preview.
    console.print("\nGet started with a template:")

    # Prompt the user to select a template.
    for index, template in enumerate(templates):
        console.print(f"({index}) {template.description}")

    template = console.ask(
        "Which template would you like to use?",
        choices=[str(i) for i in range(len(templates))],
        show_choices=False,
        default="0",
    )

    if not template:
        console.error("No template selected.")
        raise SystemExit(1)

    try:
        template_index = int(template)
    except ValueError:
        console.error("Invalid template selected.")
        raise SystemExit(1) from None

    if template_index < 0 or template_index >= len(templates):
        console.error("Invalid template selected.")
        raise SystemExit(1)

    # Return the template.
    return templates[template_index].name


def initialize_app(app_name: str, template: str | None = None) -> str | None:
    """Initialize the app either from a remote template or a blank app. If the config file exists, it is considered as reinit.

    Args:
        app_name: The name of the app.
        template: The name of the template to use.

    Returns:
        The name of the template.

    Raises:
        SystemExit: If the template is not valid or unspecified.
    """
    # Local imports to avoid circular imports.
    from reflex.utils import telemetry

    # Check if the app is already initialized.
    if constants.Config.FILE.exists():
        telemetry.send("reinit")
        return None

    templates: dict[str, Template] = {}

    # Don't fetch app templates if the user directly asked for DEFAULT.
    if template is not None and template != constants.Templates.DEFAULT:
        template, templates = fetch_remote_templates(template)

    if template is None:
        template = prompt_for_template_options(get_init_cli_prompt_options())

        if template == constants.Templates.CHOOSE_TEMPLATES:
            redir.reflex_templates()
            raise SystemExit(0)

    if template == constants.Templates.AI:
        redir.reflex_build_redirect()
        raise SystemExit(0)

    # If the blank template is selected, create a blank app.
    if template == constants.Templates.DEFAULT:
        # Default app creation behavior: a blank app.
        initialize_default_app(app_name)
    else:
        validate_and_create_app_using_remote_template(
            app_name=app_name, template=template, templates=templates
        )

    telemetry.send("init", template=template)

    return template


def get_init_cli_prompt_options() -> list[Template]:
    """Get the CLI options for initializing a Reflex app.

    Returns:
        The CLI options.
    """
    return [
        Template(
            name=constants.Templates.AI,
            description="[bold]Try our free AI builder.",
            code_url="",
        ),
        Template(
            name=constants.Templates.DEFAULT,
            description="A blank Reflex app.",
            code_url="",
        ),
        Template(
            name=constants.Templates.CHOOSE_TEMPLATES,
            description="Premade templates built by the Reflex team.",
            code_url="",
        ),
    ]
