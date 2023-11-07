import reflex as rx
import psycopg2
import json
import os
from datetime import datetime

def insert_benchmarking_data(db_connection_url, lighthouse_data, performance_data, commit_sha):
    # Connect to the database
    print("Connecting to the database..." )
    try:
        conn = psycopg2.connect(db_connection_url)
    except psycopg2.Error as e:
        print("Error connecting to the database")
        return
    cursor = conn.cursor()

    # Serialize the JSON data
    lighthouse_json = json.dumps(lighthouse_data)
    performance_json = json.dumps(performance_data)

    # Get the current timestamp
    current_timestamp = datetime.now()

    # Insert the data into the database
    insert_query = """
    INSERT INTO benchmarks (lighthouse, performance, commit_sha, time) VALUES (%s, %s, %s, %s);
    """
    cursor.execute(insert_query, (lighthouse_json, performance_json, commit_sha, current_timestamp))

    # Commit the transaction and close the connection
    conn.commit()
    cursor.close()
    conn.close()