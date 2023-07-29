"""Process operations."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
from typing import Callable, List, Optional
from urllib.parse import urlparse

import psutil
import typer

from reflex import constants
from reflex.config import get_config
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


def get_api_port() -> int:
    """Get the API port.

    Returns:
        The API port.
    """
    port = urlparse(get_config().api_url).port
    if port is None:
        port = urlparse(constants.API_URL).port
    assert port is not None
    return port


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
        sys.exit()


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
    env = {
        **os.environ,
        "PATH": os.pathsep.join([constants.NODE_BIN_PATH, os.environ["PATH"]]),
    }
    kwargs = {
        "env": env,
        "stderr": None if show_logs else subprocess.STDOUT,
        "stdout": None if show_logs else subprocess.PIPE,
        "universal_newlines": True,
        "encoding": "UTF-8",
        **kwargs,
    }
    console.debug(f"Running command: {args} with kwargs: {kwargs}")
    fn = subprocess.run if run else subprocess.Popen
    return fn(args, **kwargs)


def show_progress(process: subprocess.Popen, message: str, checkpoints: List[str]):
    """Show a progress bar for a process.

    Args:
        process: The process.
        message: The message to display.
        checkpoints: The checkpoints to advance the progress bar.
    """
    # Create a progress object
    progress = console.progress()
    task = progress.add_task(f"{message}: ", total=len(checkpoints))

    # Iterate over the process output.
    try:
        with progress, process:
            if process.stdout is None:
                return
            for line in process.stdout:
                console.debug(line, end="")

                # Check for special strings and update the progress bar.
                for special_string in checkpoints:
                    if special_string in line:
                        if special_string == checkpoints[-1]:
                            progress.update(task, completed=len(checkpoints))
                        else:
                            progress.update(task, advance=1)
                        break

    except Exception as e:
        console.error(f"Error during {message} {e}")
        console.error(
            "Run in with [bold]--loglevel debug[/bold] to see the full error."
        )
        typer.Exit(1)


def show_logs(
    message: str, process: subprocess.Popen, logger: Callable = console.debug
):
    """Show the logs for a process.

    Args:
        message: The message to display.
        process: The process.
        logger: The log function to use.
    """
    # TODO: refactor this function with show_progress
    # Iterate over the process output.
    try:
        with process:
            if process.stdout is None:
                return
            for line in process.stdout:
                logger(line, end="")

    except Exception as e:
        console.error(f"Error during {message} {e}")
        console.error(
            "Run in with [bold]--loglevel debug[/bold] to see the full error."
        )
        typer.Exit(1)


def catch_keyboard_interrupt(signal, frame):
    """Display a custom message with the current time when exiting an app.

    Args:
        signal: The keyboard interrupt signal.
        frame: The current stack frame.
    """
    console.log("Reflex app stopped.")
