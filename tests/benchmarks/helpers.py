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
        conn.close()
