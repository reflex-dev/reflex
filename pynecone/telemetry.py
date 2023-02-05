"""Anonymous telemetry for Pynecone."""

import multiprocessing
import platform

import psutil

from pynecone import constants
from pynecone.base import Base


class Telemetry(Base):
    """Anonymous telemetry for Pynecone."""

    user_os: str = ""
    cpu_count: int = 0
    memory: int = 0
    pynecone_version: str = ""
    python_version: str = ""

    def get_os(self) -> None:
        """Get the operating system."""
        self.user_os = platform.system()

    def get_python_version(self) -> None:
        """Get the Python version."""
        self.python_version = platform.python_version()

    def get_pynecone_version(self) -> None:
        """Get the Pynecone version."""
        self.pynecone_version = constants.VERSION

    def get_cpu_count(self) -> None:
        """Get the number of CPUs."""
        self.cpu_count = multiprocessing.cpu_count()

    def get_memory(self) -> None:
        """Get the total memory in MB."""
        self.memory = psutil.virtual_memory().total >> 20
