"""This module provides utility functions to initialize the frontend skeleton."""

import json
import uuid
from pathlib import Path
from typing import Literal

from reflex_base import constants
from reflex_base.config import Config, get_config
from reflex_base.environment import environment
from reflex_base.plugins.embed import get_embed_plugin

from reflex.compiler import templates
from reflex.compiler.utils import write_file
from reflex.utils import console, net, path_ops
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


AgentsMdAction = Literal["managed", "bridge"]


def _plan_agents_md(
    agents_file: Path, claude_file: Path
) -> list[tuple[Path, AgentsMdAction]]:
    """Decide which files receive the managed section or the CLAUDE.md bridge.

    Claude Code reads CLAUDE.md rather than AGENTS.md, so: if CLAUDE.md is
    missing, AGENTS.md is managed and a bridge importing it is planned; if
    CLAUDE.md is the same file as AGENTS.md (symlink) or already imports it,
    only AGENTS.md is managed; otherwise CLAUDE.md is managed directly, along
    with AGENTS.md if it already exists.

    Args:
        agents_file: The AGENTS.md file in the app root.
        claude_file: The CLAUDE.md file in the app root.

    Returns:
        (file, action) pairs to apply in order.
    """
    if not claude_file.exists():
        plan: list[tuple[Path, AgentsMdAction]] = [(agents_file, "managed")]
        # A broken symlink gets no bridge; writing it would create the target.
        if not claude_file.is_symlink():
            plan.append((claude_file, "bridge"))
        return plan
    if (
        agents_file.exists() and claude_file.samefile(agents_file)
    ) or constants.AgentsMd.CLAUDE_IMPORT in claude_file.read_text():
        return [(agents_file, "managed")]
    if agents_file.exists():
        return [(agents_file, "managed"), (claude_file, "managed")]
    return [(claude_file, "managed")]


def _apply_agents_md_action(
    file: Path, action: AgentsMdAction, managed_agents_md_text: str
):
    """Apply a planned AGENTS.md action to a file.

    For "managed", the marker-wrapped section replaces the existing valid
    begin..end span; if the file has no valid pair (markers missing, unpaired,
    or out of order), stray markers are dropped and the section is prepended,
    preserving user content. For "bridge", the one-line import is written.

    Args:
        file: The file to write.
        action: The action to apply.
        managed_agents_md_text: The marker-wrapped canonical content.
    """
    begin, end = constants.AgentsMd.BEGIN_MARKER, constants.AgentsMd.END_MARKER
    if action == "bridge":
        content = f"{constants.AgentsMd.CLAUDE_IMPORT}\n"
    elif not file.exists():
        content = managed_agents_md_text + "\n"
    else:
        existing = file.read_text()
        begin_idx = existing.find(begin)
        end_idx = existing.find(end, begin_idx + len(begin)) if begin_idx != -1 else -1
        if end_idx != -1:
            content = (
                existing[:begin_idx]
                + managed_agents_md_text
                + existing[end_idx + len(end) :]
            )
        else:
            # No valid begin..end pair: drop stray markers and prepend the section.
            remainder = existing.replace(begin, "").replace(end, "").strip("\n")
            content = managed_agents_md_text + (
                f"\n\n{remainder}\n" if remainder else "\n"
            )
    console.debug(f"Creating {file}")
    file.write_text(content)


def initialize_agents_md(
    agents_file: Path = constants.AgentsMd.FILE,
    claude_file: Path = constants.AgentsMd.CLAUDE_FILE,
    url: str = constants.AgentsMd.CANONICAL_URL,
):
    """Write or refresh the Reflex-managed section of AGENTS.md and CLAUDE.md.

    Fetches the canonical content, then applies the plan from
    _plan_agents_md() to each file. A failed fetch is a warning, not an
    error, so init still succeeds offline.

    Args:
        agents_file: The AGENTS.md file to create or refresh in the app root.
        claude_file: The CLAUDE.md file bridging AGENTS.md for Claude Code.
        url: The canonical AGENTS.md to download.
    """
    plan = _plan_agents_md(agents_file, claude_file)

    import httpx

    console.debug(f"Fetching {url}")
    try:
        response = net.get(url, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as e:
        console.warn(f"Failed to fetch AGENTS.md from {url} due to {e}. Skipping.")
        return

    managed_agents_md_text = (
        f"{constants.AgentsMd.BEGIN_MARKER}\n"
        f"{response.text.strip()}\n"
        f"{constants.AgentsMd.END_MARKER}"
    )
    for file, action in plan:
        _apply_agents_md_action(file, action, managed_agents_md_text)


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
NO_PRUNE_LOCKFILE_NAMES: tuple[str, ...] = (constants.PackageJson.PATH,)


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


def _copy_if_exists(src: Path, dest: Path, prune: bool = True) -> bool:
    """Copy ``src`` to ``dest`` (creating ``dest`` parents as needed).

    Args:
        src: The source file. If absent, ``dest`` is removed when present.
        dest: The destination file.
        prune: Remove destination file that does not exist in source.

    Returns:
        True if ``dest``'s effective contents changed (created from absence,
        overwritten with different bytes, or removed because ``src`` is gone).
    """
    if not src.exists():
        if dest.exists() and prune:
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


def sync_root_lockfile_to_web(filename: str, prune: bool = True) -> bool:
    """Mirror a single persisted lockfile into ``.web``.

    Args:
        filename: The lockfile basename.
        prune: Remove destination file that does not exist in source.

    Returns:
        True if ``.web``'s copy was meaningfully changed (overwritten with
        different bytes or removed because the root copy is gone). Initial
        creation does not count as a meaningful change since no install
        cache could exist yet.
    """
    return _copy_if_exists(
        get_root_lockfile_path(filename), get_web_lockfile_path(filename), prune=prune
    )


def sync_root_lockfiles_to_web() -> bool:
    """Mirror every persisted lockfile into ``.web``.

    Returns:
        True if any ``.web`` lockfile was meaningfully changed.
    """
    # Materialize results so every lockfile is synced
    changed = [sync_root_lockfile_to_web(name) for name in LOCKFILE_NAMES] + [
        sync_root_lockfile_to_web(name, prune=False) for name in NO_PRUNE_LOCKFILE_NAMES
    ]
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
    for name in LOCKFILE_NAMES + NO_PRUNE_LOCKFILE_NAMES:
        sync_web_lockfile_to_root(name)


def _read_persisted_package_json() -> dict:
    """Read the persisted package.json from the app root.

    Returns:
        The parsed JSON object, or an empty dict if the file is missing,
        cannot be parsed, or is not a JSON object.
    """
    root_package_json_path = get_root_lockfile_path(constants.PackageJson.PATH)
    if not root_package_json_path.exists():
        return {}
    try:
        parsed = json.loads(root_package_json_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        console.warn(
            f"Failed to read {root_package_json_path}: {e}; starting with empty dependency lists."
        )
        return {}
    if not isinstance(parsed, dict):
        console.warn(
            f"Expected {root_package_json_path} to contain a JSON object, "
            f"got {type(parsed).__name__}; starting with empty dependency lists."
        )
        return {}
    return parsed


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
    sync_web_lockfiles_to_root()

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
    from constants. User-added ``overrides`` are kept, with the
    framework-owned entries refreshed on top. Any other persisted fields
    (e.g. ``packageManager``, ``engines``) are passed through unchanged.
    The framework-managed entries in ``constants.PackageJson.DEPENDENCIES``
    / ``DEV_DEPENDENCIES`` are added later at install time via ``bun add``
    so they pick up strict pins.

    Returns:
        Rendered package.json content as string.
    """
    persisted = _read_persisted_package_json()
    scripts = {
        **(persisted.pop("scripts", None) or {}),
        "dev": constants.PackageJson.Commands.DEV,
        "export": constants.PackageJson.Commands.EXPORT,
    }
    return templates.package_json_template(
        scripts=scripts,
        dependencies=persisted.pop("dependencies", None) or {},
        dev_dependencies=persisted.pop("devDependencies", None) or {},
        overrides={
            **(persisted.pop("overrides", None) or {}),
            **constants.PackageJson.OVERRIDES,
        },
        **persisted,
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
        minify=environment.VITE_MINIFY.get(),
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
        # Generate a uuid4 and persist its 128-bit integer form. Telemetry
        # re-encodes it as the canonical UUID string before sending.
        project_hash = uuid.uuid4().int
        console.debug(f"Setting project hash to {project_hash}.")

    # Write the hash and version to the reflex json file.
    reflex_json = {
        "version": constants.Reflex.VERSION,
        "project_hash": project_hash,
    }
    path_ops.update_json_file(get_web_dir() / constants.Reflex.JSON, reflex_json)
