"""Checks the size of a specific directory and uploads result."""

import argparse
import os
import subprocess
from datetime import datetime

import psycopg2


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


def insert_benchmarking_data(
    db_connection_url: str,
    os_type_version: str,
    python_version: str,
    measurement_type: str,
    commit_sha: str,
    pr_title: str,
    branch_name: str,
    pr_id: str,
    path: str,
):
    """Insert the benchmarking data into the database.

    Args:
        db_connection_url: The URL to connect to the database.
        os_type_version: The OS type and version to insert.
        python_version: The Python version to insert.
        measurement_type: The type of metric to measure.
        commit_sha: The commit SHA to insert.
        pr_title: The PR title to insert.
        branch_name: The name of the branch.
        pr_id: The id of the PR.
        path: The path to the dir or file to check size.
    """
    if measurement_type == "reflex-package":
        size = get_package_size(path, os_type_version)
    else:
        size = get_directory_size(path)

    # Get the current timestamp
    current_timestamp = datetime.now()

    # Connect to the database and insert the data
    with psycopg2.connect(db_connection_url) as conn, conn.cursor() as cursor:
        insert_query = """
            INSERT INTO size_benchmarks (os, python_version, commit_sha, created_at, pr_title, branch_name, pr_id, measurement_type, size)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
        cursor.execute(
            insert_query,
            (
                os_type_version,
                python_version,
                commit_sha,
                current_timestamp,
                pr_title,
                branch_name,
                pr_id,
                measurement_type,
                round(
                    size / (1024 * 1024), 3
                ),  # save size in mb and round to 3 places.
            ),
        )
        # Commit the transaction
        conn.commit()


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
        "--db-url",
        help="The URL to connect to the database.",
        required=True,
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

    # Insert the data into the database
    insert_benchmarking_data(
        db_connection_url=args.db_url,
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
