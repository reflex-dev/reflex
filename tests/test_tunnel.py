import pytest

from pynecone.utils import tunnel


@pytest.mark.parametrize(
    "input_string, expected_output",
    [("example.tar.gz", "example"), ("file.zip", "file")],
)
def test_remove_file_extensions(input_string, expected_output):
    output = tunnel.remove_file_extensions(input_string)
    assert output == expected_output
