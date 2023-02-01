"""Test fixtures."""
import platform
from typing import Generator

import pytest


@pytest.fixture(scope="function")
def windows_platform() -> Generator:
    """Check if system is windows.

    Yields:
        whether system is windows.
    """
    yield platform.system() == "Windows"
