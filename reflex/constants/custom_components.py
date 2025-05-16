"""Constants for the custom components."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


class CustomComponents(SimpleNamespace):
    """Constants for the custom components."""

    # The name of the custom components source directory.
    SRC_DIR = Path("src")
    # The name of the custom components pyproject.toml file.
    PYPROJECT_TOML = Path("pyproject.toml")
    # The name of the custom components package README file.
    PACKAGE_README = Path("README.md")
    # The name of the distribution directory as result of a build.
    DIST_DIR = "dist"
    # The name of the init file.
    INIT_FILE = "__init__.py"
    # The .gitignore file for the custom component project.
    GITIGNORE_PATH = Path(".gitignore")
    # Files to gitignore.
    GITIGNORE_DEFAULTS = {"__pycache__/", "*.py[cod]", "*.egg-info/", "dist/"}
