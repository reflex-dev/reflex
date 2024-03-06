"""Helper functions for the benchmarking scripts."""

from __future__ import annotations

import json


def extract_stats_from_json(json_file: str) -> list[dict]:
    """Extracts the stats from the JSON data and returns them as a list of dictionaries.

    Args:
        json_file: The JSON file to extract the stats data from.

    Returns:
        list[dict]: The stats for each test.
    """
    with open(json_file, "r") as file:
        json_data = json.load(file)

    # Load the JSON data if it is a string, otherwise assume it's already a dictionary
    data = json.loads(json_data) if isinstance(json_data, str) else json_data

    # Initialize an empty list to store the stats for each test
    test_stats = []

    # Iterate over each test in the 'benchmarks' list
    for test in data.get("benchmarks", []):
        stats = test.get("stats", {})
        test_name = test.get("name", "Unknown Test")
        min_value = stats.get("min", None)
        max_value = stats.get("max", None)
        mean_value = stats.get("mean", None)
        stdev_value = stats.get("stddev", None)

        test_stats.append(
            {
                "test_name": test_name,
                "min": min_value,
                "max": max_value,
                "mean": mean_value,
                "stdev": stdev_value,
            }
        )
    return test_stats
