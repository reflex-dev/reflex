"""reflex.testing - tools for testing reflex apps."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import inspect
import os
import platform
import re
import socket
import socketserver
import subprocess
import sys
import textwrap
import threading
import time
import types
from collections.abc import Callable, Coroutine, Sequence
from http.server import SimpleHTTPRequestHandler
from io import TextIOWrapper
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import reflex
import reflex.reflex
import reflex.utils.exec
import reflex.utils.format
import reflex.utils.prerequisites
import reflex.utils.processes
from reflex.components.component import CustomComponent
from reflex.config import get_config
from reflex.environment import environment
from reflex.state import (
    BaseState,
    StateManager,
    StateManagerDisk,
    StateManagerMemory,
    StateManagerRedis,
    reload_state_module,
)
from reflex.utils.export import export

try:
    from selenium import webdriver
    from selenium.webdriver.remote.webdriver import WebDriver

    if TYPE_CHECKING:
        from selenium.webdriver.common.options import ArgOptions
        from selenium.webdriver.remote.webelement import WebElement

    has_selenium = True
except ImportError:
    has_selenium = False

# The timeout (minutes) to check for the port.
DEFAULT_TIMEOUT = 15
POLL_INTERVAL = 0.25
FRONTEND_POPEN_ARGS = {}
T = TypeVar("T")
TimeoutType = int | float | None
if platform.system() == "Windows":
    FRONTEND_POPEN_ARGS["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # pyright: ignore [reportAttributeAccessIssue]
    FRONTEND_POPEN_ARGS["shell"] = True
else:
    FRONTEND_POPEN_ARGS["start_new_session"] = True


# borrowed from py3.11
class chdir(contextlib.AbstractContextManager):  # noqa: N801
    """Non thread-safe context manager to change the current working directory."""

    def __init__(self, path: str | Path):
        """Prepare contextmanager.

        Args:
            path: the path to change to
        """
        self.path = path
        self._old_cwd = []

    def __enter__(self):
        """Save current directory and perform chdir."""
        self._old_cwd.append(Path.cwd())
        os.chdir(self.path)

    def __exit__(self, *excinfo):
        """Change back to previous directory on stack.

        Args:
            excinfo: sys.exc_info captured in the context block
        """
        os.chdir(self._old_cwd.pop())


class ReflexProcessLoggedErrorError(RuntimeError):
    """Exception raised when the reflex process logs contain errors."""


class ReflexProcessExitNonZeroError(RuntimeError):
    """Exception raised when the reflex process exits with a non-zero status."""


def _is_port_responsive(port: int) -> bool:
    """Check if a port is responsive.

    Args:
        port: the port to check

    Returns:
        True if the port is responsive, False otherwise
    """
    try:
        with contextlib.closing(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ) as sock:
            return sock.connect_ex(("", port)) == 0
    except (OverflowError, PermissionError, OSError):
        return False


@dataclasses.dataclass
class AppHarness:
    """AppHarness executes a reflex app in-process for testing."""

    app_name: str
    app_source: (
        Callable[[], None] | types.ModuleType | str | functools.partial[Any] | None
    )
    app_path: Path
    app_module_path: Path
    app_module: types.ModuleType | None = None
    app_instance: reflex.App | None = None
    reflex_process: subprocess.Popen | None = None
    reflex_process_log_path: Path | None = None
    reflex_process_error_log_path: Path | None = None
    frontend_url: str | None = None
    backend_port: int | None = None
    frontend_port: int | None = None
    state_manager: StateManager | None = None
    _frontends: list[WebDriver] = dataclasses.field(default_factory=list)
    _reflex_process_log_fn: TextIOWrapper | None = None

    @classmethod
    def create(
        cls,
        root: Path,
        app_source: (
            Callable[[], None] | types.ModuleType | str | functools.partial[Any] | None
        ) = None,
        app_name: str | None = None,
    ) -> AppHarness:
        """Create an AppHarness instance at root.

        Args:
            root: the directory that will contain the app under test.
            app_source: if specified, the source code from this function or module is used
                as the main module for the app. It may also be the raw source code text, as a str.
                If unspecified, then root must already contain a working reflex app and will be used directly.
            app_name: provide the name of the app, otherwise will be derived from app_source or root.

        Raises:
            ValueError: when app_source is a string and app_name is not provided.

        Returns:
            AppHarness instance
        """
        if app_name is None:
            if app_source is None:
                app_name = root.name
            elif isinstance(app_source, functools.partial):
                keywords = app_source.keywords
                slug_suffix = "_".join([str(v) for v in keywords.values()])
                func_name = app_source.func.__name__
                app_name = f"{func_name}_{slug_suffix}"
                app_name = re.sub(r"[^a-zA-Z0-9_]", "_", app_name)
            elif isinstance(app_source, str):
                msg = "app_name must be provided when app_source is a string."
                raise ValueError(msg)
            else:
                app_name = app_source.__name__

            app_name = app_name.lower()
            while "__" in app_name:
                app_name = app_name.replace("__", "_")
        return cls(
            app_name=app_name,
            app_source=app_source,
            app_path=root,
            app_module_path=root / app_name / f"{app_name}.py",
        )

    def get_state_name(self, state_cls_name: str) -> str:
        """Get the state name for the given state class name.

        Args:
            state_cls_name: The state class name

        Returns:
            The state name
        """
        return reflex.utils.format.to_snake_case(
            f"{self.app_name}___{self.app_name}___" + state_cls_name
        )

    def get_full_state_name(self, path: list[str]) -> str:
        """Get the full state name for the given state class name.

        Args:
            path: A list of state class names

        Returns:
            The full state name
        """
        # NOTE: using State.get_name() somehow causes trouble here
        # path = [State.get_name()] + [self.get_state_name(p) for p in path] # noqa: ERA001
        path = ["reflex___state____state"] + [self.get_state_name(p) for p in path]
        return ".".join(path)

    def _get_globals_from_signature(self, func: Any) -> dict[str, Any]:
        """Get the globals from a function or module object.

        Args:
            func: function or module object

        Returns:
            dict of globals
        """
        overrides = {}
        glbs = {}
        if not callable(func):
            return glbs
        if isinstance(func, functools.partial):
            overrides = func.keywords
            func = func.func
        for param in inspect.signature(func).parameters.values():
            if param.default is not inspect.Parameter.empty:
                glbs[param.name] = param.default
        glbs.update(overrides)
        return glbs

    def _get_source_from_app_source(self, app_source: Any) -> str:
        """Get the source from app_source.

        Args:
            app_source: function or module or str

        Returns:
            source code
        """
        if isinstance(app_source, str):
            return app_source
        source = inspect.getsource(app_source)
        source = re.sub(
            r"^\s*def\s+\w+\s*\(.*?\)(\s+->\s+\w+)?:", "", source, flags=re.DOTALL
        )
        return textwrap.dedent(source)

    def _initialize_app(self):
        # disable telemetry reporting for tests

        os.environ["REFLEX_TELEMETRY_ENABLED"] = "false"
        CustomComponent.create().get_component.cache_clear()
        self.app_path.mkdir(parents=True, exist_ok=True)
        if self.app_source is not None:
            app_globals = self._get_globals_from_signature(self.app_source)
            if isinstance(self.app_source, functools.partial):
                self.app_source = self.app_source.func
            # get the source from a function or module object
            source_code = "\n".join(
                [
                    "\n".join(
                        self.get_app_global_source(k, v) for k, v in app_globals.items()
                    ),
                    self._get_source_from_app_source(self.app_source),
                ]
            )
            get_config().loglevel = reflex.constants.LogLevel.INFO
            with chdir(self.app_path):
                reflex.reflex._init(
                    name=self.app_name,
                    template=reflex.constants.Templates.DEFAULT,
                )
                self.app_module_path.write_text(source_code)
        else:
            # Just initialize the web folder.
            with chdir(self.app_path):
                reflex.utils.prerequisites.initialize_frontend_dependencies()
        with chdir(self.app_path):
            # ensure config and app are reloaded when testing different app
            reflex.config.get_config(reload=True)
            # Ensure the AppHarness test does not skip State assignment due to running via pytest
            os.environ.pop(reflex.constants.PYTEST_CURRENT_TEST, None)
            os.environ[reflex.constants.APP_HARNESS_FLAG] = "true"
            self.app_instance, self.app_module = (
                reflex.utils.prerequisites.get_and_validate_app(
                    # Do not reload the module for pre-existing apps (only apps generated from source)
                    reload=self.app_source is not None
                )
            )
            # Have to compile to ensure all state is available.
            _ = self.app_instance()
        self.state_manager = (
            self.app_instance._state_manager if self.app_instance else None
        )
        if isinstance(self.state_manager, StateManagerDisk):
            object.__setattr__(
                self.state_manager, "states_directory", self.app_path / ".states"
            )

    def _reload_state_module(self):
        """Reload the rx.State module to avoid conflict when reloading."""
        reload_state_module(module=f"{self.app_name}.{self.app_name}")

    def _start_subprocess(
        self, backend: bool = True, frontend: bool = True, mode: str = "dev"
    ):
        """Start the reflex app using subprocess instead of threads.

        Args:
            backend: Whether to start the backend server.
            frontend: Whether to start the frontend server.
            mode: The mode to run the app in (dev, prod, etc.).
        """
        self.reflex_process_log_path = self.app_path / "reflex.log"
        self.reflex_process_error_log_path = self.app_path / "reflex_error.log"
        self._reflex_process_log_fn = self.reflex_process_log_path.open("w")
        command = [
            sys.executable,
            "-u",
            "-m",
            "reflex",
            "run",
            "--env",
            mode,
            "--loglevel",
            "debug",
        ]
        if backend:
            if self.backend_port is None:
                self.backend_port = reflex.utils.processes.handle_port(
                    "backend", 48000, auto_increment=True
                )
            command.extend(["--backend-port", str(self.backend_port)])
            if not frontend:
                command.append("--backend-only")
        if frontend:
            if self.frontend_port is None:
                self.frontend_port = reflex.utils.processes.handle_port(
                    "frontend", 43000, auto_increment=True
                )
            command.extend(["--frontend-port", str(self.frontend_port)])
            if not backend:
                command.append("--frontend-only")
        self.reflex_process = subprocess.Popen(
            command,
            stdout=self._reflex_process_log_fn,
            stderr=self._reflex_process_log_fn,
            cwd=self.app_path,
            env={
                **os.environ,
                "REFLEX_ERROR_LOG_FILE": str(self.reflex_process_error_log_path),
                "PYTEST_CURRENT_TEST": "",
                "APP_HARNESS_FLAG": "true",
            },
        )
        self._wait_for_servers(backend=backend, frontend=frontend)

    def _wait_for_servers(self, backend: bool, frontend: bool):
        """Wait for both frontend and backend servers to be ready by parsing console output.

        Args:
            backend: Whether to wait for the backend server to be ready.
            frontend: Whether to wait for the frontend server to be ready.

        Raises:
            RuntimeError: If servers did not start properly.
        """
        if self.reflex_process is None or self.reflex_process.pid is None:
            msg = "Reflex process has no pid."
            raise RuntimeError(msg)

        if backend and self.backend_port is None:
            msg = "Backend port is not set."
            raise RuntimeError(msg)

        if frontend and self.frontend_port is None:
            msg = "Frontend port is not set."
            raise RuntimeError(msg)

        frontend_ready = False
        backend_ready = False

        while not ((not frontend or frontend_ready) and (not backend or backend_ready)):
            if backend and self.backend_port and _is_port_responsive(self.backend_port):
                backend_ready = True
            if (
                frontend
                and self.frontend_port
                and _is_port_responsive(self.frontend_port)
            ):
                frontend_ready = True

    async def _reset_backend_state_manager(self):
        """Reset the StateManagerRedis event loop affinity.

        This is necessary when the backend is restarted and the state manager is a
        StateManagerRedis instance.

        Raises:
            RuntimeError: when the state manager cannot be reset
        """
        if (
            self.app_instance is not None
            and isinstance(
                self.app_instance._state_manager,
                StateManagerRedis,
            )
            and self.app_instance._state is not None
        ):
            with contextlib.suppress(RuntimeError):
                await self.app_instance._state_manager.close()
            self.app_instance._state_manager = StateManagerRedis.create(
                state=self.app_instance._state,
            )
            if not isinstance(self.app_instance.state_manager, StateManagerRedis):
                msg = "Failed to reset state manager."
                raise RuntimeError(msg)

    def start(self) -> AppHarness:
        """Start the app using reflex run subprocess.

        Returns:
            self
        """
        self._initialize_app()
        self._start_subprocess()
        return self

    @staticmethod
    def get_app_global_source(key: str, value: Any):
        """Get the source code of a global object.
        If value is a function or class we render the actual
        source of value otherwise we assign value to key.

        Args:
            key: variable name to assign value to.
            value: value of the global variable.

        Returns:
            The rendered app global code.
        """
        if not inspect.isclass(value) and not inspect.isfunction(value):
            return f"{key} = {value!r}"
        return inspect.getsource(value)

    def __enter__(self) -> AppHarness:
        """Contextmanager protocol for `start()`.

        Returns:
            Instance of AppHarness after calling start()
        """
        return self.start()

    def stop(self) -> None:
        """Stop the reflex subprocess."""
        for driver in self._frontends:
            driver.quit()

        self._stop_reflex()
        self._reload_state_module()

    def _stop_reflex(self):
        returncode = None
        # Check if the process exited on its own or we have to kill it.
        if (
            self.reflex_process is not None
            and (returncode := self.reflex_process.poll()) is None
        ):
            try:
                # Kill server and children recursively.
                reflex.utils.exec.kill(self.reflex_process.pid)
            except (ProcessLookupError, OSError):
                pass
            finally:
                self.reflex_process = None
        if self._reflex_process_log_fn is not None:
            with contextlib.suppress(Exception):
                self._reflex_process_log_fn.close()
        if self.reflex_process_log_path is not None:
            print(self.reflex_process_log_path.read_text())  # noqa: T201  for pytest debugging
        # If there are errors in the logs, raise an exception.
        if (
            self.reflex_process_error_log_path is not None
            and self.reflex_process_error_log_path.exists()
        ):
            error_log_content = self.reflex_process_error_log_path.read_text()
            if error_log_content:
                msg = f"Reflex process error log contains errors:\n{error_log_content}"
                raise ReflexProcessLoggedErrorError(msg)
        # When the process exits non-zero, but wasn't killed, it is a test failure.
        if returncode is not None and returncode != 0:
            msg = (
                f"Reflex process exited with code {returncode}. "
                "Check the logs for more details."
            )
            raise ReflexProcessExitNonZeroError(msg)

    def __exit__(self, *excinfo) -> None:
        """Contextmanager protocol for `stop()`.

        Args:
            excinfo: sys.exc_info captured in the context block
        """
        self.stop()

    @staticmethod
    def _poll_for(
        target: Callable[[], T],
        timeout: TimeoutType = None,
        step: TimeoutType = None,
    ) -> T | Literal[False]:
        """Generic polling logic.

        Args:
            target: callable that returns truthy if polling condition is met.
            timeout: max polling time
            step: interval between checking target()

        Returns:
            return value of target() if truthy within timeout
            False if timeout elapses
        """
        if timeout is None:
            timeout = DEFAULT_TIMEOUT
        if step is None:
            step = POLL_INTERVAL
        deadline = time.time() + timeout
        while time.time() < deadline:
            with contextlib.suppress(Exception):
                success = target()
                if success:
                    return success
            time.sleep(step)
        return False

    @staticmethod
    async def _poll_for_async(
        target: Callable[[], Coroutine[None, None, T]],
        timeout: TimeoutType = None,
        step: TimeoutType = None,
    ) -> T | bool:
        """Generic polling logic for async functions.

        Args:
            target: callable that returns truthy if polling condition is met.
            timeout: max polling time
            step: interval between checking target()

        Returns:
            return value of target() if truthy within timeout
            False if timeout elapses
        """
        if timeout is None:
            timeout = DEFAULT_TIMEOUT
        if step is None:
            step = POLL_INTERVAL
        deadline = time.time() + timeout
        while time.time() < deadline:
            success = await target()
            if success:
                return success
            await asyncio.sleep(step)
        return False

    def frontend(
        self,
        driver_clz: type[WebDriver] | None = None,
        driver_kwargs: dict[str, Any] | None = None,
        driver_options: ArgOptions | None = None,
        driver_option_args: list[str] | None = None,
        driver_option_capabilities: dict[str, Any] | None = None,
    ) -> WebDriver:
        """Get a selenium webdriver instance pointed at the app.

        Args:
            driver_clz: webdriver.Chrome (default), webdriver.Firefox, webdriver.Safari,
                webdriver.Edge, etc
            driver_kwargs: additional keyword arguments to pass to the webdriver constructor
            driver_options: selenium ArgOptions instance to pass to the webdriver constructor
            driver_option_args: additional arguments for the webdriver options
            driver_option_capabilities: additional capabilities for the webdriver options

        Returns:
            Instance of the given webdriver navigated to the frontend url of the app.

        Raises:
            RuntimeError: when selenium is not importable or frontend is not running
        """
        if not has_selenium:
            msg = (
                "Frontend functionality requires `selenium` to be installed, "
                "and it could not be imported."
            )
            raise RuntimeError(msg)
        if self.frontend_url is None:
            msg = "Frontend is not running."
            raise RuntimeError(msg)
        want_headless = False
        if environment.APP_HARNESS_HEADLESS.get():
            want_headless = True
        if driver_clz is None:
            requested_driver = environment.APP_HARNESS_DRIVER.get()
            driver_clz = getattr(webdriver, requested_driver)  # pyright: ignore [reportPossiblyUnboundVariable]
            if driver_options is None:
                driver_options = getattr(webdriver, f"{requested_driver}Options")()  # pyright: ignore [reportPossiblyUnboundVariable]
        if driver_clz is webdriver.Chrome:  # pyright: ignore [reportPossiblyUnboundVariable]
            if driver_options is None:
                driver_options = webdriver.ChromeOptions()  # pyright: ignore [reportPossiblyUnboundVariable]
            driver_options.add_argument("--class=AppHarness")
            if want_headless:
                driver_options.add_argument("--headless=new")
        elif driver_clz is webdriver.Firefox:  # pyright: ignore [reportPossiblyUnboundVariable]
            if driver_options is None:
                driver_options = webdriver.FirefoxOptions()  # pyright: ignore [reportPossiblyUnboundVariable]
            if want_headless:
                driver_options.add_argument("-headless")
        elif driver_clz is webdriver.Edge:  # pyright: ignore [reportPossiblyUnboundVariable]
            if driver_options is None:
                driver_options = webdriver.EdgeOptions()  # pyright: ignore [reportPossiblyUnboundVariable]
            if want_headless:
                driver_options.add_argument("headless")
        if driver_options is None:
            msg = f"Could not determine options for {driver_clz}"
            raise RuntimeError(msg)
        if args := environment.APP_HARNESS_DRIVER_ARGS.get():
            for arg in args.split(","):
                driver_options.add_argument(arg)
        if driver_option_args is not None:
            for arg in driver_option_args:
                driver_options.add_argument(arg)
        if driver_option_capabilities is not None:
            for key, value in driver_option_capabilities.items():
                driver_options.set_capability(key, value)
        if driver_kwargs is None:
            driver_kwargs = {}
        driver = driver_clz(options=driver_options, **driver_kwargs)  # pyright: ignore [reportOptionalCall, reportArgumentType]
        driver.get(self.frontend_url)
        self._frontends.append(driver)
        return driver

    async def get_state(self, token: str) -> BaseState:
        """Get the state associated with the given token.

        Args:
            token: The state token to look up.

        Returns:
            The state instance associated with the given token

        Raises:
            AssertionError: when the state manager is not initialized
        """
        assert self.state_manager is not None, "State manager is not initialized."
        if isinstance(self.state_manager, StateManagerDisk):
            self.state_manager.states.clear()  # always reload from disk
        try:
            return await self.state_manager.get_state(token)
        finally:
            await self._reset_backend_state_manager()
            if isinstance(self.state_manager, StateManagerRedis):
                await self.state_manager.close()

    def poll_for_content(
        self,
        element: WebElement,
        timeout: TimeoutType = None,
        exp_not_equal: str = "",
    ) -> str:
        """Poll element.text for change.

        Args:
            element: selenium webdriver element to check
            timeout: how long to poll element.text
            exp_not_equal: exit the polling loop when the element text does not match

        Returns:
            The element text when the polling loop exited

        Raises:
            TimeoutError: when the timeout expires before text changes
        """
        if not self._poll_for(
            target=lambda: element.text != exp_not_equal,
            timeout=timeout,
        ):
            msg = f"{element} content remains {exp_not_equal!r} while polling."
            raise TimeoutError(msg)
        return element.text

    def poll_for_value(
        self,
        element: WebElement,
        timeout: TimeoutType = None,
        exp_not_equal: str | Sequence[str] = "",
    ) -> str | None:
        """Poll element.get_attribute("value") for change.

        Args:
            element: selenium webdriver element to check
            timeout: how long to poll element value attribute
            exp_not_equal: exit the polling loop when the value does not match

        Returns:
            The element value when the polling loop exited

        Raises:
            TimeoutError: when the timeout expires before value changes
        """
        exp_not_equal = (
            (exp_not_equal,) if isinstance(exp_not_equal, str) else exp_not_equal
        )
        if not self._poll_for(
            target=lambda: element.get_attribute("value") not in exp_not_equal,
            timeout=timeout,
        ):
            msg = f"{element} content remains {exp_not_equal!r} while polling."
            raise TimeoutError(msg)
        return element.get_attribute("value")

    def poll_for_clients(self, timeout: TimeoutType = None) -> dict[str, BaseState]:
        """Poll app state_manager for any connected clients.

        Args:
            timeout: how long to wait for client states

        Returns:
            active state instances when the polling loop exited

        Raises:
            RuntimeError: when the app hasn't started running
            TimeoutError: when the timeout expires before any states are seen
            ValueError: when the state_manager is not a memory state manager
        """
        if self.app_instance is None:
            msg = "App is not running."
            raise RuntimeError(msg)
        state_manager = self.app_instance.state_manager
        if not isinstance(state_manager, (StateManagerMemory, StateManagerDisk)):
            msg = "Only works with memory or disk state manager"
            raise ValueError(msg)
        if not self._poll_for(
            target=lambda: state_manager.states,
            timeout=timeout,
        ):
            msg = "No states were observed while polling."
            raise TimeoutError(msg)
        return state_manager.states

    @staticmethod
    def poll_for_or_raise_timeout(
        target: Callable[[], T],
        timeout: TimeoutType = None,
        step: TimeoutType = None,
    ) -> T:
        """Poll target callable for a truthy return value.

        Like `_poll_for`, but raises a `TimeoutError` if the target does not
        return a truthy value within the timeout.

        Args:
            target: callable that returns truthy if polling condition is met.
            timeout: max polling time
            step: interval between checking target()

        Returns:
            return value of target() if truthy within timeout

        Raises:
            TimeoutError: when target does not return a truthy value within timeout
        """
        result = AppHarness._poll_for(
            target=target,
            timeout=timeout,
            step=step,
        )
        if result is False:
            msg = "Target did not return a truthy value while polling."
            raise TimeoutError(msg)
        return result

    @staticmethod
    def expect(
        target: Callable[[], T],
        timeout: TimeoutType = None,
        step: TimeoutType = None,
    ):
        """Expect a target callable to return a truthy value within the timeout.

        Args:
            target: callable that returns truthy if polling condition is met.
            timeout: max polling time
            step: interval between checking target()
        """
        AppHarness.poll_for_or_raise_timeout(
            target=target,
            timeout=timeout,
            step=step,
        )


class SimpleHTTPRequestHandlerCustomErrors(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with custom error page handling."""

    def __init__(self, *args, error_page_map: dict[int, Path], **kwargs):
        """Initialize the handler.

        Args:
            error_page_map: map of error code to error page path
            *args: passed through to superclass
            **kwargs: passed through to superclass
        """
        self.error_page_map = error_page_map
        super().__init__(*args, **kwargs)

    def send_error(
        self, code: int, message: str | None = None, explain: str | None = None
    ) -> None:
        """Send the error page for the given error code.

        If the code matches a custom error page, then message and explain are
        ignored.

        Args:
            code: the error code
            message: the error message
            explain: the error explanation
        """
        error_page = self.error_page_map.get(code)
        if error_page:
            self.send_response(code, message)
            self.send_header("Connection", "close")
            body = error_page.read_bytes()
            self.send_header("Content-Type", self.error_content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().send_error(code, message, explain)


class Subdir404TCPServer(socketserver.TCPServer):
    """TCPServer for SimpleHTTPRequestHandlerCustomErrors that serves from a subdir."""

    def __init__(
        self,
        *args,
        root: Path,
        error_page_map: dict[int, Path] | None,
        **kwargs,
    ):
        """Initialize the server.

        Args:
            root: the root directory to serve from
            error_page_map: map of error code to error page path
            *args: passed through to superclass
            **kwargs: passed through to superclass
        """
        self.root = root
        self.error_page_map = error_page_map or {}
        super().__init__(*args, **kwargs)

    def finish_request(self, request: socket.socket, client_address: tuple[str, int]):
        """Finish one request by instantiating RequestHandlerClass.

        Args:
            request: the requesting socket
            client_address: (host, port) referring to the client's address.
        """
        self.RequestHandlerClass(
            request,
            client_address,
            self,
            directory=str(self.root),  # pyright: ignore [reportCallIssue]
            error_page_map=self.error_page_map,  # pyright: ignore [reportCallIssue]
        )


class AppHarnessProd(AppHarness):
    """AppHarnessProd executes a reflex app in-process for testing.

    In prod mode, instead of running `react-router dev` the app is exported as static
    files and served via the builtin python http.server with custom 404 redirect
    handling. Additionally, the backend runs in multi-worker mode.
    """

    frontend_thread: threading.Thread | None = None
    frontend_server: Subdir404TCPServer | None = None

    def _run_frontend(self):
        web_root = (
            self.app_path
            / reflex.utils.prerequisites.get_web_dir()
            / reflex.constants.Dirs.STATIC
        )
        error_page_map = {
            404: web_root / "404" / "index.html",
        }
        with Subdir404TCPServer(
            ("", 0),
            SimpleHTTPRequestHandlerCustomErrors,
            root=web_root,
            error_page_map=error_page_map,
        ) as self.frontend_server:
            self.frontend_url = "http://localhost:{1}/".format(
                *self.frontend_server.socket.getsockname()
            )
            self.frontend_server.serve_forever()

    def _start_frontend(self):
        # Set up the frontend.
        with chdir(self.app_path):
            config = reflex.config.get_config()
            config.api_url = f"http://localhost:{self.backend_port}"
            print("Building frontend...")  # for pytest diagnosis #noqa: T201

            get_config().loglevel = reflex.constants.LogLevel.INFO

            reflex.utils.prerequisites.assert_in_reflex_dir()

            if reflex.utils.prerequisites.needs_reinit():
                reflex.reflex._init(name=get_config().app_name)

            export(
                zipping=False,
                frontend=True,
                backend=False,
                loglevel=reflex.constants.LogLevel.INFO,
                env=reflex.constants.Env.PROD,
            )

        print("Frontend starting...")  # for pytest diagnosis #noqa: T201

        self.frontend_thread = threading.Thread(target=self._run_frontend)
        self.frontend_thread.start()

    def _wait_frontend(self):
        self._poll_for(lambda: self.frontend_server is not None)
        if self.frontend_server is None or not self.frontend_server.socket.fileno():
            msg = "Frontend did not start"
            raise RuntimeError(msg)

    def start(self) -> AppHarness:
        """Start the app using reflex run subprocess.

        Returns:
            self
        """
        self._initialize_app()
        self._start_subprocess(frontend=False, mode="prod")
        self._start_frontend()
        self._wait_frontend()
        return self

    def stop(self):
        """Stop the frontend python webserver."""
        super().stop()
        if self.frontend_server is not None:
            self.frontend_server.shutdown()
        if self.frontend_thread is not None:
            self.frontend_thread.join()
