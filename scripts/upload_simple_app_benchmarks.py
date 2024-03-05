"""Runs the benchmarks and inserts the results into the database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import psycopg2
from benchmark_helpers import extract_stats_from_json


def insert_benchmarking_data(
    db_connection_url: str,
    os_type_version: str,
    python_version: str,
    performance_data: list[dict],
    commit_sha: str,
    pr_title: str,
):
    """Insert the benchmarking data into the database.

    Args:
        db_connection_url: The URL to connect to the database.
        os_type_version: The OS type and version to insert.
        python_version: The Python version to insert.
        performance_data: The performance data of reflex web to insert.
        commit_sha: The commit SHA to insert.
        pr_title: The PR title to insert.
    """
    # Serialize the JSON data
    simple_app_performance_json = json.dumps(performance_data)

    # Get the current timestamp
    current_timestamp = datetime.now()

    # Connect to the database and insert the data
    with psycopg2.connect(db_connection_url) as conn, conn.cursor() as cursor:
        insert_query = """
            INSERT INTO simple_app_benchmarks (os, python_version, commit_sha, time, pr_title, performance)
            VALUES (%s, %s, %s, %s, %s);
            """
        cursor.execute(
            insert_query,
            (
                os_type_version,
                python_version,
                commit_sha,
                current_timestamp,
                pr_title,
                simple_app_performance_json,
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
        "--benchmark-json",
        help="The JSON file containing the benchmark results.",
    )
    parser.add_argument(
        "--pr-title",
        help="The PR title to insert into the database.",
    )
    args = parser.parse_args()

    # Get the PR title and database URL from the environment variables
    db_url = os.environ.get("DATABASE_URL")

    if db_url is None or args.pr_title is None:
        sys.exit("Missing environment variables")

    # Get the results of pytest benchmarks
    cleaned_benchmark_results = extract_stats_from_json(args.reflex_web_benchmark_json)
    # Insert the data into the database
    insert_benchmarking_data(
        db_connection_url=db_url,
        os_type_version=args.os,
        python_version=args.python_version,
        performance_data=cleaned_benchmark_results,
        commit_sha=args.commit_sha,
        pr_title=args.pr_title,
    )


if __name__ == "__main__":
    main()
