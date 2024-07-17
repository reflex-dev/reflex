"""Utility functions for the benchmarks."""

import os
import subprocess

import httpx
from httpx import HTTPError


def get_python_version(venv_path, os_name):
    """Get the python version of python in a virtual env.

    Args:
        venv_path: Path to virtual environment.
        os_name: Name of os.

    Returns:
        The python version.
    """
    python_executable = (
        os.path.join(venv_path, "bin", "python")
        if "windows" not in os_name
        else os.path.join(venv_path, "Scripts", "python.exe")
    )
    try:
        output = subprocess.check_output(
            [python_executable, "--version"], stderr=subprocess.STDOUT
        )
        python_version = output.decode("utf-8").strip().split()[1]
        return ".".join(python_version.split(".")[:-1])
    except subprocess.CalledProcessError:
        return None


def get_directory_size(directory):
    """Get the size of a directory in bytes.

    Args:
        directory: The directory to check.

    Returns:
        The size of the dir in bytes.
    """
    total_size = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size


def send_data_to_posthog(event, properties):
    """Send data to PostHog.

    Args:
        event: The event to send.
        properties: The properties to send.

    Raises:
        HTTPError: When there is an error sending data to PostHog.
    """
    event_data = {
        "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
        "event": event,
        "properties": properties,
    }

    with httpx.Client() as client:
        response = client.post("https://app.posthog.com/capture/", json=event_data)
        if response.status_code != 200:
            raise HTTPError(
                f"Error sending data to PostHog: {response.status_code} - {response.text}"
            )
