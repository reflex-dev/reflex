import platform

import pytest


@pytest.fixture(scope="function")
def windows_platform():
    yield platform.system() == "Windows"
