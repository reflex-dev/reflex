"""Extracts the Lighthouse scores from the JSON files in the specified directory and inserts them into the database."""

from __future__ import annotations

import json
import os
import sys

from utils import send_data_to_posthog


def insert_benchmarking_data(
    lighthouse_data: dict,
    commit_sha: str,
):
    """Insert the benchmarking data into the database.

    Args:
        lighthouse_data: The Lighthouse data to insert.
        commit_sha: The commit SHA to insert.
    """
    properties = {
        "distinct_id": commit_sha,
        "lighthouse_data": lighthouse_data,
    }

    # Send the data to PostHog
    send_data_to_posthog("lighthouse_benchmark", properties)


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
                    scores[data["finalUrl"].replace("http://localhost:3000/", "/")] = {
                        "performance_score": data["categories"]["performance"]["score"],
                        "accessibility_score": data["categories"]["accessibility"][
                            "score"
                        ],
                        "best_practices_score": data["categories"]["best-practices"][
                            "score"
                        ],
                        "seo_score": data["categories"]["seo"]["score"],
                    }
    except Exception as e:
        return {"error": e}

    return scores


def main():
    """Runs the benchmarks and inserts the results into the database."""
    # Get the commit SHA and JSON directory from the command line arguments
    commit_sha = sys.argv[1]
    json_dir = sys.argv[2]

    # Get the Lighthouse scores
    lighthouse_scores = get_lighthouse_scores(json_dir)

    # Insert the data into the database
    insert_benchmarking_data(lighthouse_scores, commit_sha)


if __name__ == "__main__":
    main()
