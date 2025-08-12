"""Integration tests for all urls in Reflex."""

import os
import re
from pathlib import Path

import pytest
import requests


def check_urls(repo_dir: Path):
    """Check that all URLs in the repo are valid and secure.

    Args:
        repo_dir: The directory of the repo.

    Returns:
        A list of errors.
    """
    url_pattern = re.compile(r'http[s]?://reflex\.dev[^\s")]*')
    errors = []

    for root, _dirs, files in os.walk(repo_dir):
        root = Path(root)
        if root.stem == "__pycache__":
            continue

        for file_name in files:
            if not file_name.endswith(".py") and not file_name.endswith(".md"):
                continue

            file_path = root / file_name
            try:
                for line in file_path.read_text().splitlines():
                    urls = url_pattern.findall(line)
                    for url in set(urls):
                        if url.startswith("http://"):
                            errors.append(
                                f"Found insecure HTTP URL: {url} in {file_path}"
                            )
                        url = url.strip('"\n')
                        try:
                            response = requests.head(
                                url, allow_redirects=True, timeout=5
                            )
                            response.raise_for_status()
                        except requests.RequestException as e:
                            errors.append(
                                f"Error accessing URL: {url} in {file_path} | Error: {e}, , Check your path ends with a /"
                            )
            except Exception as e:
                errors.append(f"Error reading file: {file_path} | Error: {e}")

    return errors


@pytest.mark.parametrize(
    "repo_dir",
    [Path(__file__).resolve().parent.parent / "reflex"],
)
def test_find_and_check_urls(repo_dir: Path):
    """Test that all URLs in the repo are valid and secure.

    Args:
        repo_dir: The directory of the repo.
    """
    errors = check_urls(repo_dir)
    assert not errors, "\n".join(errors)
