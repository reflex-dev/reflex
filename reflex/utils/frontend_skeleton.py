"""This module provides utility functions to initialize the frontend skeleton."""

import json
import random
from pathlib import Path

from reflex_base import constants
from reflex_base.config import Config, get_config
from reflex_base.environment import environment
from reflex_base.plugins.embed import get_embed_plugin

from reflex.compiler import templates
from reflex.compiler.utils import write_file
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


def initialize_requirements_txt(
    requirements_file_path: Path = Path(constants.RequirementsTxt.FILE),
    pyproject_file_path: Path = Path(constants.PyprojectToml.FILE),
) -> bool:
    """Initialize the requirements.txt file.

    If a project already uses pyproject.toml, leave dependency management to the
    package manager. Otherwise ensure requirements.txt pins the current Reflex
    version for legacy workflows.

    Returns:
        True if the user has to update the requirements.txt file.
    """
    if not requirements_file_path.exists() and pyproject_file_path.exists():
        return False

    requirements_file_path.touch(exist_ok=True)

    content, encoding = _read_dependency_file(requirements_file_path)
    if content is None:
        return True

    if _has_reflex_requirement_line(content):
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


#: Lockfiles persisted under ``reflex.lock/`` and mirrored into ``.web``.
#: Both bun and npm flows are covered so projects can be (re)built with
#: either package manager without losing pinned versions.
LOCKFILE_NAMES: tuple[str, ...] = (
    constants.Bun.LOCKFILE_PATH,
    constants.Node.LOCKFILE_PATH,
)


def get_root_lockfile_path(filename: str) -> Path:
    """Get a persisted lockfile path under the app root's reflex.lock dir.

    Args:
        filename: The lockfile basename (e.g. ``bun.lock``, ``package-lock.json``).

    Returns:
        The lockfile path inside ``<cwd>/reflex.lock/``.
    """
    return Path.cwd() / constants.Bun.ROOT_LOCKFILE_DIR / filename


def get_web_lockfile_path(filename: str) -> Path:
    """Get the mirrored lockfile path inside ``.web``.

    Args:
        filename: The lockfile basename.

    Returns:
        The lockfile path inside the ``.web`` directory.
    """
    return get_web_dir() / filename


def get_root_package_json_path() -> Path:
    """Get the persisted package.json path in the app root.

    Stored alongside the lockfiles inside ``reflex.lock/`` so resolved
    dependency pins survive a fresh ``reflex init``.

    Returns:
        The persisted package.json path in the app root.
    """
    return Path.cwd() / constants.Bun.ROOT_LOCKFILE_DIR / constants.PackageJson.PATH


def get_web_package_json_path() -> Path:
    """Get the package.json path in the .web directory.

    Returns:
        The package.json path in the .web directory.
    """
    return get_web_dir() / constants.PackageJson.PATH


def _copy_if_exists(src: Path, dest: Path) -> bool:
    """Copy ``src`` to ``dest`` (creating ``dest`` parents as needed).

    Args:
        src: The source file. If absent, ``dest`` is removed when present.
        dest: The destination file.

    Returns:
        True if ``dest``'s effective contents changed (created from absence,
        overwritten with different bytes, or removed because ``src`` is gone).
    """
    if not src.exists():
        if dest.exists():
            console.debug(f"Removing stale {dest}")
            path_ops.rm(dest)
            return True
        return False

    if dest.exists() and dest.read_bytes() == src.read_bytes():
        return False

    changed = dest.exists()
    path_ops.mkdir(dest.parent)
    console.debug(f"Copying {src} to {dest}")
    path_ops.cp(src, dest)
    return changed


def sync_root_lockfile_to_web(filename: str) -> bool:
    """Mirror a single persisted lockfile into ``.web``.

    Args:
        filename: The lockfile basename.

    Returns:
        True if ``.web``'s copy was meaningfully changed (overwritten with
        different bytes or removed because the root copy is gone). Initial
        creation does not count as a meaningful change since no install
        cache could exist yet.
    """
    return _copy_if_exists(
        get_root_lockfile_path(filename), get_web_lockfile_path(filename)
    )


def sync_root_lockfiles_to_web() -> bool:
    """Mirror every persisted lockfile into ``.web``.

    Returns:
        True if any ``.web`` lockfile was meaningfully changed.
    """
    # Materialize results so every lockfile is synced
    changed = [sync_root_lockfile_to_web(name) for name in LOCKFILE_NAMES]
    return any(changed)


def sync_web_lockfile_to_root(filename: str):
    """Persist a single ``.web`` lockfile back to the app root.

    Args:
        filename: The lockfile basename.
    """
    web = get_web_lockfile_path(filename)
    if not web.exists():
        return
    root = get_root_lockfile_path(filename)
    path_ops.mkdir(root.parent)
    console.debug(f"Copying {web} to {root}")
    path_ops.cp(web, root)


def sync_web_lockfiles_to_root():
    """Persist every ``.web`` lockfile back to the app root."""
    for name in LOCKFILE_NAMES:
        sync_web_lockfile_to_root(name)


def sync_web_package_json_to_root():
    """Persist the resolved .web package.json back to the app root.

    Captures the dependency pins produced by ``bun add`` so the next
    ``reflex init`` can restore them as the starting point for the new
    package.json.
    """
    web_package_json_path = get_web_package_json_path()
    if not web_package_json_path.exists():
        return

    root_package_json_path = get_root_package_json_path()
    path_ops.mkdir(root_package_json_path.parent)
    console.debug(f"Copying {web_package_json_path} to {root_package_json_path}")
    path_ops.cp(web_package_json_path, root_package_json_path)


def _read_persisted_package_json() -> dict:
    """Read the persisted package.json from the app root.

    Returns:
        The parsed JSON object, or an empty dict if the file is missing or
        cannot be parsed.
    """
    root_package_json_path = get_root_package_json_path()
    if not root_package_json_path.exists():
        return {}
    try:
        return json.loads(root_package_json_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        console.warn(
            f"Failed to read {root_package_json_path}: {e}; starting with empty dependency lists."
        )
        return {}


def initialize_web_directory():
    """Initialize the web directory on reflex init."""
    console.log("Initializing the web directory.")

    # Reuse the hash if one is already created, so we don't over-write it when running reflex init
    project_hash = get_project_hash()

    console.debug(f"Copying {constants.Templates.Dirs.WEB_TEMPLATE} to {get_web_dir()}")
    path_ops.copy_tree(constants.Templates.Dirs.WEB_TEMPLATE, str(get_web_dir()))

    console.debug("Restoring lockfiles.")
    sync_root_lockfiles_to_web()

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


def update_entry_client():
    """Write ``.web/app/entry.client.js`` from the framework-mode template.

    Skipped when any registered plugin reports ``provides_entry_client()`` —
    that plugin emits its own variant via a save task and overwriting it
    here would just be redone on the same compile.
    """
    if any(p.provides_entry_client() for p in get_config().plugins):
        return
    write_file(
        get_web_dir() / constants.Embed.ENTRY_PATH,
        (
            constants.Templates.Dirs.WEB_TEMPLATE / constants.Embed.ENTRY_PATH
        ).read_text(),
    )


def update_react_router_config(prerender_routes: bool = False):
    """Update react-router.config.js config from Reflex config.

    Args:
        prerender_routes: Whether to enable prerendering of routes.
    """
    write_file(
        get_web_dir() / constants.ReactRouter.CONFIG_FILE,
        _update_react_router_config(get_config(), prerender_routes=prerender_routes),
    )


def _update_react_router_config(config: Config, prerender_routes: bool = False):
    react_router_config = {
        "basename": config.prepend_frontend_path("/"),
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
    """Build package.json content for .web.

    Recovers ``dependencies`` and ``devDependencies`` from the persisted
    ``reflex.lock/package.json`` (when present) so resolved version pins
    survive a fresh ``reflex init``. User-added ``scripts`` are preserved;
    only the framework-owned ``dev`` and ``export`` entries are refreshed
    from constants. ``overrides`` are always refreshed. The framework-managed
    entries in ``constants.PackageJson.DEPENDENCIES`` / ``DEV_DEPENDENCIES``
    are added later at install time via ``bun add`` so they pick up strict
    pins.

    Returns:
        Rendered package.json content as string.
    """
    persisted = _read_persisted_package_json()
    persisted_scripts = persisted.get("scripts") or {}
    scripts = {
        **persisted_scripts,
        "dev": constants.PackageJson.Commands.DEV,
        "export": constants.PackageJson.Commands.EXPORT,
    }
    return templates.package_json_template(
        scripts=scripts,
        dependencies=persisted.get("dependencies") or {},
        dev_dependencies=persisted.get("devDependencies") or {},
        overrides=constants.PackageJson.OVERRIDES,
    )


def initialize_package_json():
    """Render and write in .web the package.json file."""
    output_path = get_web_dir() / constants.PackageJson.PATH
    output_path.write_text(_compile_package_json())


def _compile_vite_config(config: Config):
    base = config.prepend_frontend_path("/")
    embed_plugin = get_embed_plugin()
    if embed_plugin and embed_plugin.embed_origin:
        # Cross-origin hosts must resolve assets against the bundle's server
        # rather than their own document.baseURI.
        base = embed_plugin.embed_origin.rstrip("/") + base
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
