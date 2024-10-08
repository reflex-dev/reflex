"""Constants for the custom components."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


class CustomComponents(SimpleNamespace):
    """Constants for the custom components."""

    # The name of the custom components source directory.
    SRC_DIR = "custom_components"
    # The name of the custom components pyproject.toml file.
    PYPROJECT_TOML = Path("pyproject.toml")
    # The name of the custom components package README file.
    PACKAGE_README = Path("README.md")
    # The name of the custom components package .gitignore file.
    PACKAGE_GITIGNORE = ".gitignore"
    # The name of the distribution directory as result of a build.
    DIST_DIR = "dist"
    # The name of the init file.
    INIT_FILE = "__init__.py"
    # Suffixes for the distribution files.
    DISTRIBUTION_FILE_SUFFIXES = [".tar.gz", ".whl"]
    # The name to the URL of python package repositories.
    REPO_URLS = {
        # Note: the trailing slash is required for below URLs.
        "pypi": "https://upload.pypi.org/legacy/",
        "testpypi": "https://test.pypi.org/legacy/",
    }
    # The .gitignore file for the custom component project.
    FILE = Path(".gitignore")
    # Files to gitignore.
    DEFAULTS = {"__pycache__/", "*.py[cod]", "*.egg-info/", "dist/"}
