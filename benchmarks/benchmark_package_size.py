"""Checks the size of a specific directory and uploads result to Posthog."""

import argparse
import os

from utils import get_directory_size, get_python_version, send_data_to_posthog


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
    print("Python version:", python_version)
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


def insert_benchmarking_data(
    os_type_version: str,
    python_version: str,
    commit_sha: str,
    pr_title: str,
    branch_name: str,
    pr_id: str,
    path: str,
):
    """Insert the benchmarking data into PostHog.

    Args:
        os_type_version: The OS type and version to insert.
        python_version: The Python version to insert.
        commit_sha: The commit SHA to insert.
        pr_title: The PR title to insert.
        branch_name: The name of the branch.
        pr_id: The id of the PR.
        path: The path to the dir or file to check size.
    """
    if "./dist" in path:
        size = get_directory_size(path)
    else:
        size = get_package_size(path, os_type_version)

    # Prepare the event data
    properties = {
        "path": path,
        "os": os_type_version,
        "python_version": python_version,
        "distinct_id": commit_sha,
        "pr_title": pr_title,
        "branch_name": branch_name,
        "pr_id": pr_id,
        "size_mb": round(
            size / (1024 * 1024), 3
        ),  # save size in MB and round to 3 places
    }

    send_data_to_posthog("package_size", properties)


def main():
    """Runs the benchmarks and inserts the results."""
    parser = argparse.ArgumentParser(description="Run benchmarks and process results.")
    parser.add_argument(
        "--os", help="The OS type and version to insert into the database."
    )
    parser.add_argument(
        "--python-version", help="The Python version to insert into the database."
    )
    parser.add_argument(
        "--commit-sha", help="The commit SHA to insert into the database."
    )
    parser.add_argument(
        "--pr-title",
        help="The PR title to insert into the database.",
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
        "--path",
        help="The path to the vnenv.",
        required=True,
    )
    args = parser.parse_args()

    # Get the PR title from env or the args. For the PR merge or push event, there is no PR title, leaving it empty.
    pr_title = args.pr_title or os.getenv("PR_TITLE", "")

    # Insert the data into the database
    insert_benchmarking_data(
        os_type_version=args.os,
        python_version=args.python_version,
        commit_sha=args.commit_sha,
        pr_title=pr_title,
        branch_name=args.branch_name,
        pr_id=args.pr_id,
        path=args.path,
    )


if __name__ == "__main__":
    main()
