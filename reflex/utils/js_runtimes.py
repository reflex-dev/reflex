"""This module provides utilities for managing JavaScript runtimes like Node.js and Bun."""

import functools
import json
import logging
import os
import tempfile
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path

from packaging import version
from reflex_base import constants
from reflex_base.config import Config, get_config
from reflex_base.environment import environment
from reflex_base.utils.decorator import cached_procedure, once
from reflex_base.utils.exceptions import SystemPackageMissingError
from reflex_base.utils.frontend_package import FrontendPackageMode, get_frontend_package
from rich.markup import escape

from reflex.utils import console, frontend_skeleton, net, path_ops, processes
from reflex.utils.prerequisites import get_web_dir, windows_check_onedrive_in_path

logger = logging.getLogger(__name__)


def check_node_version() -> bool:
    """Check the version of Node.js.

    Returns:
        Whether the version of Node.js is valid.
    """
    current_version = get_node_version()
    return current_version is not None and current_version >= version.parse(
        constants.Node.MIN_VERSION
    )


def _get_version_of_executable(
    executable_path: Path | None, version_arg: str = "--version"
) -> version.Version | None:
    """Get the version of an executable.

    Args:
        executable_path: The path to the executable.
        version_arg: The argument to pass to the executable to get its version.

    Returns:
        The version of the executable.
    """
    if executable_path is None:
        return None
    try:
        result = processes.new_process([executable_path, version_arg], run=True)
        if result.returncode != 0:
            logger.error(
                f"Failed to run {executable_path} {version_arg} to get version. Return code: {result.returncode}. Standard error: {result.stderr!r}."
            )
            return None
        return version.parse(result.stdout.strip())
    except (FileNotFoundError, TypeError):
        return None
    except version.InvalidVersion as e:
        logger.warning(
            f"The detected version of {executable_path} ({e.args[0]}) is not valid. Defaulting to None."
        )
        return None


@once
def get_node_version() -> version.Version | None:
    """Get the version of node.

    Returns:
        The version of node.
    """
    return _get_version_of_executable(path_ops.get_node_path())


def get_bun_version(bun_path: Path | None = None) -> version.Version | None:
    """Get the version of bun.

    Args:
        bun_path: The path to the bun executable.

    Returns:
        The version of bun.
    """
    return _get_version_of_executable(bun_path or path_ops.get_bun_path())


def npm_escape_hatch() -> bool:
    """If the user sets REFLEX_USE_NPM, prefer npm over bun.

    Returns:
        If the user has set REFLEX_USE_NPM.
    """
    return environment.REFLEX_USE_NPM.get()


def _persisted_lockfile_implies_npm() -> bool:
    """Whether the persisted lockfiles imply the project is npm-managed.

    A project is treated as npm-managed when ``reflex.lock/`` carries an
    npm lockfile but no bun lockfile, so committing only ``package-lock.json``
    is enough to opt in without setting ``REFLEX_USE_NPM=1``.

    Returns:
        Whether the persisted state implies npm.
    """
    root_dir = Path.cwd() / constants.Bun.ROOT_LOCKFILE_DIR
    return (root_dir / constants.Node.LOCKFILE_PATH).exists() and not (
        root_dir / constants.Bun.LOCKFILE_PATH
    ).exists()


def prefer_npm_over_bun() -> bool:
    """Check if npm should be preferred over bun.

    Order of precedence:
      1. Windows + OneDrive — always npm (bun is broken there).
      2. ``REFLEX_USE_NPM`` set — honor the explicit value.
      3. Persisted lockfile state — implicit npm if only a npm lock is
         present in ``reflex.lock/``.

    Returns:
        If npm should be preferred over bun.
    """
    if constants.IS_WINDOWS and windows_check_onedrive_in_path():
        return True
    explicit = environment.REFLEX_USE_NPM.getenv()
    if explicit is not None:
        return explicit
    return _persisted_lockfile_implies_npm()


def get_nodejs_compatible_package_managers(
    raise_on_none: bool = True,
) -> Sequence[str]:
    """Get the package manager executable for installation. Typically, bun is used for installation.

    Args:
        raise_on_none: Whether to raise an error if the package manager is not found.

    Returns:
        The path to the package manager.

    Raises:
        FileNotFoundError: If the package manager is not found and raise_on_none is True.
    """
    bun_package_manager = (
        str(bun_path) if (bun_path := path_ops.get_bun_path()) else None
    )

    npm_package_manager = (
        str(npm_path) if (npm_path := path_ops.get_npm_path()) else None
    )

    if prefer_npm_over_bun():
        package_managers = [npm_package_manager, bun_package_manager]
    else:
        package_managers = [bun_package_manager, npm_package_manager]

    package_managers = list(filter(None, package_managers))

    if not package_managers and raise_on_none:
        msg = "Bun or npm not found. You might need to rerun `reflex init` or install either."
        raise FileNotFoundError(msg)

    return package_managers


def is_outdated_nodejs_installed():
    """Check if the installed Node.js version is outdated.

    Returns:
        If the installed Node.js version is outdated.
    """
    current_version = get_node_version()
    if current_version is not None and current_version < version.parse(
        constants.Node.MIN_VERSION
    ):
        logger.warning(
            f"Your version ({current_version}) of Node.js is out of date. Upgrade to {constants.Node.MIN_VERSION} or higher."
        )
        return True
    return False


def get_js_package_executor(raise_on_none: bool = False) -> Sequence[Sequence[str]]:
    """Get the paths to package managers for running commands. Ordered by preference.
    This is currently identical to get_install_package_managers, but may change in the future.

    Args:
        raise_on_none: Whether to raise an error if no package managers is not found.

    Returns:
        The paths to the package managers as a list of lists, where each list is the command to run and its arguments.

    Raises:
        FileNotFoundError: If no package managers are found and raise_on_none is True.
    """
    bun_package_manager = (
        [str(bun_path)] + (["--bun"] if is_outdated_nodejs_installed() else [])
        if (bun_path := path_ops.get_bun_path())
        else None
    )

    npm_package_manager = (
        [str(npm_path)] if (npm_path := path_ops.get_npm_path()) else None
    )

    if prefer_npm_over_bun():
        package_managers = [npm_package_manager, bun_package_manager]
    else:
        package_managers = [bun_package_manager, npm_package_manager]

    package_managers = list(filter(None, package_managers))

    if not package_managers and raise_on_none:
        msg = "Bun or npm not found. You might need to rerun `reflex init` or install either."
        raise FileNotFoundError(msg)

    return package_managers


def download_and_run(url: str, *args, show_status: bool = False, **env):
    """Download and run a script.

    Args:
        url: The url of the script.
        args: The arguments to pass to the script.
        show_status: Whether to show the status of the script.
        env: The environment variables to use.

    Raises:
        SystemExit: If the script fails to download.
    """
    import httpx

    # Download the script
    logger.debug(f"Downloading {url}")
    try:
        response = net.get(url)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(
            f"Failed to download bun install script. You can install or update bun manually from https://bun.com \n{e}"
        )
        raise SystemExit(1) from None

    # Save the script to a temporary file.
    with tempfile.NamedTemporaryFile() as tempfile_file:
        script = Path(tempfile_file.name)

        script.write_text(response.text)

        # Run the script.
        env = {**os.environ, **env}
        process = processes.new_process(["bash", str(script), *args], env=env)
        show = processes.show_status if show_status else processes.show_logs
        show(f"Installing {url}", process)


def install_bun():
    """Install bun onto the user's system.

    Raises:
        SystemPackageMissingError: If "unzip" is missing.
        SystemExit: If REFLEX_USE_NPM is set but Node.js is not installed.
    """
    if npm_escape_hatch():
        if get_node_version() is not None:
            logger.info(
                "Skipping bun installation as REFLEX_USE_NPM is set. Using npm instead."
            )
            return
        logger.error(
            "REFLEX_USE_NPM is set, but Node.js is not installed. Please install Node.js to use npm."
        )
        raise SystemExit(1)

    bun_path = path_ops.get_bun_path()

    # Skip if bun is already installed.
    if (
        bun_path
        and (current_version := get_bun_version(bun_path=bun_path))
        and current_version >= version.parse(constants.Bun.MIN_VERSION)
    ):
        logger.debug("Skipping bun installation as it is already installed.")
        return

    if bun_path and path_ops.use_system_bun():
        validate_bun(bun_path=bun_path)
        return

    if constants.IS_WINDOWS:
        processes.new_process(
            [
                "powershell",
                "-c",
                f"irm {constants.Bun.WINDOWS_INSTALL_URL}|iex",
            ],
            env={
                "BUN_INSTALL": str(constants.Bun.ROOT_PATH),
                "BUN_VERSION": constants.Bun.VERSION,
            },
            shell=True,
            run=True,
            show_logs=console.is_debug(),
        )
    else:
        if path_ops.which("unzip") is None:
            msg = "unzip"
            raise SystemPackageMissingError(msg)

        # Run the bun install script.
        download_and_run(
            constants.Bun.INSTALL_URL,
            f"bun-v{constants.Bun.VERSION}",
            BUN_INSTALL=str(constants.Bun.ROOT_PATH),
            BUN_VERSION=str(constants.Bun.VERSION),
        )


def validate_bun(bun_path: Path | None = None):
    """Validate bun if a custom bun path is specified to ensure the bun version meets requirements.

    Args:
        bun_path: The path to the bun executable. If None, the default bun path is used.

    Raises:
        SystemExit: If custom specified bun does not exist or does not meet requirements.
    """
    bun_path = bun_path or path_ops.get_bun_path()

    if bun_path is None:
        return

    if not path_ops.samefile(bun_path, constants.Bun.DEFAULT_PATH):
        logger.info(f"Using custom Bun path: {bun_path}")
        bun_version = get_bun_version(bun_path=bun_path)
        if bun_version is None:
            logger.error(
                "Failed to obtain bun version. Make sure the specified bun path in your config is correct."
            )
            raise SystemExit(1)
        if bun_version < version.parse(constants.Bun.MIN_VERSION):
            logger.warning(
                f"Reflex requires bun version {constants.Bun.MIN_VERSION} or higher to run, but the detected version is "
                f"{bun_version}. If you have specified a custom bun path in your config, make sure to provide one "
                f"that satisfies the minimum version requirement. You can upgrade bun by running [bold]bun upgrade[/bold].",
                extra={"rich": True},
            )


def validate_frontend_dependencies(init: bool = True):
    """Validate frontend dependencies to ensure they meet requirements.

    Args:
        init: whether running `reflex init`

    Raises:
        SystemExit: If the package manager is invalid.
    """
    if not init:
        try:
            get_js_package_executor(raise_on_none=True)
        except FileNotFoundError as e:
            logger.error(f"Failed to find a valid package manager due to {e}.")
            raise SystemExit(1) from None

    if prefer_npm_over_bun() and not check_node_version():
        node_version = get_node_version()
        logger.error(
            f"Reflex requires node version {constants.Node.MIN_VERSION} or higher to run, but the detected version is {node_version}",
        )
        raise SystemExit(1)


def remove_existing_bun_installation():
    """Remove existing bun installation."""
    logger.debug("Removing existing bun installation.")
    if Path(get_config().bun_path).exists():
        path_ops.rm(constants.Bun.ROOT_PATH)


def _frontend_packages_cache_path() -> Path:
    """Get the cache file path for frontend package installs.

    Returns:
        The cache file path for frontend package installs.
    """
    return get_web_dir() / "reflex.install_frontend_packages.cached"


def _sync_root_lockfiles_for_frontend_install():
    """Sync persisted lockfiles into .web and invalidate the install cache when needed."""
    if frontend_skeleton.sync_root_lockfiles_to_web():
        cache_file = _frontend_packages_cache_path()
        if cache_file.exists():
            path_ops.rm(cache_file)


def _extract_package_name(package_spec: str) -> str:
    """Strip any version suffix from a ``bun add``-style spec.

    Handles plain (``react``), pinned (``react@1.2.3``), scoped
    (``@scope/pkg``), and pinned-scoped (``@scope/pkg@1.2.3``) forms.

    Args:
        package_spec: The spec to parse.

    Returns:
        The bare package name.
    """
    if package_spec.startswith("@"):
        idx = package_spec.find("@", 1)
        return package_spec if idx == -1 else package_spec[:idx]
    return package_spec.split("@", 1)[0]


def _existing_web_package_sections() -> tuple[set[str], set[str]]:
    """Return packages currently declared in .web/package.json by section.

    Reads ``.web/package.json``'s ``dependencies`` and ``devDependencies``
    separately so callers can detect packages declared in the wrong
    section. ``overrides`` are excluded because they reference transitive
    deps.

    Returns:
        A tuple ``(deps, dev_deps)`` of bare package names. Both empty if
        the file is missing or unreadable.
    """
    web_pkg_json_path = frontend_skeleton.get_web_lockfile_path(
        constants.PackageJson.PATH
    )
    if not web_pkg_json_path.exists():
        return set(), set()
    try:
        data = json.loads(web_pkg_json_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(
            f"Failed to read {web_pkg_json_path}: {e}; skipping existing package check."
        )
        return set(), set()
    return (
        set(data.get("dependencies") or {}),
        set(data.get("devDependencies") or {}),
    )


def _is_bun_package_manager(package_manager: str) -> bool:
    """Whether the given package manager path refers to bun.

    bun-specific CLI flags (``--frozen-lockfile``, ``--only-missing``) are
    not understood by npm and will fail outright on upcoming npm versions
    that reject unknown options, so callers gate those flags on this check.

    Args:
        package_manager: Path or bare name of the package manager executable.

    Returns:
        Whether the executable is bun.
    """
    return Path(package_manager).stem.lower() == "bun"


def _run_initial_install(
    primary_package_manager: str, env: dict, frozen_lockfile: bool
) -> None:
    """Run the initial install with a friendly recovery hint.

    When ``frozen_lockfile`` is set, bun reports ``error: lockfile had
    changes, but lockfile is frozen`` if the persisted lockfile cannot
    satisfy the recovered package.json. When that happens, point the user at
    ``reflex.lock/package.json`` so they can delete it and let Reflex
    regenerate the dep set from scratch on the next run.

    Args:
        primary_package_manager: Path to the package manager executable.
        env: Extra environment variables for the subprocess.
        frozen_lockfile: Whether to enforce the lockfile, erroring when it is
            out of sync with package.json instead of updating it in place.

    Raises:
        SystemExit: If the install fails. The exit message tells the user
            how to recover from a frozen-lockfile mismatch when applicable.
    """
    install_args = [
        primary_package_manager,
        "install",
        "--legacy-peer-deps",
    ]
    if frozen_lockfile and _is_bun_package_manager(primary_package_manager):
        # ``--frozen-lockfile`` is bun-only; npm ignores it today and the
        # next major rejects unknown flags outright.
        install_args.append("--frozen-lockfile")
    args = processes.get_command_with_loglevel(install_args)
    process = processes.new_process(
        args,
        cwd=get_web_dir(),
        shell=constants.IS_WINDOWS,
        env=env,
    )
    logs = processes.show_status(
        "Installing base frontend packages",
        process,
        suppress_errors=True,
    )
    if process.returncode == 0:
        return

    if any("lockfile had changes, but lockfile is frozen" in line for line in logs):
        root_dir = Path.cwd() / constants.Bun.ROOT_LOCKFILE_DIR
        logger.error(
            "The persisted lockfile is out of sync with the recovered "
            f"package.json. Delete the [bold]{escape(str(root_dir))}[/bold] directory "
            "and rerun so Reflex regenerates it from scratch.",
            extra={"rich": True},
        )
        raise SystemExit(1)

    # Replay captured logs so the user can diagnose other failures (mirrors
    # show_status's default error path, which we suppressed above).
    for line in logs:
        logger.error(line, extra={"end": ""})
    logger.error(
        "\nRun with [bold]--loglevel debug[/bold] for the full log.",
        extra={"rich": True},
    )
    raise SystemExit(1)


def _has_version_specifier(package_spec: str) -> bool:
    """Check whether a package spec already includes a version specifier.

    Treats a package as pinned if it contains an ``@`` after the first
    character (so scoped packages like ``@scope/pkg`` are unpinned, while
    ``@scope/pkg@1.2.3`` is pinned).

    Args:
        package_spec: The package spec to inspect.

    Returns:
        Whether the spec carries a version specifier.
    """
    return "@" in package_spec[1:]


def _split_by_version_specifier(
    packages: set[str],
) -> tuple[set[str], set[str]]:
    """Partition packages into pinned and unpinned sets.

    Args:
        packages: Package specs to partition.

    Returns:
        A tuple ``(pinned, unpinned)`` of disjoint package sets.
    """
    pinned: set[str] = set()
    unpinned: set[str] = set()
    for package in packages:
        if _has_version_specifier(package):
            pinned.add(package)
        else:
            unpinned.add(package)
    return pinned, unpinned


def _pinned_specs_from_manifest(deps: dict[str, str]) -> set[str]:
    """Render manifest-style dep dicts as ``name@version`` add args.

    Args:
        deps: Mapping of package name to version string.

    Returns:
        Set of ``name@version`` specs.
    """
    return {f"{name}@{version}" for name, version in deps.items()}


def _frontend_packages_cache_payload(
    packages: set[str],
    config: Config,
    install_package_managers: Sequence[str],
) -> str:
    """Cache fingerprint for frontend package installs.

    Args:
        packages: Custom packages requested by the caller.
        config: The active Reflex config.
        install_package_managers: The package manager paths in priority order.

    Returns:
        Stable fingerprint string for the cached procedure.
    """
    frontend_package = get_frontend_package()
    return (
        f"{sorted(packages)!r},{config.json()},{list(install_package_managers)!r},"
        f"{frontend_package.mode.value},{frontend_package.path!s},"
        f"{frontend_package.name},{frontend_package.version},"
        f"{sorted(frontend_package.dependencies.items())!r},"
        f"{sorted(frontend_package.dev_dependencies.items())!r},"
        f"{metadata.version('reflex-base')},"
        f"{sorted(constants.PackageJson.OVERRIDES.items())!r}"
    )


@cached_procedure(
    cache_file_path=_frontend_packages_cache_path,
    payload_fn=_frontend_packages_cache_payload,
)
def _install_frontend_packages(
    packages: set[str],
    config: Config,
    install_package_managers: Sequence[str],
):
    """Installs the bundled frontend package and custom frontend packages.

    Resolution rules:
      * The bundled frontend package (``@reflex-dev/reflex-base``) is
        referenced by a Python-written ``file:``/``link:`` entry. When the
        persisted entry differs from the current install's, the entry is
        rewritten after the frozen initial install when the old target still
        resolves (upgrade in place), or before it (with the frozen install
        relaxed) when it no longer does.
      * The runtime framework deps (react, react-router, ...) resolve
        transitively through that package, so user ``overrides`` control
        their versions. In SOURCE mode (editable installs, where the
        symlinked directory's deps are not auto-installed) they are also
        added top-level with the manifest's pins.
      * The app toolchain comes from the manifest's ``devDependencies`` and
        is added with strict pins (a dependency's devDependencies are never
        installed by package managers).
      * Plugin/custom packages with explicit version specifiers are added
        with strict pins.
      * Plugin/custom packages without version specifiers are skipped
        entirely if package.json already declares them in the correct
        section, so previously resolved pins are preserved across runs
        without relying on package-manager-specific flags. Otherwise they
        are added without a version so the manager picks one.
      * Packages declared in the wrong section (e.g. a regular dep
        listed under ``devDependencies``) are removed first and re-added
        so they land in the section the framework/plugin/import-graph
        actually intends. Framework deps that older Reflex versions pinned
        at the top level fall out through the same stale sweep.

    Args:
        packages: Custom packages requested by the caller (from
            ``Config.frontend_packages`` and inferred component imports).
        config: The active Reflex config.
        install_package_managers: The package manager paths in priority
            order (primary plus fallbacks).

    Example:
        >>> install_frontend_packages({"react", "react-dom"}, get_config())
    """
    env = (
        {
            "NODE_TLS_REJECT_UNAUTHORIZED": "0",
        }
        if environment.SSL_NO_VERIFY.get()
        else {}
    )

    primary_package_manager = install_package_managers[0]

    # No fallback to a different package manager: switching mid-flow could
    # bypass the persisted lockfile (e.g. on a package-integrity failure
    # the alternate manager would happily fetch a new version), defeating
    # the whole point of pinning. A failure here must surface as a failure.
    run_package_manager = functools.partial(
        processes.run_process_with_fallbacks,
        fallbacks=None,
        analytics_enabled=True,
        cwd=get_web_dir(),
        shell=constants.IS_WINDOWS,
        env=env,
    )

    frontend_package = get_frontend_package()
    frontend_skeleton.materialize_frontend_tarball()
    desired_spec = frontend_skeleton.get_frontend_package_spec(primary_package_manager)
    current_spec = frontend_skeleton.current_frontend_package_entry()
    frontend_entry_unchanged = current_spec == desired_spec
    entry_rewritten_before_install = False
    if (
        not frontend_entry_unchanged
        and not frontend_skeleton.frontend_package_entry_resolvable(current_spec)
    ):
        # The persisted entry points at nothing installable (e.g. a fresh
        # checkout after a Reflex upgrade whose tarball isn't in .web), so
        # the restored pair cannot install anyway: rewrite before the
        # initial install and let it resolve unfrozen.
        entry_rewritten_before_install = frontend_skeleton.set_frontend_package_entry(
            desired_spec
        )

    # Resolve plugin-contributed deps up front so we know the full needed
    # set before deciding which entries in package.json are stale.
    development_deps: set[str] = set()
    for plugin in config.plugins:
        development_deps.update(plugin.get_frontend_development_dependencies())
        packages.update(plugin.get_frontend_dependencies())

    manifest_dependencies = (
        frontend_package.dependencies
        if frontend_package.mode is FrontendPackageMode.SOURCE
        else {}
    )
    wanted_dep_names = (
        {frontend_package.name}
        | set(manifest_dependencies)
        | {_extract_package_name(p) for p in packages}
    )
    # If the same package is requested as both a regular and a development
    # dependency (e.g. two plugins disagree on the section), prefer the
    # regular-dep section. This keeps the placement deterministic instead
    # of depending on the order the package manager processes the two
    # add calls.
    wanted_dev_dep_names = (
        set(frontend_package.dev_dependencies)
        | {_extract_package_name(p) for p in development_deps}
    ) - wanted_dep_names
    needed_names = wanted_dep_names | wanted_dev_dep_names

    existing_deps, existing_dev_deps = _existing_web_package_sections()
    existing_names = existing_deps | existing_dev_deps

    # Drop deps lingering in package.json that no component, plugin, or
    # framework manifest calls for anymore, plus any package declared in
    # the wrong section. bun and npm both update the existing entry
    # in-place on a re-add and won't move it across sections, so misplaced
    # entries must be removed first to land in the correct one.
    stale_packages = existing_names - needed_names
    misplaced_in_dev = (wanted_dep_names & existing_dev_deps) - existing_deps
    misplaced_in_deps = (wanted_dev_dep_names & existing_deps) - existing_dev_deps
    to_remove = stale_packages | misplaced_in_dev | misplaced_in_deps
    if to_remove:
        run_package_manager(
            [
                primary_package_manager,
                "remove",
                "--legacy-peer-deps",
                *sorted(to_remove),
            ],
            show_status_message="Removing unused frontend packages",
        )

    # Install against the recovered lockfile so its pins are honored
    # before any further mutation. The frozen check is relaxed when the
    # frontend package entry had to be rewritten upfront, since the pair is
    # then knowingly out of sync with the persisted lockfile.
    initial_install_ran = False
    if any(
        frontend_skeleton.get_web_lockfile_path(name).exists()
        for name in frontend_skeleton.LOCKFILE_NAMES
    ):
        if config.frozen_lockfile and entry_rewritten_before_install:
            logger.warning(
                "The Reflex frontend package reference changed to "
                f"{desired_spec}; the persisted lockfile will be updated."
            )
        _run_initial_install(
            primary_package_manager,
            env,
            config.frozen_lockfile and not entry_rewritten_before_install,
        )
        initial_install_ran = True

    # Framework overrides are withheld while the persisted package.json is
    # restored so the frozen install above sees exactly the file that produced
    # the persisted lockfile. Merge them now, before any resolution happens.
    overrides_changed = frontend_skeleton.update_package_json_overrides()

    # Upgrade in place: the old tarball satisfied the frozen install above;
    # point the entry at the current one now so the adds below resolve it.
    entry_rewritten_after_install = False
    if not frontend_entry_unchanged and not entry_rewritten_before_install:
        entry_rewritten_after_install = frontend_skeleton.set_frontend_package_entry(
            desired_spec
        )

    pinned_packages, unpinned_packages = _split_by_version_specifier(packages)
    pinned_dev_deps, unpinned_dev_deps = _split_by_version_specifier(development_deps)

    # Skip unpinned entries that already appear in the correct section so
    # the package manager doesn't churn the previously resolved version.
    # Misplaced entries fall through here and get re-added (after the
    # remove step above) into the right section. This replaces bun's
    # ``--only-missing`` flag with package-manager-agnostic logic that
    # also works on npm.
    new_unpinned_packages = unpinned_packages - existing_deps
    new_unpinned_dev_deps = unpinned_dev_deps - existing_dev_deps

    deps_to_add = (
        _pinned_specs_from_manifest(manifest_dependencies)
        | pinned_packages
        | new_unpinned_packages
    )
    deps_names_to_add = {_extract_package_name(p) for p in deps_to_add}
    dev_deps_to_add = {
        spec
        for spec in (
            _pinned_specs_from_manifest(frontend_package.dev_dependencies)
            | pinned_dev_deps
            | new_unpinned_dev_deps
        )
        if _extract_package_name(spec) not in deps_names_to_add
    }

    # Add dev dependencies first so that any subsequent regular-dep add
    # for an overlapping name lands in ``dependencies`` regardless of
    # whether the package manager moves entries between sections.
    if dev_deps_to_add:
        run_package_manager(
            [
                primary_package_manager,
                "add",
                "--legacy-peer-deps",
                "-d",
                *dev_deps_to_add,
            ],
            show_status_message="Installing frontend development dependencies",
        )
    if deps_to_add:
        run_package_manager(
            [primary_package_manager, "add", "--legacy-peer-deps", *deps_to_add],
            show_status_message="Installing frontend packages",
        )

    # An entry rewritten before the (unfrozen) initial install was already
    # resolved by it; anything later still needs to reach the lockfile.
    entry_needs_resolution = entry_rewritten_after_install or (
        entry_rewritten_before_install and not initial_install_ran
    )
    if (overrides_changed or entry_needs_resolution) and not (
        dev_deps_to_add or deps_to_add
    ):
        # Newly merged overrides or a rewritten frontend entry with no add to
        # carry them into the lockfile: resolve them now so the persisted
        # pair stays frozen-install ready.
        run_package_manager(
            [primary_package_manager, "install", "--legacy-peer-deps"],
            show_status_message="Applying frontend package changes",
        )

    frontend_skeleton.prune_stale_frontend_tarballs()


def install_frontend_packages(packages: set[str], config: Config):
    """Install frontend packages while respecting the canonical root bun.lock."""
    for env_var in ("REACT_VERSION", "REACT_ROUTER_VERSION"):
        if os.getenv(env_var):
            console.deprecate(
                feature_name=f"The {env_var} environment variable",
                reason=(
                    "it no longer has any effect: frontend framework versions "
                    "are declared by the bundled @reflex-dev/reflex-base npm "
                    "package. Pin versions via 'overrides' in "
                    "reflex.lock/package.json instead"
                ),
                deprecation_version="0.9.9",
                removal_version="1.0",
            )
    install_package_managers = tuple(
        get_nodejs_compatible_package_managers(raise_on_none=True)
    )
    _sync_root_lockfiles_for_frontend_install()
    _install_frontend_packages(set(packages), config, install_package_managers)
    frontend_skeleton.sync_web_lockfiles_to_root()
