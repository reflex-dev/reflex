"""Helper functions for the benchmarking integration."""

import json
from datetime import datetime

import psycopg2


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
