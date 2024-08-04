"""Extract and upload benchmarking data to PostHog."""

from __future__ import annotations

import argparse
import json
import os

from utils import send_data_to_posthog


def extract_stats_from_json(json_file: str) -> dict:
    """Extracts the stats from the JSON data and returns them as dictionaries.

    Args:
        json_file: The JSON file to extract the stats data from.

    Returns:
        dict: The stats for each test.
    """
    with open(json_file, "r") as file:
        json_data = json.load(file)

    # Load the JSON data if it is a string, otherwise assume it's already a dictionary
    data = json.loads(json_data) if isinstance(json_data, str) else json_data

    result = data.get("results", [{}])[0]
    return {
        k: v
        for k, v in result.items()
        if k in ("mean", "stddev", "median", "min", "max")
    }


def insert_benchmarking_data(
    os_type_version: str,
    python_version: str,
    performance_data: dict,
    commit_sha: str,
    pr_title: str,
    branch_name: str,
    pr_id: str,
    app_name: str,
):
    """Insert the benchmarking data into the database.

    Args:
        os_type_version: The OS type and version to insert.
        python_version: The Python version to insert.
        performance_data: The imports performance data to insert.
        commit_sha: The commit SHA to insert.
        pr_title: The PR title to insert.
        branch_name: The name of the branch.
        pr_id: Id of the PR.
        app_name: The name of the app being measured.
    """
    properties = {
        "os": os_type_version,
        "python_version": python_version,
        "distinct_id": commit_sha,
        "pr_title": pr_title,
        "branch_name": branch_name,
        "pr_id": pr_id,
        "performance": performance_data,
        "app_name": app_name,
    }

    send_data_to_posthog("import_benchmark", properties)


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
        "--benchmark-json",
        help="The JSON file containing the benchmark results.",
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
        help="ID of the PR.",
        required=True,
    )
    args = parser.parse_args()

    # Get the PR title from env or the args. For the PR merge or push event, there is no PR title, leaving it empty.
    pr_title = args.pr_title or os.getenv("PR_TITLE", "")

    cleaned_benchmark_results = extract_stats_from_json(args.benchmark_json)
    # Insert the data into the database
    insert_benchmarking_data(
        os_type_version=args.os,
        python_version=args.python_version,
        performance_data=cleaned_benchmark_results,
        commit_sha=args.commit_sha,
        pr_title=pr_title,
        branch_name=args.branch_name,
        app_name=args.app_name,
        pr_id=args.pr_id,
    )


if __name__ == "__main__":
    main()
