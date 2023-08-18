"""Process operations."""

from __future__ import annotations

import collections
import contextlib
import os
import signal
import subprocess
from concurrent import futures
from typing import Callable, List, Optional, Tuple, Union

import psutil
import typer

from reflex import constants
from reflex.utils import console, prerequisites


def kill(pid):
    """Kill a process.

    Args:
        pid: The process ID.
    """
    os.kill(pid, signal.SIGTERM)


def get_num_workers() -> int:
    """Get the number of backend worker processes.

    Returns:
        The number of backend worker processes.
    """
    return 1 if prerequisites.get_redis() is None else (os.cpu_count() or 1) * 2 + 1


def get_process_on_port(port) -> Optional[psutil.Process]:
    """Get the process on the given port.

    Args:
        port: The port.

    Returns:
        The process on the given port.
    """
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            for conns in proc.connections(kind="inet"):
                if conns.laddr.port == int(port):
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None


def is_process_on_port(port) -> bool:
    """Check if a process is running on the given port.

    Args:
        port: The port.

    Returns:
        Whether a process is running on the given port.
    """
    return get_process_on_port(port) is not None


def kill_process_on_port(port):
    """Kill the process on the given port.

    Args:
        port: The port.
    """
    if get_process_on_port(port) is not None:
        with contextlib.suppress(psutil.AccessDenied):
            get_process_on_port(port).kill()  # type: ignore


def change_or_terminate_port(port, _type) -> str:
    """Terminate or change the port.

    Args:
        port: The port.
        _type: The type of the port.

    Returns:
        The new port or the current one.


    Raises:
        Exit: If the user wants to exit.
    """
    console.info(
        f"Something is already running on port [bold underline]{port}[/bold underline]. This is the port the {_type} runs on."
    )
    frontend_action = console.ask("Kill or change it?", choices=["k", "c", "n"])
    if frontend_action == "k":
        kill_process_on_port(port)
        return port
    elif frontend_action == "c":
        new_port = console.ask("Specify the new port")

        # Check if also the new port is used
        if is_process_on_port(new_port):
            return change_or_terminate_port(new_port, _type)
        else:
            console.info(
                f"The {_type} will run on port [bold underline]{new_port}[/bold underline]."
            )
            return new_port
    else:
        console.log("Exiting...")
        raise typer.Exit()


def new_process(args, run: bool = False, show_logs: bool = False, **kwargs):
    """Wrapper over subprocess.Popen to unify the launch of child processes.

    Args:
        args: A string, or a sequence of program arguments.
        run: Whether to run the process to completion.
        show_logs: Whether to show the logs of the process.
        **kwargs: Kwargs to override default wrap values to pass to subprocess.Popen as arguments.

    Returns:
        Execute a child program in a new process.
    """
    # Add the node bin path to the PATH environment variable.
    env = {
        **os.environ,
        "PATH": os.pathsep.join([constants.NODE_BIN_PATH, os.environ["PATH"]]),
        **kwargs.pop("env", {}),
    }
    kwargs = {
        "env": env,
        "stderr": None if show_logs else subprocess.STDOUT,
        "stdout": None if show_logs else subprocess.PIPE,
        "universal_newlines": True,
        "encoding": "UTF-8",
        **kwargs,
    }
    console.debug(f"Running command: {args}")
    fn = subprocess.run if run else subprocess.Popen
    return fn(args, **kwargs)


def run_concurrently(*fns: Union[Callable, Tuple]):
    """Run functions concurrently in a thread pool.


    Args:
        *fns: The functions to run.
    """
    # Convert the functions to tuples.
    fns = [fn if isinstance(fn, tuple) else (fn,) for fn in fns]  # type: ignore

    # Run the functions concurrently.
    with futures.ThreadPoolExecutor(max_workers=len(fns)) as executor:
        # Submit the tasks.
        tasks = [executor.submit(*fn) for fn in fns]  # type: ignore

        # Get the results in the order completed to check any exceptions.
        for task in futures.as_completed(tasks):
            task.result()


def stream_logs(
    message: str,
    process: subprocess.Popen,
):
    """Stream the logs for a process.

    Args:
        message: The message to display.
        process: The process.

    Yields:
        The lines of the process output.

    Raises:
        Exit: If the process failed.
    """
    # Store the tail of the logs.
    logs = collections.deque(maxlen=512)
    with process:
        console.debug(message)
        if process.stdout is None:
            return
        for line in process.stdout:
            console.debug(line, end="")
            logs.append(line)
            yield line

    if process.returncode != 0:
        console.error(f"{message} failed with exit code {process.returncode}")
        for line in logs:
            console.error(line, end="")
        console.error("Run with [bold]--loglevel debug [/bold] for the full log.")
        raise typer.Exit(1)


def show_logs(
    message: str,
    process: subprocess.Popen,
):
    """Show the logs for a process.

    Args:
        message: The message to display.
        process: The process.
    """
    for _ in stream_logs(message, process):
        pass


def show_status(message: str, process: subprocess.Popen):
    """Show the status of a process.

    Args:
        message: The initial message to display.
        process: The process.
    """
    with console.status(message) as status:
        for line in stream_logs(message, process):
            status.update(f"{message} {line}")


def show_progress(message: str, process: subprocess.Popen, checkpoints: List[str]):
    """Show a progress bar for a process.

    Args:
        message: The message to display.
        process: The process.
        checkpoints: The checkpoints to advance the progress bar.
    """
    # Iterate over the process output.
    with console.progress() as progress:
        task = progress.add_task(f"{message}: ", total=len(checkpoints))
        for line in stream_logs(message, process):
            # Check for special strings and update the progress bar.
            for special_string in checkpoints:
                if special_string in line:
                    progress.update(task, advance=1)
                    if special_string == checkpoints[-1]:
                        progress.update(task, completed=len(checkpoints))
                    break


def catch_keyboard_interrupt(signal, frame):
    """Display a custom message with the current time when exiting an app.

    Args:
        signal: The keyboard interrupt signal.
        frame: The current stack frame.
    """
    console.log("Reflex app stopped.")
