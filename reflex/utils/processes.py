"""Process operations."""

from __future__ import annotations

import collections
import contextlib
import importlib.metadata
import os
import signal
import subprocess
from concurrent import futures
from pathlib import Path
from typing import Any, Callable, Generator, Literal, Sequence, Tuple, overload

import psutil
import typer
from redis.exceptions import RedisError
from rich.progress import Progress

from reflex import constants
from reflex.config import environment
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
        Exit: If unable to connect to Redis.

    Returns:
        The number of backend worker processes.
    """
    if (redis_client := prerequisites.get_redis_sync()) is None:
        return 1
    try:
        redis_client.ping()
    except RedisError as re:
        console.error(f"Unable to connect to Redis: {re}")
        raise typer.Exit(1) from re
    return (os.cpu_count() or 1) * 2 + 1


def get_process_on_port(port: int) -> psutil.Process | None:
    """Get the process on the given port.

    Args:
        port: The port.

    Returns:
        The process on the given port.
    """
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        with contextlib.suppress(
            psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess
        ):
            if importlib.metadata.version("psutil") >= "6.0.0":
                conns = proc.net_connections(kind="inet")
            else:
                conns = proc.connections(kind="inet")
            for conn in conns:
                if conn.laddr.port == int(port):
                    return proc
    return None


def is_process_on_port(port: int) -> bool:
    """Check if a process is running on the given port.

    Args:
        port: The port.

    Returns:
        Whether a process is running on the given port.
    """
    return get_process_on_port(port) is not None


def kill_process_on_port(port: int):
    """Kill the process on the given port.

    Args:
        port: The port.
    """
    if get_process_on_port(port) is not None:
        with contextlib.suppress(psutil.AccessDenied):
            get_process_on_port(port).kill()  # pyright: ignore [reportOptionalMemberAccess]


def change_port(port: int, _type: str) -> int:
    """Change the port.

    Args:
        port: The port.
        _type: The type of the port.

    Returns:
        The new port.

    """
    new_port = port + 1
    if is_process_on_port(new_port):
        return change_port(new_port, _type)
    console.info(
        f"The {_type} will run on port [bold underline]{new_port}[/bold underline]."
    )
    return new_port


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
        Exit:when the port is in use.
    """
    if (process := get_process_on_port(port)) is None:
        return port
    if auto_increment:
        return change_port(port, service_name)
    else:
        console.error(
            f"{service_name.capitalize()} port: {port} is already in use by PID: {process.pid}."
        )
        raise typer.Exit()


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
        Exit: When attempting to run a command with a None value.
    """
    # Check for invalid command first.
    non_empty_args = list(filter(None, args)) if isinstance(args, list) else [args]
    if isinstance(args, list) and len(non_empty_args) != len(args):
        console.error(f"Invalid command: {args}")
        raise typer.Exit(1)

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


def run_concurrently(*fns: Callable | Tuple) -> None:
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
    prior_logs: Tuple[tuple[str, ...], ...] = (),
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
        Exit: If the process failed.
    """
    from reflex.utils import telemetry

    # Store the tail of the logs.
    logs = collections.deque(maxlen=512)
    with process:
        console.debug(message, progress=progress)
        if process.stdout is None:
            return
        for line in process.stdout:
            console.debug(line, end="", progress=progress)
            logs.append(line)
            yield line

    # Check if the process failed (not printing the logs for SIGINT).

    # Windows uvicorn bug
    # https://github.com/reflex-dev/reflex/issues/2335
    accepted_return_codes = [0, -2, 15] if constants.IS_WINDOWS else [0, -2]
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
            raise typer.Exit(1)
        for set_of_logs in (*prior_logs, tuple(logs)):
            for line in set_of_logs:
                console.error(line, end="")
            console.error("\n\n")
        if analytics_enabled:
            telemetry.send("error", context=message)
        console.error("Run with [bold]--loglevel debug [/bold] for the full log.")
        raise typer.Exit(1)


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
    prior_logs: Tuple[tuple[str, ...], ...] = (),
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
            for special_string in checkpoints:
                if special_string in line:
                    progress.update(task, advance=1)
                    if special_string == checkpoints[-1]:
                        progress.update(task, completed=len(checkpoints))
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
    prior_logs: Tuple[tuple[str, ...], ...] = (),
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
