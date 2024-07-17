"""Checks the size of a specific directory and uploads result to Posthog."""

import argparse
import os

from utils import get_directory_size, send_data_to_posthog


def insert_benchmarking_data(
    os_type_version: str,
    python_version: str,
    app_name: str,
    commit_sha: str,
    pr_title: str,
    branch_name: str,
    pr_id: str,
    path: str,
):
    """Insert the benchmarking data into PostHog.

    Args:
        app_name: The name of the app being measured.
        os_type_version: The OS type and version to insert.
        python_version: The Python version to insert.
        commit_sha: The commit SHA to insert.
        pr_title: The PR title to insert.
        branch_name: The name of the branch.
        pr_id: The id of the PR.
        path: The path to the dir or file to check size.
    """
    size = get_directory_size(path)

    # Prepare the event data
    properties = {
        "app_name": app_name,
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

    send_data_to_posthog("web-size", properties)


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
        "--app-name",
        help="The name of the app measured.",
        required=True,
    )
    parser.add_argument(
        "--pr-id",
        help="The pr id",
        required=True,
    )
    parser.add_argument(
        "--path",
        help="The current path to app to check.",
        required=True,
    )
    args = parser.parse_args()

    # Get the PR title from env or the args. For the PR merge or push event, there is no PR title, leaving it empty.
    pr_title = args.pr_title or os.getenv("PR_TITLE", "")

    # Insert the data into the database
    insert_benchmarking_data(
        app_name=args.app_name,
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
