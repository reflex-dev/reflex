import unittest
import os
from scripts.benchmarks.benchmark_reflex_size import send_benchmarking_data_to_posthog as size_posthog
from scripts.benchmarks.benchmark_imports import send_benchmarking_data_to_posthog as imports_posthog
from scripts.benchmarks.simple_app_benchmark_upload import send_benchmarking_data_to_posthog as simple_app_posthog  # Replace 'your_module' with the actual module name

posthog_api_key = os.environ.get('POSTHOG_API_KEY', 'phc_JoMo0fOyi0GQAooY3UyO9k0hebGkMyFJrrCw1Gt5SGb')

class TestSendBenchmarkingDataIntegration(unittest.TestCase):
    def test_send_size_benchmarking_data_to_posthog_integration(self):
        # Call the function with test data
        result = size_posthog(
            posthog_api_key=posthog_api_key,
            os_type_version='test-os',
            python_version='3.8',
            measurement_type='test-measurement',
            commit_sha='test-sha',
            pr_title='Test PR',
            branch_name='test-branch',
            pr_id='test-pr-id',
            path='/path/to/test/venv'
        )
        # Print the result for debugging
        print(f"Result of send_benchmarking_data_to_posthog (size): {result}")
        # Assert that the function returned True, indicating success
        self.assertTrue(result, "Failed to send data to PostHog")
        print("Integration test for send_benchmarking_data_to_posthog (size) passed successfully!")

    def test_send_imports_benchmarking_data_to_posthog_integration(self):
        # Prepare test data
        performance_data = {
            "mean": 0.1,
            "stddev": 0.01,
            "median": 0.095,
            "min": 0.09,
            "max": 0.11
        }
        # Call the function with test data
        result = imports_posthog(
            posthog_api_key=posthog_api_key,
            os_type_version='test-os',
            python_version='3.9.5',
            performance_data=performance_data,
            commit_sha='test-sha',
            pr_title='Test PR',
            branch_name='test-branch',
            event_type='pull_request',
            actor='test-user',
            pr_id='test-pr-id'
        )
        # Print the result for debugging
        print(f"Result of send_benchmarking_data_to_posthog (imports): {result}")
        # Assert that the function executed without raising an exception
        self.assertIsNone(result, "Function should execute without errors and return None")
        print("Integration test for send_benchmarking_data_to_posthog (imports) passed successfully!")

    def test_send_simple_app_benchmarking_data_to_posthog_integration(self):
        # Prepare test data
        performance_data = [
            {
                "test_name": "test_simple_app",
                "group": "performance",
                "stats": {
                    "mean": 0.1,
                    "stddev": 0.01,
                    "median": 0.095,
                    "min": 0.09,
                    "max": 0.11
                },
                "full_name": "tests/test_simple_app.py::test_simple_app",
                "file_name": "test_simple_app"
            }
        ]
        # Call the function with test data
        try:
            simple_app_posthog(
                posthog_api_key=posthog_api_key,
                os_type_version='test-os',
                python_version='3.9.5',
                performance_data=performance_data,
                commit_sha='test-sha',
                pr_title='Test PR',
                branch_name='test-branch',
                event_type='pull_request',
                actor='test-user',
                pr_id='test-pr-id'
            )
            print("Integration test for send_benchmarking_data_to_posthog (simple app) passed successfully!")
        except Exception as e:
            self.fail(f"Function raised an exception: {str(e)}")

if __name__ == '__main__':
    unittest.main()