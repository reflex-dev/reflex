"""Test fixtures."""
import platform

import pytest


@pytest.fixture(scope="function")
def windows_platform() -> bool:
    """Check if system is windows.

    Returns:
        whether system is windows.
    """
    yield platform.system() == "Windows"
