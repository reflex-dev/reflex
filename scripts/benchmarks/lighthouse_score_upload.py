"""Runs the benchmarks and inserts the results into the database."""

from __future__ import annotations

import json
import os
import sys
import httpx

def insert_benchmarking_data(
    db_connection_url: str,
    lighthouse_data: dict,
    commit_sha: str,
    pr_title: str,
):
    """Insert the benchmarking data into the database.

    Args:
        db_connection_url: The URL to connect to the database.
        lighthouse_data: The Lighthouse data to insert.
        commit_sha: The commit SHA to insert.
        pr_title: The PR title to insert.
    """

    # Prepare the event data
    event_data = {
        "api_key": "phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb",
        "event": "lighthouse_benchmark",
        "properties": {
            "distinct_id": commit_sha,
            "lighthouse_data": lighthouse_data,
            "pr_title": pr_title,
        }
    }

    # Send the data to PostHog
    with httpx.Client() as client:
        response = client.post("https://app.posthog.com/capture/", json=event_data)

    if response.status_code != 200:
        print(f"Error sending data to PostHog: {response.status_code} - {response.text}")
    else:
        print("Successfully sent benchmark data to PostHog")


def get_lighthouse_scores(directory_path: str) -> dict:
    """Extracts the Lighthouse scores from the JSON files in the specified directory.

    Args:
        directory_path (str): The path to the directory containing the JSON files.

    Returns:
        dict: The Lighthouse scores.
    """
    scores = {}

    try:
        for filename in os.listdir(directory_path):
            if filename.endswith(".json") and filename != "manifest.json":
                file_path = os.path.join(directory_path, filename)
                with open(file_path, "r") as file:
                    data = json.load(file)
                    # Extract scores and add them to the dictionary with the filename as key
                    scores[data["finalUrl"].replace("http://localhost:3000/", "")] = {
                        "performance_score": data["categories"]["performance"]["score"],
                        "accessibility_score": data["categories"]["accessibility"][
                            "score"
                        ],
                        "best_practices_score": data["categories"]["best-practices"][
                            "score"
                        ],
                        "seo_score": data["categories"]["seo"]["score"],
                        "pwa_score": data["categories"]["pwa"]["score"],
                    }
    except Exception as e:
        print(e)
        return {"error": "Error parsing JSON files"}

    return scores


def main():
    """Runs the benchmarks and inserts the results into the database."""
    # Get the commit SHA and JSON directory from the command line arguments
    commit_sha = sys.argv[1]
    json_dir = sys.argv[2]

    # Get the PR title and database URL from the environment variables
    pr_title = os.environ.get("PR_TITLE")
    db_url = os.environ.get("DATABASE_URL")

    if db_url is None or pr_title is None:
        sys.exit("Missing environment variables")

    # Get the Lighthouse scores
    lighthouse_scores = get_lighthouse_scores(json_dir)

    # Insert the data into the database
    insert_benchmarking_data(db_url, lighthouse_scores, commit_sha, pr_title)


if __name__ == "__main__":
    main()
