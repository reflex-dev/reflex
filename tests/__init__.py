"""Root directory for tests."""
import os

from reflex import constants

os.environ[constants.PYTEST_CURRENT_TEST] = "true"
print("Gegining testing-------------\n")
print(constants.PYTEST_CURRENT_TEST in os.environ)
