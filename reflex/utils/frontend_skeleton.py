"""This module provides utility functions to initialize the frontend skeleton."""

import json
import random
import re
from pathlib import Path

from reflex import constants
from reflex.compiler import templates
from reflex.config import Config, get_config
from reflex.environment import environment
from reflex.utils import console, path_ops
from reflex.utils.prerequisites import get_project_hash, get_web_dir
from reflex.utils.registry import get_npm_registry


def initialize_gitignore(
    gitignore_file: Path = constants.GitIgnore.FILE,
    files_to_ignore: set[str] | list[str] = constants.GitIgnore.DEFAULTS,
):
    """Initialize the template .gitignore file.

    Args:
        gitignore_file: The .gitignore file to create.
        files_to_ignore: The files to add to the .gitignore file.
    """
    # Combine with the current ignored files.
    current_ignore: list[str] = []
    if gitignore_file.exists():
        current_ignore = [ln.strip() for ln in gitignore_file.read_text().splitlines()]

    if files_to_ignore == current_ignore:
        console.debug(f"{gitignore_file} already up to date.")
        return
    files_to_ignore = [ln for ln in files_to_ignore if ln not in current_ignore]
    files_to_ignore += current_ignore

    # Write files to the .gitignore file.
    gitignore_file.touch(exist_ok=True)
    console.debug(f"Creating {gitignore_file}")
    gitignore_file.write_text("\n".join(files_to_ignore) + "\n")


def initialize_requirements_txt() -> bool:
    """Initialize the requirements.txt file.
    If absent and no pyproject.toml file exists, generate one for the user.
    If the requirements.txt does not have reflex as dependency,
    generate a requirement pinning current version and append to
    the requirements.txt file.

    Returns:
        True if the user has to update the requirements.txt file.

    Raises:
        SystemExit: If the requirements.txt file cannot be read or written to.
    """
    requirements_file_path = Path(constants.RequirementsTxt.FILE)
    if (
        not requirements_file_path.exists()
        and Path(constants.PyprojectToml.FILE).exists()
    ):
        return True

    requirements_file_path.touch(exist_ok=True)

    for encoding in [None, "utf-8"]:
        try:
            content = requirements_file_path.read_text(encoding)
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            console.error(f"Failed to read {requirements_file_path} due to {e}.")
            raise SystemExit(1) from None
    else:
        return True

    for line in content.splitlines():
        if re.match(r"^reflex[^a-zA-Z0-9]", line):
            console.debug(f"{requirements_file_path} already has reflex as dependency.")
            return False

    console.debug(
        f"Appending {constants.RequirementsTxt.DEFAULTS_STUB} to {requirements_file_path}"
    )
    with requirements_file_path.open("a", encoding=encoding) as f:
        f.write(
            "\n" + constants.RequirementsTxt.DEFAULTS_STUB + constants.Reflex.VERSION
        )

    return False


def initialize_web_directory():
    """Initialize the web directory on reflex init."""
    console.log("Initializing the web directory.")

    # Reuse the hash if one is already created, so we don't over-write it when running reflex init
    project_hash = get_project_hash()

    console.debug(f"Copying {constants.Templates.Dirs.WEB_TEMPLATE} to {get_web_dir()}")
    path_ops.copy_tree(constants.Templates.Dirs.WEB_TEMPLATE, str(get_web_dir()))

    console.debug("Initializing the web directory.")
    initialize_package_json()

    console.debug("Initializing the bun config file.")
    initialize_bun_config()

    console.debug("Initializing the .npmrc file.")
    initialize_npmrc()

    console.debug("Initializing the public directory.")
    path_ops.mkdir(get_web_dir() / constants.Dirs.PUBLIC)

    console.debug("Initializing the react-router.config.js file.")
    update_react_router_config()

    console.debug("Initializing the vite.config.js file.")
    initialize_vite_config()

    console.debug("Initializing the reflex.json file.")
    # Initialize the reflex json file.
    init_reflex_json(project_hash=project_hash)


def update_react_router_config(prerender_routes: bool = False):
    """Update react-router.config.js config from Reflex config.

    Args:
        prerender_routes: Whether to enable prerendering of routes.
    """
    react_router_config_file_path = get_web_dir() / constants.ReactRouter.CONFIG_FILE

    new_react_router_config = _update_react_router_config(
        get_config(), prerender_routes=prerender_routes
    )

    # Overwriting the config file triggers a full server reload, so make sure
    # there is actually a diff.
    old_react_router_config = (
        react_router_config_file_path.read_text()
        if react_router_config_file_path.exists()
        else ""
    )
    if old_react_router_config != new_react_router_config:
        react_router_config_file_path.write_text(new_react_router_config)


def _update_react_router_config(config: Config, prerender_routes: bool = False):
    basename = "/" + (config.frontend_path or "").strip("/")
    if not basename.endswith("/"):
        basename += "/"

    react_router_config = {
        "basename": basename,
        "future": {
            "unstable_optimizeDeps": True,
        },
        "ssr": False,
    }

    if prerender_routes:
        react_router_config["prerender"] = True
        react_router_config["build"] = constants.Dirs.BUILD_DIR

    return f"export default {json.dumps(react_router_config)};"


def _compile_package_json():
    return templates.package_json_template(
        scripts={
            "dev": constants.PackageJson.Commands.DEV,
            "export": constants.PackageJson.Commands.EXPORT,
            "prod": constants.PackageJson.Commands.PROD,
        },
        dependencies=constants.PackageJson.DEPENDENCIES,
        dev_dependencies=constants.PackageJson.DEV_DEPENDENCIES,
        overrides=constants.PackageJson.OVERRIDES,
    )


def initialize_package_json():
    """Render and write in .web the package.json file."""
    output_path = get_web_dir() / constants.PackageJson.PATH
    output_path.write_text(_compile_package_json())


def _compile_vite_config(config: Config):
    # base must have exactly one trailing slash
    base = "/"
    if frontend_path := config.frontend_path.strip("/"):
        base += frontend_path + "/"
    return templates.vite_config_template(
        base=base,
        hmr=environment.VITE_HMR.get(),
        force_full_reload=environment.VITE_FORCE_FULL_RELOAD.get(),
        experimental_hmr=environment.VITE_EXPERIMENTAL_HMR.get(),
        sourcemap=environment.VITE_SOURCEMAP.get(),
    )


def initialize_vite_config():
    """Render and write in .web the vite.config.js file using Reflex config."""
    vite_config_file_path = get_web_dir() / constants.ReactRouter.VITE_CONFIG_FILE
    vite_config_file_path.write_text(_compile_vite_config(get_config()))


def initialize_bun_config():
    """Initialize the bun config file."""
    bun_config_path = get_web_dir() / constants.Bun.CONFIG_PATH

    if (custom_bunfig := Path(constants.Bun.CONFIG_PATH)).exists():
        bunfig_content = custom_bunfig.read_text()
        console.info(f"Copying custom bunfig.toml inside {get_web_dir()} folder")
    else:
        best_registry = get_npm_registry()
        bunfig_content = constants.Bun.DEFAULT_CONFIG.format(registry=best_registry)

    bun_config_path.write_text(bunfig_content)


def initialize_npmrc():
    """Initialize the .npmrc file."""
    npmrc_path = get_web_dir() / constants.Node.CONFIG_PATH

    if (custom_npmrc := Path(constants.Node.CONFIG_PATH)).exists():
        npmrc_content = custom_npmrc.read_text()
        console.info(f"Copying custom .npmrc inside {get_web_dir()} folder")
    else:
        best_registry = get_npm_registry()
        npmrc_content = constants.Node.DEFAULT_CONFIG.format(registry=best_registry)

    npmrc_path.write_text(npmrc_content)


def init_reflex_json(project_hash: int | None):
    """Write the hash of the Reflex project to a REFLEX_JSON.

    Reuse the hash if one is already created, therefore do not
    overwrite it every time we run the reflex init command
    .

    Args:
        project_hash: The app hash.
    """
    if project_hash is not None:
        console.debug(f"Project hash is already set to {project_hash}.")
    else:
        # Get a random project hash.
        project_hash = random.getrandbits(128)
        console.debug(f"Setting project hash to {project_hash}.")

    # Write the hash and version to the reflex json file.
    reflex_json = {
        "version": constants.Reflex.VERSION,
        "project_hash": project_hash,
    }
    path_ops.update_json_file(get_web_dir() / constants.Reflex.JSON, reflex_json)
