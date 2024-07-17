"""Checks the size of a specific directory and uploads result."""

import argparse
import os
import httpx


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
        actor: Username of the user that triggered the run.
    """
    size = get_directory_size(path)
       
    # Prepare the event data
    event_data = {
        "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
        "event": "web-size",
        "properties": {
            "app_name": app_name,
            "os": os_type_version,
            "python_version": python_version,
            "distinct_id": commit_sha,
            "pr_title": pr_title,
            "branch_name": branch_name,
            "pr_id": pr_id,
            "size_mb": round(size / (1024 * 1024), 3),  # save size in MB and round to 3 places
        },
    }

    # Send the data to PostHog
    with httpx.Client() as client:
        response = client.post("https://app.posthog.com/capture/", json=event_data)

    if response.status_code != 200:
        print(f"Error sending data to PostHog: {response.status_code} - {response.text}")
    else:
        print("Successfully sent benchmarking data to PostHog")


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
