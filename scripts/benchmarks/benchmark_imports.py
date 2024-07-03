"""Runs the benchmarks and sends the results to PostHog."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from reflex import constants

import httpx


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


def send_benchmarking_data_to_posthog(
    posthog_api_key: str,
    os_type_version: str,
    python_version: str,
    performance_data: dict,
    commit_sha: str,
    pr_title: str,
    branch_name: str,
    event_type: str,
    actor: str,
    pr_id: str,
):
    """Send the benchmarking data to PostHog.

    Args:
        posthog_api_key: The API key for PostHog.
        os_type_version: The OS type and version to send.
        python_version: The Python version to send.
        performance_data: The imports performance data to send.
        commit_sha: The commit SHA to send.
        pr_title: The PR title to send.
        branch_name: The name of the branch.
        event_type: Type of github event(push, pull request, etc)
        actor: Username of the user that triggered the run.
        pr_id: Id of the PR.
    """
    # Get the current timestamp
    current_timestamp = datetime.now().isoformat()

    # Prepare the event data
    event_data = {
        "api_key": posthog_api_key,
        "event": "import_benchmark",
        "properties": {
            "distinct_id": actor,
            "os": os_type_version,
            "python_version": python_version,
            "commit_sha": commit_sha,
            "timestamp": current_timestamp,
            "pr_title": pr_title,
            "branch_name": branch_name,
            "event_type": event_type,
            "pr_id": pr_id,
            "performance": performance_data,
        }
    }

    # Send the data to PostHog
    with httpx.Client() as client:
        response = client.post(
            "https://app.posthog.com/capture/",
            json=event_data
        )

    if response.status_code != 200:
        print(f"Error sending data to PostHog: {response.status_code} - {response.text}")
    else:
        print("Successfully sent data to PostHog")


def main():
    """Runs the benchmarks and sends the results to PostHog."""
    parser = argparse.ArgumentParser(description="Run benchmarks and process results.")
    parser.add_argument(
        "--os", help="The OS type and version to send to PostHog."
    )
    parser.add_argument(
        "--python-version", help="The Python version to send to PostHog."
    )
    parser.add_argument(
        "--commit-sha", help="The commit SHA to send to PostHog."
    )
    parser.add_argument(
        "--benchmark-json",
        help="The JSON file containing the benchmark results.",
    )
    parser.add_argument(
        "--posthog-api-key",
        help="The API key for PostHog.",
        required=True,
    )
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
        "--event-type",
        help="The github event type",
        required=True,
    )
    parser.add_argument(
        "--actor",
        help="Username of the user that triggered the run.",
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
    # Send the data to PostHog
    send_benchmarking_data_to_posthog(
        posthog_api_key= constants.POSTHOG_API_KEY,
        os_type_version=args.os,
        python_version=args.python_version,
        performance_data=cleaned_benchmark_results,
        commit_sha=args.commit_sha,
        pr_title=pr_title,
        branch_name=args.branch_name,
        event_type=args.event_type,
        actor=args.actor,
        pr_id=args.pr_id,
    )


if __name__ == "__main__":
    main()