"""Runs the benchmarks and inserts the results into the database."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import psycopg2
import pytest
from benchmark_helpers import extract_stats_from_json


def insert_benchmarking_data(
    db_connection_url: str,
    lighthouse_data: dict,
    performance_data: list[dict],
    commit_sha: str,
    pr_title: str,
):
    """Insert the benchmarking data into the database.

    Args:
        db_connection_url: The URL to connect to the database.
        lighthouse_data: The Lighthouse data to insert.
        performance_data: The performance data to insert.
        commit_sha: The commit SHA to insert.
        pr_title: The PR title to insert.
    """
    # Serialize the JSON data
    lighthouse_json = json.dumps(lighthouse_data)
    performance_json = json.dumps(performance_data)

    # Get the current timestamp
    current_timestamp = datetime.now()

    # Connect to the database and insert the data
    with psycopg2.connect(db_connection_url) as conn, conn.cursor() as cursor:
        insert_query = """
            INSERT INTO benchmarks (lighthouse, performance, commit_sha, pr_title, time)
            VALUES (%s, %s, %s, %s, %s);
            """
        cursor.execute(
            insert_query,
            (
                lighthouse_json,
                performance_json,
                commit_sha,
                pr_title,
                current_timestamp,
            ),
        )
        # Commit the transaction
        conn.commit()


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


def run_pytest_and_get_results(test_path=None) -> str:
    """Runs pytest and returns the results.

    Args:
        test_path: The path to the tests to run.

    Returns:
        the name of the output file
    """
    # Set the default path to the current directory if no path is provided
    if not test_path:
        test_path = os.getcwd()

    output_file = "benchmark_report.json"

    # Ensure you have installed the pytest-json plugin before running this
    pytest_args = ["-v", f"--benchmark-json={output_file}", test_path]

    # Run pytest with the specified arguments
    pytest.main(pytest_args)

    # Print ls of the current directory
    print(os.listdir())

    return output_file


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

    # Run pytest and get the results
    result_json_file = run_pytest_and_get_results()
    cleaned_results = extract_stats_from_json(result_json_file)

    # Get the Lighthouse scores
    lighthouse_scores = get_lighthouse_scores(json_dir)

    # Insert the data into the database
    insert_benchmarking_data(
        db_url, lighthouse_scores, cleaned_results, commit_sha, pr_title
    )


if __name__ == "__main__":
    main()
