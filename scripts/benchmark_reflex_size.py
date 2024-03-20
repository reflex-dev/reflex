import os
import sys
import subprocess
import argparse
import json
from datetime import datetime

import psycopg2

def get_directory_size(directory):
    total_size = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

def get_python_version(venv_path):
    python_executable = os.path.join(venv_path, 'bin', 'python')
    try:
        output = subprocess.check_output([python_executable, '--version'], stderr=subprocess.STDOUT)
        python_version = output.decode('utf-8').strip().split()[1]
        return ".".join(python_version.split(".")[:-1])
    except subprocess.CalledProcessError:
        return None

def get_package_size(venv_path):
    python_version = get_python_version(venv_path)
    if python_version is None:
        print("Error: Failed to determine Python version.")
        return

    package_dir = os.path.join(venv_path,  'lib', f"python{python_version}", 'site-packages')
    if not os.path.exists(package_dir):
        print("Error: Virtual environment does not exist or is not activated.")
        return

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
        performance_data: The performance data of reflex web to insert.
        commit_sha: The commit SHA to insert.
        pr_title: The PR title to insert.
        branch_name: The name of the branch.
        event_type: Type of github event(push, pull request, etc)
        actor: Username of the user that triggered the run.
    """
    # Serialize the JSON data

    if measurement_type == "reflex-package":
        size = get_package_size(path)
    elif measurement_type == "counter-app-dot-web":
        size = get_directory_size(path)
    else:
        raise ValueError(f"measurement_type should be of the following values: `reflex-package`")

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
                size,
            ),
        )
        # Commit the transaction
        conn.commit()

def main():
    """Runs the benchmarks and inserts the results."""
    # Get the commit SHA and JSON directory from the command line arguments
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
        required=True,
    )
    parser.add_argument(
        "--branch-name",
        help="The current branch",
        required=True,
    )
    parser.add_argument(
        "--pr-id",
        help="The github event type",
        required=True,
    )
    parser.add_argument(
        "--measurement-type",
        help="Username of the user that triggered the run.",
        required=True,
    )
    parser.add_argument(
        "--path",
        help="Username of the user that triggered the run.",
        required=True,
    )
    args = parser.parse_args()

    # Get the results of pytest benchmarks
    # Insert the data into the database
    insert_benchmarking_data(
        db_connection_url=args.db_url,
        os_type_version=args.os,
        python_version=args.python_version,
        measurement_type=args.measurement_type,
        commit_sha=args.commit_sha,
        pr_title=args.pr_title,
        branch_name=args.branch_name,
        pr_id=args.pr_id,
        path=args.path
    )


if __name__ == "__main__":
    main()
