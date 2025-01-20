import pytest
from benchmarks.benchmark_imports import extract_stats_from_json

@pytest.mark.benchmark
def test_extract_stats_from_json(benchmark):
    # Example JSON data
    json_data = '{"results": [{"mean": 1.0, "stddev": 0.1, "median": 1.0, "min": 0.9, "max": 1.1}]}'
    
    # Benchmark the extract_stats_from_json function
    result = benchmark(extract_stats_from_json, json_data)
    
    # Assert the result to ensure correctness
    assert result == {
        "mean": 1.0,
        "stddev": 0.1,
        "median": 1.0,
        "min": 0.9,
        "max": 1.1
    } 