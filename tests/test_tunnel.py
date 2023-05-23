import pytest

from pynecone.utils.tunnel import remove_file_extensions


@pytest.mark.parametrize(
    "input_string, expected_output",
    [("example.tar.gz", "example"), ("file.zip", "file")],
)
def test_remove_file_extensions(input_string, expected_output):
    output = remove_file_extensions(input_string)
    assert output == expected_output
