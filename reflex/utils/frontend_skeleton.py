"""This module provides utility functions to initialize the frontend skeleton."""

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

from reflex_base import constants
from reflex_base.config import Config, get_config
from reflex_base.environment import environment

from reflex.compiler import templates
from reflex.utils import console, path_ops
from reflex.utils.prerequisites import get_project_hash, get_web_dir
from reflex.utils.registry import get_npm_registry


@dataclass(frozen=True)
class PythonManifestInitResult:
    """The result of initializing a project's Python dependency manifest."""

    kind: Literal["pyproject", "requirements"]
    needs_manual_reflex_dependency: bool = False


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


def _read_dependency_file(file_path: Path) -> tuple[str | None, str | None]:
    """Read a dependency file with a forgiving encoding strategy.

    Args:
        file_path: The file to read.

    Returns:
        A tuple of file content and the encoding used to read it.
    """
    try:
        return file_path.read_text(), None
    except UnicodeDecodeError:
        pass
    except Exception as e:
        console.error(f"Failed to read {file_path} due to {e}.")
        raise SystemExit(1) from None

    try:
        return file_path.read_text(encoding="utf-8"), "utf-8"
    except UnicodeDecodeError:
        return None, None
    except Exception as e:
        console.error(f"Failed to read {file_path} due to {e}.")
        raise SystemExit(1) from None


def _has_reflex_requirement_line(requirements_text: str) -> bool:
    """Check whether requirements.txt already contains reflex.

    Returns:
        Whether reflex is already present in the requirements text.
    """
    return any(
        _is_reflex_dependency_spec(line) for line in requirements_text.splitlines()
    )


def _is_reflex_dependency_spec(requirement: str) -> bool:
    """Check whether a dependency specification refers to the reflex package.

    Args:
        requirement: The dependency specification to check.

    Returns:
        Whether the specification refers to the reflex package.
    """
    requirement = requirement.strip()
    if not requirement.lower().startswith("reflex"):
        return False

    suffix = requirement[len("reflex") :]
    if suffix.startswith("["):
        extras_end = suffix.find("]")
        if extras_end == -1:
            return False
        suffix = suffix[extras_end + 1 :]

    return not suffix or suffix.lstrip().startswith((
        "==",
        "!=",
        ">=",
        "<=",
        "~=",
        ">",
        "<",
        ";",
        "@",
    ))


def _pyproject_has_reflex_dependency_in_project_table(
    pyproject_data: dict[str, Any],
) -> bool:
    """Check parsed pyproject data for a Reflex dependency in supported tables.

    Returns:
        Whether Reflex is declared in a supported pyproject dependency table.
    """
    project = pyproject_data.get("project", {})
    if isinstance(project, dict):
        dependencies = project.get("dependencies", [])
        if isinstance(dependencies, list) and any(
            isinstance(dependency, str) and _is_reflex_dependency_spec(dependency)
            for dependency in dependencies
        ):
            return True

    poetry_dependencies = (
        pyproject_data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    return isinstance(poetry_dependencies, dict) and any(
        isinstance(dependency_name, str) and dependency_name.lower() == "reflex"
        for dependency_name in poetry_dependencies
    )


def _extract_toml_string_values(toml_line: str) -> list[str]:
    """Extract quoted string values from a TOML line.

    Returns:
        The quoted string values found in the line.
    """
    return [
        value
        for _, value in re.findall(
            r"""(["'])((?:\\.|(?!\1).)*)\1""",
            toml_line,
        )
    ]


def _has_reflex_dependency_in_pyproject_fallback(pyproject_text: str) -> bool:
    """Check pyproject.toml text for Reflex dependency declarations without TOML parsing.

    Returns:
        Whether Reflex is declared in a supported dependency section.
    """
    current_section: tuple[str, ...] = ()
    reading_project_dependencies = False

    for raw_line in pyproject_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        section_match = re.match(r"^\[([^\]]+)\](?:\s+#.*)?$", line)
        if section_match:
            current_section = tuple(
                part.strip() for part in section_match.group(1).split(".")
            )
            reading_project_dependencies = False
            continue

        if reading_project_dependencies:
            if any(
                _is_reflex_dependency_spec(value)
                for value in _extract_toml_string_values(line)
            ):
                return True
            if "]" in line:
                reading_project_dependencies = False
            continue

        if current_section == ("project",):
            dependencies_match = re.match(r"^dependencies\s*=\s*\[(.*)$", line)
            if dependencies_match:
                dependency_values = dependencies_match.group(1)
                if any(
                    _is_reflex_dependency_spec(value)
                    for value in _extract_toml_string_values(dependency_values)
                ):
                    return True
                if "]" not in dependency_values:
                    reading_project_dependencies = True
                continue

        if current_section == ("tool", "poetry", "dependencies"):
            poetry_match = re.match(
                r"""^(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_.-]+))\s*=""", line
            )
            dependency_name = (
                next(
                    (group for group in poetry_match.groups() if group),
                    None,
                )
                if poetry_match
                else None
            )
            if dependency_name and dependency_name.lower() == "reflex":
                return True

    return False


def _has_reflex_dependency_in_pyproject(pyproject_text: str) -> bool:
    """Check whether pyproject.toml already declares reflex as a dependency.

    Returns:
        Whether reflex is already declared as a dependency.
    """
    if tomllib is not None:
        try:
            return _pyproject_has_reflex_dependency_in_project_table(
                tomllib.loads(pyproject_text)
            )
        except tomllib.TOMLDecodeError:
            pass

    return _has_reflex_dependency_in_pyproject_fallback(pyproject_text)


def _initialize_requirements_txt(
    requirements_file_path: Path,
) -> PythonManifestInitResult:
    """Initialize or update a legacy requirements.txt file.

    Returns:
        The manifest initialization result for a requirements.txt-based project.
    """
    requirements_file_path.touch(exist_ok=True)

    content, encoding = _read_dependency_file(requirements_file_path)
    if content is None:
        return PythonManifestInitResult(
            kind="requirements",
            needs_manual_reflex_dependency=True,
        )

    if _has_reflex_requirement_line(content):
        console.debug(f"{requirements_file_path} already has reflex as dependency.")
        return PythonManifestInitResult(kind="requirements")

    console.debug(
        f"Appending {constants.RequirementsTxt.DEFAULTS_STUB} to {requirements_file_path}"
    )
    with requirements_file_path.open("a", encoding=encoding) as f:
        f.write(
            "\n" + constants.RequirementsTxt.DEFAULTS_STUB + constants.Reflex.VERSION
        )

    return PythonManifestInitResult(kind="requirements")


def _initialize_pyproject_toml(pyproject_file_path: Path, app_name: str):
    """Create a minimal pyproject.toml for a new Reflex app.

    Raises:
        SystemExit: If the pyproject.toml file cannot be written.
    """
    console.debug(f"Creating {pyproject_file_path}")
    try:
        pyproject_file_path.write_text(
            templates.pyproject_toml_template(
                app_name=app_name,
                reflex_version=constants.Reflex.VERSION,
            )
        )
    except Exception as e:
        console.error(f"Failed to write {pyproject_file_path} due to {e}.")
        raise SystemExit(1) from None


def initialize_python_manifest(
    app_name: str,
    *,
    pyproject_file_path: Path = Path(constants.PyprojectToml.FILE),
    requirements_file_path: Path = Path(constants.RequirementsTxt.FILE),
) -> PythonManifestInitResult:
    """Initialize the Python dependency manifest for a Reflex app.

    The default for new apps is pyproject.toml. Existing projects that already use
    requirements.txt continue to be supported without creating a second manifest.

    Args:
        app_name: The initialized app name.
        pyproject_file_path: The pyproject.toml path.
        requirements_file_path: The requirements.txt path.

    Returns:
        The manifest initialization result.
    """
    if pyproject_file_path.exists():
        content, _ = _read_dependency_file(pyproject_file_path)
        return PythonManifestInitResult(
            kind="pyproject",
            needs_manual_reflex_dependency=(
                content is None or not _has_reflex_dependency_in_pyproject(content)
            ),
        )

    if requirements_file_path.exists():
        return _initialize_requirements_txt(requirements_file_path)

    _initialize_pyproject_toml(pyproject_file_path, app_name)
    return PythonManifestInitResult(kind="pyproject")


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
    config = get_config()
    return templates.package_json_template(
        scripts={
            "dev": constants.PackageJson.Commands.DEV,
            "export": constants.PackageJson.Commands.EXPORT,
            "prod": constants.PackageJson.Commands.get_prod_command(
                config.frontend_path
            ),
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
        allowed_hosts=config.vite_allowed_hosts,
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
