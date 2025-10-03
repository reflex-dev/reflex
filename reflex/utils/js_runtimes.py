"""This module provides utilities for managing JavaScript runtimes like Node.js and Bun."""

import functools
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from packaging import version

from reflex import constants
from reflex.config import Config, get_config
from reflex.environment import environment
from reflex.utils import console, net, path_ops, processes
from reflex.utils.decorator import cached_procedure, once
from reflex.utils.exceptions import SystemPackageMissingError
from reflex.utils.prerequisites import get_web_dir, windows_check_onedrive_in_path


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
            console.error(
                f"Failed to run {executable_path} {version_arg} to get version. Return code: {result.returncode}. Standard error: {result.stderr!r}."
            )
            return None
        return version.parse(result.stdout.strip())
    except (FileNotFoundError, TypeError):
        return None
    except version.InvalidVersion as e:
        console.warn(
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


def prefer_npm_over_bun() -> bool:
    """Check if npm should be preferred over bun.

    Returns:
        If npm should be preferred over bun.
    """
    return npm_escape_hatch() or (
        constants.IS_WINDOWS and windows_check_onedrive_in_path()
    )


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
        console.warn(
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
    console.debug(f"Downloading {url}")
    try:
        response = net.get(url)
        response.raise_for_status()
    except httpx.HTTPError as e:
        console.error(
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
            console.info(
                "Skipping bun installation as REFLEX_USE_NPM is set. Using npm instead."
            )
            return
        console.error(
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
        console.debug("Skipping bun installation as it is already installed.")
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
        console.info(f"Using custom Bun path: {bun_path}")
        bun_version = get_bun_version(bun_path=bun_path)
        if bun_version is None:
            console.error(
                "Failed to obtain bun version. Make sure the specified bun path in your config is correct."
            )
            raise SystemExit(1)
        if bun_version < version.parse(constants.Bun.MIN_VERSION):
            console.warn(
                f"Reflex requires bun version {constants.Bun.MIN_VERSION} or higher to run, but the detected version is "
                f"{bun_version}. If you have specified a custom bun path in your config, make sure to provide one "
                f"that satisfies the minimum version requirement. You can upgrade bun by running [bold]bun upgrade[/bold]."
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
            console.error(f"Failed to find a valid package manager due to {e}.")
            raise SystemExit(1) from None

    if prefer_npm_over_bun() and not check_node_version():
        node_version = get_node_version()
        console.error(
            f"Reflex requires node version {constants.Node.MIN_VERSION} or higher to run, but the detected version is {node_version}",
        )
        raise SystemExit(1)


def remove_existing_bun_installation():
    """Remove existing bun installation."""
    console.debug("Removing existing bun installation.")
    if Path(get_config().bun_path).exists():
        path_ops.rm(constants.Bun.ROOT_PATH)


@cached_procedure(
    cache_file_path=lambda: get_web_dir() / "reflex.install_frontend_packages.cached",
    payload_fn=lambda packages, config: f"{sorted(packages)!r},{config.json()}",
)
def install_frontend_packages(packages: set[str], config: Config):
    """Installs the base and custom frontend packages.

    Args:
        packages: A list of package names to be installed.
        config: The config object.

    Example:
        >>> install_frontend_packages(["react", "react-dom"], get_config())
    """
    install_package_managers = get_nodejs_compatible_package_managers(
        raise_on_none=True
    )

    env = (
        {
            "NODE_TLS_REJECT_UNAUTHORIZED": "0",
        }
        if environment.SSL_NO_VERIFY.get()
        else {}
    )

    primary_package_manager = install_package_managers[0]
    fallbacks = install_package_managers[1:]

    run_package_manager = functools.partial(
        processes.run_process_with_fallbacks,
        fallbacks=fallbacks,
        analytics_enabled=True,
        cwd=get_web_dir(),
        shell=constants.IS_WINDOWS,
        env=env,
    )

    run_package_manager(
        [primary_package_manager, "install", "--legacy-peer-deps"],
        show_status_message="Installing base frontend packages",
    )

    development_deps: set[str] = set()
    for plugin in config.plugins:
        development_deps.update(plugin.get_frontend_development_dependencies())
        packages.update(plugin.get_frontend_dependencies())

    if development_deps:
        run_package_manager(
            [
                primary_package_manager,
                "add",
                "--legacy-peer-deps",
                "-d",
                *development_deps,
            ],
            show_status_message="Installing frontend development dependencies",
        )

    # Install custom packages defined in frontend_packages
    if packages:
        run_package_manager(
            [primary_package_manager, "add", "--legacy-peer-deps", *packages],
            show_status_message="Installing frontend packages from config and components",
        )
