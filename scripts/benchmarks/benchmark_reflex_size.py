"""Module for benchmarking the size of the reflex package and sending the data to PostHog."""

import argparse
import os
import subprocess
from datetime import datetime

import httpx

from reflex import constants


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


def get_package_size(venv_path, os_name):
    """Get the size of a specified package.

    Args:
        venv_path: The path to the venv.
        os_name: Name of os.

    Returns:
        The total size of the package in bytes.

    Raises:
        ValueError: when venv does not exist or python version is None.
    """
    python_version = get_python_version(venv_path, os_name)
    if python_version is None:
        raise ValueError("Error: Failed to determine Python version.")

    is_windows = "windows" in os_name

    full_path = (
        ["lib", f"python{python_version}", "site-packages"]
        if not is_windows
        else ["Lib", "site-packages"]
    )

    package_dir = os.path.join(venv_path, *full_path)
    if not os.path.exists(package_dir):
        raise ValueError(
            "Error: Virtual environment does not exist or is not activated."
        )

    total_size = get_directory_size(package_dir)
    return total_size


def send_benchmarking_data_to_posthog(
    posthog_api_key: str,
    os_type_version: str,
    python_version: str,
    measurement_type: str,
    commit_sha: str,
    pr_title: str,
    branch_name: str,
    pr_id: str,
    path: str,
):
    """Send the benchmarking data to PostHog.

    Args:
        posthog_api_key: The API key for PostHog.
        os_type_version: The OS type and version to send.
        python_version: The Python version to send.
        measurement_type: The type of metric to measure.
        commit_sha: The commit SHA to send.
        pr_title: The PR title to send.
        branch_name: The name of the branch.
        pr_id: The id of the PR.
        path: The path to the dir or file to check size.
    """
    if measurement_type == "reflex-package":
        size = get_package_size(path, os_type_version)
    else:
        size = get_directory_size(path)

    # Get the current timestamp
    current_timestamp = datetime.now().isoformat()

    # Prepare the event data
    event_data = {
        "api_key": posthog_api_key,
        "event": "size_benchmark",
        "properties": {
            "distinct_id": os.environ.get("GITHUB_ACTOR", "unknown"),
            "os": os_type_version,
            "python_version": python_version,
            "commit_sha": commit_sha,
            "created_at": current_timestamp,
            "pr_title": pr_title,
            "branch_name": branch_name,
            "pr_id": pr_id,
            "measurement_type": measurement_type,
            "size_mb": round(size / (1024 * 1024), 3),  # size in mb rounded to 3 places
        },
    }

    # Send the data to PostHog
    with httpx.Client() as client:
        response = client.post("https://app.posthog.com/capture/", json=event_data)

    if response.status_code != 200:
        print(
            f"Error sending data to PostHog: {response.status_code} - {response.text}"
        )
    else:
        print("Successfully sent data to PostHog")


def main():
    """Runs the benchmarks and sends the results to PostHog."""
    parser = argparse.ArgumentParser(description="Run benchmarks and process results.")
    parser.add_argument("--os", help="The OS type and version to send to PostHog.")
    parser.add_argument(
        "--python-version", help="The Python version to send to PostHog."
    )
    parser.add_argument("--commit-sha", help="The commit SHA to send to PostHog.")
    parser.add_argument(
        "--pr-title",
        help="The PR title to send to PostHog.",
    )
    parser.add_argument(
        "--branch-name",
        help="The current branch",
        required=True,
    )
    parser.add_argument(
        "--pr-id",
        help="The pr id",
        required=True,
    )
    parser.add_argument(
        "--measurement-type",
        help="The type of metric to be checked.",
        required=True,
    )
    parser.add_argument(
        "--path",
        help="the current path to check size.",
        required=True,
    )
    args = parser.parse_args()

    # Get the PR title from env or the args. For the PR merge or push event, there is no PR title, leaving it empty.
    pr_title = args.pr_title or os.getenv("PR_TITLE", "")

    # Send the data to PostHog
    send_benchmarking_data_to_posthog(
        posthog_api_key=constants.POSTHOG_API_KEY,
        os_type_version=args.os,
        python_version=args.python_version,
        measurement_type=args.measurement_type,
        commit_sha=args.commit_sha,
        pr_title=pr_title,
        branch_name=args.branch_name,
        pr_id=args.pr_id,
        path=args.path,
    )


if __name__ == "__main__":
    main()
