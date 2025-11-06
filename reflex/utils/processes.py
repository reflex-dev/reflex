"""Process operations."""

from __future__ import annotations

import collections
import contextlib
import os
import signal
import socket
import subprocess
import sys
from collections.abc import Callable, Generator, Sequence
from concurrent import futures
from contextlib import closing
from pathlib import Path
from typing import Any, Literal, overload

import rich.markup
from rich.progress import Progress

from reflex import constants
from reflex.config import get_config
from reflex.environment import environment
from reflex.utils import console, path_ops, prerequisites
from reflex.utils.registry import get_npm_registry


def kill(pid: int):
    """Kill a process.

    Args:
        pid: The process ID.
    """
    os.kill(pid, signal.SIGTERM)


def get_num_workers() -> int:
    """Get the number of backend worker processes.

    Raises:
        SystemExit: If unable to connect to Redis.

    Returns:
        The number of backend worker processes.
    """
    if get_config().transport == "polling":
        return 1

    if (redis_client := prerequisites.get_redis_sync()) is None:
        return 1

    from redis.exceptions import RedisError

    try:
        redis_client.ping()
    except RedisError as re:
        console.error(f"Unable to connect to Redis: {re}")
        raise SystemExit(1) from None
    return (os.cpu_count() or 1) * 2 + 1


def _can_bind_at_port(
    address_family: socket.AddressFamily | int, address: str, port: int
) -> bool:
    """Check if a given address and port are responsive.

    Args:
        address_family: The address family (e.g., socket.AF_INET or socket.AF_INET6).
        address: The address to check.
        port: The port to check.

    Returns:
        Whether the address and port are responsive.
    """
    try:
        with closing(socket.socket(address_family, socket.SOCK_STREAM)) as sock:
            if sys.platform != "win32":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((address, port))
    except (OverflowError, PermissionError, OSError) as e:
        console.warn(f"Unable to bind to {address}:{port} due to: {e}.")
        return False
    return True


def _can_bind_at_any_port(address_family: socket.AddressFamily | int) -> bool:
    """Check if any port is available for binding.

    Args:
        address_family: The address family (e.g., socket.AF_INET or socket.AF_INET6).

    Returns:
        Whether any port is available for binding.
    """
    try:
        with closing(socket.socket(address_family, socket.SOCK_STREAM)) as sock:
            sock.bind(("", 0))  # Bind to any available port
            return True
    except (OverflowError, PermissionError, OSError) as e:
        console.debug(f"Unable to bind to any port for {address_family}: {e}")
        return False


def is_process_on_port(
    port: int,
    address_families: Sequence[socket.AddressFamily | int] = (
        socket.AF_INET,
        socket.AF_INET6,
    ),
) -> bool:
    """Check if a process is running on the given port.

    Args:
        port: The port.
        address_families: The address families to check (default: IPv4 and IPv6).

    Returns:
        Whether a process is running on the given port.
    """
    return any(not _can_bind_at_port(family, "", port) for family in address_families)


MAXIMUM_PORT = 2**16 - 1


def handle_port(service_name: str, port: int, auto_increment: bool) -> int:
    """Change port if the specified port is in use and is not explicitly specified as a CLI arg or config arg.
    Otherwise tell the user the port is in use and exit the app.

    Args:
        service_name: The frontend or backend.
        port: The provided port.
        auto_increment: Whether to automatically increment the port.

    Returns:
        The port to run the service on.

    Raises:
        SystemExit:when the port is in use.
    """
    console.debug(f"Checking if {service_name.capitalize()} port: {port} is in use.")

    families = [
        address_family
        for address_family in (socket.AF_INET, socket.AF_INET6)
        if _can_bind_at_any_port(address_family)
    ]

    if not families:
        console.error(
            f"Unable to bind to any port for {service_name}. "
            "Please check your network configuration."
        )
        raise SystemExit(1)

    console.debug(
        f"Checking if {service_name.capitalize()} port: {port} is in use for families: {families}."
    )

    if not is_process_on_port(port, families):
        console.debug(f"{service_name.capitalize()} port: {port} is not in use.")
        return port

    if auto_increment:
        for new_port in range(port + 1, MAXIMUM_PORT + 1):
            if not is_process_on_port(new_port, families):
                console.info(
                    f"The {service_name} will run on port [bold underline]{new_port}[/bold underline]."
                )
                return new_port
            console.debug(
                f"{service_name.capitalize()} port: {new_port} is already in use."
            )

        # If we reach here, it means we couldn't find an available port.
        console.error(f"Unable to find an available port for {service_name}")
    else:
        console.error(f"{service_name.capitalize()} port: {port} is already in use.")

    raise SystemExit(1)


@overload
def new_process(
    args: str | list[str] | list[str | None] | list[str | Path | None],
    run: Literal[False] = False,
    show_logs: bool = False,
    **kwargs,
) -> subprocess.Popen[str]: ...


@overload
def new_process(
    args: str | list[str] | list[str | None] | list[str | Path | None],
    run: Literal[True],
    show_logs: bool = False,
    **kwargs,
) -> subprocess.CompletedProcess[str]: ...


def new_process(
    args: str | list[str] | list[str | None] | list[str | Path | None],
    run: bool = False,
    show_logs: bool = False,
    **kwargs,
) -> subprocess.CompletedProcess[str] | subprocess.Popen[str]:
    """Wrapper over subprocess.Popen to unify the launch of child processes.

    Args:
        args: A string, or a sequence of program arguments.
        run: Whether to run the process to completion.
        show_logs: Whether to show the logs of the process.
        **kwargs: Kwargs to override default wrap values to pass to subprocess.Popen as arguments.

    Returns:
        Execute a child program in a new process.

    Raises:
        SystemExit: When attempting to run a command with a None value.
    """
    # Check for invalid command first.
    non_empty_args = list(filter(None, args)) if isinstance(args, list) else [args]
    if isinstance(args, list) and len(non_empty_args) != len(args):
        console.error(f"Invalid command: {args}")
        raise SystemExit(1)

    path_env: str = os.environ.get("PATH", "")

    # Add node_bin_path to the PATH environment variable.
    if not environment.REFLEX_BACKEND_ONLY.get():
        node_bin_path = path_ops.get_node_bin_path()
        if node_bin_path:
            path_env = os.pathsep.join([str(node_bin_path), path_env])

    env: dict[str, str] = {
        **os.environ,
        "PATH": path_env,
        **kwargs.pop("env", {}),
    }

    kwargs = {
        "env": env,
        "stderr": None if show_logs else subprocess.STDOUT,
        "stdout": None if show_logs else subprocess.PIPE,
        "universal_newlines": True,
        "encoding": "UTF-8",
        "errors": "replace",  # Avoid UnicodeDecodeError in unknown command output
        **kwargs,
    }
    console.debug(f"Running command: {non_empty_args}")

    def subprocess_p_open(args: subprocess._CMD, **kwargs):
        return subprocess.Popen(args, **kwargs)

    fn: Callable[..., subprocess.CompletedProcess[str] | subprocess.Popen[str]] = (
        subprocess.run if run else subprocess_p_open
    )
    return fn(non_empty_args, **kwargs)


@contextlib.contextmanager
def run_concurrently_context(
    *fns: Callable[..., Any] | tuple[Callable[..., Any], ...],
) -> Generator[list[futures.Future], None, None]:
    """Run functions concurrently in a thread pool.

    Args:
        *fns: The functions to run.

    Yields:
        The futures for the functions.
    """
    # If no functions are provided, yield an empty list and return.
    if not fns:
        yield []
        return

    # Convert the functions to tuples.
    fns = tuple(fn if isinstance(fn, tuple) else (fn,) for fn in fns)

    # Run the functions concurrently.
    executor = None
    try:
        executor = futures.ThreadPoolExecutor(max_workers=len(fns))
        # Submit the tasks.
        tasks = [executor.submit(*fn) for fn in fns]

        # Yield control back to the main thread while tasks are running.
        yield tasks

        # Get the results in the order completed to check any exceptions.
        for task in futures.as_completed(tasks):
            # if task throws something, we let it bubble up immediately
            task.result()
    finally:
        # Shutdown the executor
        if executor:
            executor.shutdown(wait=False)


def run_concurrently(*fns: Callable | tuple) -> None:
    """Run functions concurrently in a thread pool.

    Args:
        *fns: The functions to run.
    """
    with run_concurrently_context(*fns):
        pass


def stream_logs(
    message: str,
    process: subprocess.Popen,
    progress: Progress | None = None,
    suppress_errors: bool = False,
    analytics_enabled: bool = False,
    prior_logs: tuple[tuple[str, ...], ...] = (),
):
    """Stream the logs for a process.

    Args:
        message: The message to display.
        process: The process.
        progress: The ongoing progress bar if one is being used.
        suppress_errors: If True, do not exit if errors are encountered (for fallback).
        analytics_enabled: Whether analytics are enabled for this command.
        prior_logs: The logs of the prior processes that have been run.

    Yields:
        The lines of the process output.

    Raises:
        SystemExit: If the process failed.
        ValueError: If the process stdout pipe is closed, but the process remains running.
    """
    from reflex.utils import telemetry

    # Store the tail of the logs.
    logs = collections.deque(maxlen=512)
    with process:
        console.debug(message, progress=progress)
        if process.stdout is None:
            return
        try:
            for line in process.stdout:
                console.debug(rich.markup.escape(line), end="", progress=progress)
                logs.append(line)
                yield line
        except ValueError:
            # The stream we were reading has been closed,
            if process.poll() is None:
                # But if the process is still running that is weird.
                raise
            # If the process exited, break out of the loop for post processing.

    # Check if the process failed (not printing the logs for SIGINT).

    # Windows uvicorn bug
    # https://github.com/reflex-dev/reflex/issues/2335
    # 130 is the exit code that react router returns when it is interrupted by a signal.
    accepted_return_codes = [0, -2, 15, 130] if constants.IS_WINDOWS else [0, -2, 130]
    if process.returncode not in accepted_return_codes and not suppress_errors:
        console.error(f"{message} failed with exit code {process.returncode}")
        if "".join(logs).count("CERT_HAS_EXPIRED") > 0:
            bunfig = prerequisites.get_web_dir() / constants.Bun.CONFIG_PATH
            npm_registry_line = next(
                (
                    line
                    for line in bunfig.read_text().splitlines()
                    if line.startswith("registry")
                ),
                None,
            )
            if not npm_registry_line or "=" not in npm_registry_line:
                npm_registry = get_npm_registry()
            else:
                npm_registry = npm_registry_line.split("=")[1].strip()
            console.error(
                f"Failed to fetch securely from [bold]{npm_registry}[/bold]. Please check your network connection. "
                "You can try running the command again or changing the registry by setting the "
                "NPM_CONFIG_REGISTRY environment variable. If TLS is the issue, and you know what "
                "you are doing, you can disable it by setting the SSL_NO_VERIFY environment variable."
            )
            raise SystemExit(1)
        for set_of_logs in (*prior_logs, tuple(logs)):
            for line in set_of_logs:
                console.error(line, end="")
            console.error("\n\n")
        if analytics_enabled:
            telemetry.send("error", context=message)
        console.error("Run with [bold]--loglevel debug [/bold] for the full log.")
        raise SystemExit(1)


def show_logs(message: str, process: subprocess.Popen):
    """Show the logs for a process.

    Args:
        message: The message to display.
        process: The process.
    """
    for _ in stream_logs(message, process):
        pass


def show_status(
    message: str,
    process: subprocess.Popen,
    suppress_errors: bool = False,
    analytics_enabled: bool = False,
    prior_logs: tuple[tuple[str, ...], ...] = (),
) -> list[str]:
    """Show the status of a process.

    Args:
        message: The initial message to display.
        process: The process.
        suppress_errors: If True, do not exit if errors are encountered (for fallback).
        analytics_enabled: Whether analytics are enabled for this command.
        prior_logs: The logs of the prior processes that have been run.

    Returns:
        The lines of the process output.
    """
    lines = []

    with console.status(message) as status:
        for line in stream_logs(
            message,
            process,
            suppress_errors=suppress_errors,
            analytics_enabled=analytics_enabled,
            prior_logs=prior_logs,
        ):
            status.update(f"{message} {line}")
            lines.append(line)
        return lines


def show_progress(message: str, process: subprocess.Popen, checkpoints: list[str]):
    """Show a progress bar for a process.

    Args:
        message: The message to display.
        process: The process.
        checkpoints: The checkpoints to advance the progress bar.
    """
    # Iterate over the process output.
    with console.progress() as progress:
        task = progress.add_task(f"{message}: ", total=len(checkpoints))
        for line in stream_logs(message, process, progress=progress):
            # Check for special strings and update the progress bar.
            special_string = checkpoints[0]
            if special_string in line:
                progress.update(task, advance=1)
                checkpoints.pop(0)
            if not checkpoints:
                break


def atexit_handler():
    """Display a custom message with the current time when exiting an app."""
    console.log("Reflex app stopped.")


def get_command_with_loglevel(command: list[str]) -> list[str]:
    """Add the right loglevel flag to the designated command.
     npm uses --loglevel <level>, Bun doesn't use the --loglevel flag and
     runs in debug mode by default.

    Args:
        command:The command to add loglevel flag.

    Returns:
        The updated command list
    """
    npm_path = path_ops.get_npm_path()
    npm_path = str(npm_path) if npm_path else None

    if command[0] == npm_path:
        return [*command, "--loglevel", "silly"]
    return command


def run_process_with_fallbacks(
    args: list[str],
    *,
    show_status_message: str,
    fallbacks: str | Sequence[str] | Sequence[Sequence[str]] | None = None,
    analytics_enabled: bool = False,
    prior_logs: tuple[tuple[str, ...], ...] = (),
    **kwargs,
):
    """Run subprocess and retry using fallback command if initial command fails.

    Args:
        args: A string, or a sequence of program arguments.
        show_status_message: The status message to be displayed in the console.
        fallbacks: The fallback command to run if the initial command fails.
        analytics_enabled: Whether analytics are enabled for this command.
        prior_logs: The logs of the prior processes that have been run.
        **kwargs: Kwargs to pass to new_process function.
    """
    process = new_process(get_command_with_loglevel(args), **kwargs)
    if not fallbacks:
        # No fallback given, or this _is_ the fallback command.
        show_status(
            show_status_message,
            process,
            analytics_enabled=analytics_enabled,
            prior_logs=prior_logs,
        )
    else:
        # Suppress errors for initial command, because we will try to fallback
        logs = show_status(show_status_message, process, suppress_errors=True)

        current_fallback = fallbacks[0] if not isinstance(fallbacks, str) else fallbacks
        next_fallbacks = fallbacks[1:] if not isinstance(fallbacks, str) else None

        if process.returncode != 0:
            # retry with fallback command.
            fallback_with_args = (
                [current_fallback, *args[1:]]
                if isinstance(current_fallback, str)
                else [*current_fallback, *args[1:]]
            )
            console.warn(
                f"There was an error running command: {args}. Falling back to: {fallback_with_args}."
            )
            run_process_with_fallbacks(
                fallback_with_args,
                show_status_message=show_status_message,
                fallbacks=next_fallbacks,
                analytics_enabled=analytics_enabled,
                prior_logs=(*prior_logs, tuple(logs)),
                **kwargs,
            )


def execute_command_and_return_output(command: str) -> str | None:
    """Execute a command and return the output.

    Args:
        command: The command to run.

    Returns:
        The output of the command.
    """
    try:
        return subprocess.check_output(command, shell=True).decode().strip()
    except subprocess.SubprocessError as err:
        console.error(
            f"The command `{command}` failed with error: {err}. This will return None."
        )
        return None
