"""Constants for the custom components."""
from __future__ import annotations

from types import SimpleNamespace


class CustomComponents(SimpleNamespace):
    """Constants for the custom components."""

    # The name of the custom components source directory.
    SRC_DIR = "custom_components"
    # The name of the custom components pyproject.toml file.
    PYPROJECT_TOML = "pyproject.toml"
    # The name of the custom components package README file.
    PACKAGE_README = "README.md"
    # The name of the custom components package .gitignore file.
    PACKAGE_GITIGNORE = ".gitignore"
    # The name of the distribution directory as result of a build.
    DIST_DIR = "dist"
    # The name to the URL of python package repositories.
    REPO_URLS: dict[str, str] = {
        # Note: the trailing slash is required for below URLs.
        "pypi": "https://pypi.org/legacy/",
        "testpypi": "https://test.pypi.org/legacy/",
    }
