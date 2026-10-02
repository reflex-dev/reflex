from pathlib import Path

import pytest
from pytest_mock import MockFixture
from reflex_cli.utils.dependency import detect_encoding, is_valid_url


def test_detect_encoding_file_not_found(mocker: MockFixture):
    filename = "non_existent_file.txt"

    mocker.patch("pathlib.Path.exists", return_value=False)

    with pytest.raises(FileNotFoundError):
        detect_encoding(Path(filename))


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.example.com", True),
        ("http://example.com", True),
        ("https://subdomain.example.com", True),
        ("http://example.com:8080", True),
        ("https://example.com/path?query=1&lang=en", True),
        ("https://example.com/#fragment", True),
        ("invalid-url", False),
        ("www.example.com", False),
        ("http://", False),
        ("", False),
        (None, False),
        ("https://", False),
        ("ftp://", False),
    ],
)
def test_is_valid_url(url: str, expected: bool):
    assert is_valid_url(url) == expected
