"""The base for CustomBackendServer."""

from __future__ import annotations

import os
from abc import abstractmethod
from pathlib import Path

from reflex import constants
from reflex.base import Base
from reflex.constants.base import Env, LogLevel


class CustomBackendServer(Base):
    """BackendServer base."""

    @staticmethod
    def get_app_module(for_granian_target: bool = False, add_extra_api: bool = False):
        """Get the app module for the backend.

        Returns:
            The app module for the backend.
        """
        import reflex

        if for_granian_target:
            app_path = str(Path(reflex.__file__).parent / "app_module_for_backend.py")
        else:
            app_path = "reflex.app_module_for_backend"

        return f"{app_path}:{constants.CompileVars.APP}{f'.{constants.CompileVars.API}' if add_extra_api else ''}"

    def get_available_cpus(self) -> int:
        """Get available cpus."""
        return os.cpu_count() or 1

    def get_max_workers(self) -> int:
        """Get max workers."""
        # https://docs.gunicorn.org/en/latest/settings.html#workers
        return (os.cpu_count() or 1) * 4 + 1

    def get_recommended_workers(self) -> int:
        """Get recommended workers."""
        # https://docs.gunicorn.org/en/latest/settings.html#workers
        return (os.cpu_count() or 1) * 2 + 1

    def get_max_threads(self, wait_time_ms: int = 50, service_time_ms: int = 5) -> int:
        """Get max threads."""
        # https://engineering.zalando.com/posts/2019/04/how-to-set-an-ideal-thread-pool-size.html
        # Brian Goetz formula
        return int(self.get_available_cpus() * (1 + wait_time_ms / service_time_ms))

    def get_recommended_threads(
        self,
        target_reqs: int | None = None,
        wait_time_ms: int = 50,
        service_time_ms: int = 5,
    ) -> int:
        """Get recommended threads."""
        # https://engineering.zalando.com/posts/2019/04/how-to-set-an-ideal-thread-pool-size.html
        max_available_threads = self.get_max_threads()

        if target_reqs:
            # Little's law formula
            need_threads = target_reqs * (
                (wait_time_ms / 1000) + (service_time_ms / 1000)
            )
        else:
            need_threads = self.get_max_threads(wait_time_ms, service_time_ms)

        return int(
            max_available_threads
            if need_threads > max_available_threads
            else need_threads
        )

    @abstractmethod
    def check_import(self, extra: bool = False):
        """Check package importation."""
        raise NotImplementedError()

    @abstractmethod
    def setup(self, host: str, port: int, loglevel: LogLevel, env: Env):
        """Setup."""
        raise NotImplementedError()

    @abstractmethod
    def run_prod(self):
        """Run in production mode."""
        raise NotImplementedError()

    @abstractmethod
    def run_dev(self):
        """Run in development mode."""
        raise NotImplementedError()
