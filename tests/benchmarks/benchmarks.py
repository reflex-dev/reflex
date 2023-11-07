import json
import os
import pytest
from helpers import insert_benchmarking_data
import sys

def get_lighthouse_scores(directory_path):
    scores = {}
    
    # List all files in the given directory
    for filename in os.listdir(directory_path):
        # Check if the file is a JSON file
        if filename.endswith('.json'):
            file_path = os.path.join(directory_path, filename)
            with open(file_path, 'r') as file:
                data = json.load(file)
                # Extract scores and add them to the dictionary with the filename as key
                scores[data["finalUrl"].replace("http://localhost:3000/", "")] = {
                    "performance_score": data["categories"]["performance"]["score"],
                    "accessibility_score": data["categories"]["accessibility"]["score"],
                    "best_practices_score": data["categories"]["best-practices"]["score"],
                    "seo_score": data["categories"]["seo"]["score"],
                    "pwa_score": data["categories"]["pwa"]["score"]
                }
    return scores

def run_pytest_and_get_results(test_path=None):
    # Set the default path to the current directory if no path is provided
    if not test_path:
        test_path = os.getcwd()
    # Ensure you have installed the pytest-json plugin before running this
    pytest_args = ['-v', '--benchmark-json=benchmark_report.json', test_path]

    # Run pytest with the specified arguments
    pytest.main(pytest_args)

    with open('benchmark_report.json', 'r') as file:
            pytest_results = json.load(file)

    return pytest_results

def extract_stats_from_json(json_data):
    # Load the JSON data if it is a string, otherwise assume it's already a dictionary
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data

    # Initialize an empty list to store the stats for each test
    test_stats = []

    # Iterate over each test in the 'benchmarks' list
    for test in data.get('benchmarks', []):
        stats = test.get('stats', {})
        test_name = test.get('name', 'Unknown Test')
        min_value = stats.get('min', None)
        max_value = stats.get('max', None)
        mean_value = stats.get('mean', None)
        stdev_value = stats.get('stddev', None)

        test_stats.append({
            'test_name': test_name,
            'min': min_value,
            'max': max_value,
            'mean': mean_value,
            'stdev': stdev_value
        })

    return test_stats


def main():
    # Commit SHA
    commit_sha = sys.argv[1]
    json_dir = sys.argv[2]

    results = run_pytest_and_get_results()
    cleaned_results = extract_stats_from_json(results)

    # Upload lighthouse scores
    lighthouse_scores = get_lighthouse_scores(json_dir)

     # Upload benchmarking data to the database
    db_url = os.environ.get('DATABASE_URL')
    print(db_url)
    insert_benchmarking_data(db_url, lighthouse_scores, cleaned_results, commit_sha)

if __name__ == "__main__":
    main()