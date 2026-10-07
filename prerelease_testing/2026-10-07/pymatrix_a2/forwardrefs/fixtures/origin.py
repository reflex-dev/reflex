"""Explicit runtime and installed-package origin guards."""

import importlib.metadata
import os
import platform
import sys
from pathlib import Path

import reflex as rx
import reflex_base


def check_origin():
    """Require the assigned published environment and expected interpreter.

    Returns:
        Runtime and imported-package metadata.
    """
    expected = Path(os.environ["REFLEX_EXPECT_ENV"]).resolve()
    assert Path(rx.__file__).resolve().is_relative_to(expected), rx.__file__
    assert Path(reflex_base.__file__).resolve().is_relative_to(expected), (
        reflex_base.__file__
    )
    assert importlib.metadata.version("reflex") == os.environ["REFLEX_EXPECT_VERSION"]
    assert platform.python_version().startswith(os.environ["PYTHON_EXPECT_VERSION"])
    return {
        "python": platform.python_version(),
        "executable": sys.executable,
        "reflex": importlib.metadata.version("reflex"),
        "reflex_base": importlib.metadata.version("reflex-base"),
        "pydantic": importlib.metadata.version("pydantic"),
        "reflex_path": rx.__file__,
        "reflex_base_path": reflex_base.__file__,
    }
