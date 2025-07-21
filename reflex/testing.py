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
import signal
import socket
import socketserver
import subprocess
import sys
import textwrap
import threading
import time
import types
from collections.abc import AsyncIterator, Callable, Coroutine, Sequence
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import uvicorn

import reflex
import reflex.environment
import reflex.reflex
import reflex.utils.build
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
from reflex.utils import console
from reflex.utils.export import export
from reflex.utils.types import ASGIApp

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
    app_asgi: ASGIApp | None = None
    frontend_process: subprocess.Popen | None = None
    frontend_url: str | None = None
    frontend_output_thread: threading.Thread | None = None
    backend_thread: threading.Thread | None = None
    backend: uvicorn.Server | None = None
    state_manager: StateManager | None = None
    _frontends: list[WebDriver] = dataclasses.field(default_factory=list)

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
            # Ensure we actually compile the app during first initialization.
            self.app_instance, self.app_module = (
                reflex.utils.prerequisites.get_and_validate_app(
                    # Do not reload the module for pre-existing apps (only apps generated from source)
                    reload=self.app_source is not None
                )
            )
            self.app_asgi = self.app_instance()
        if self.app_instance and isinstance(
            self.app_instance._state_manager, StateManagerRedis
        ):
            if self.app_instance._state is None:
                msg = "State is not set."
                raise RuntimeError(msg)
            # Create our own redis connection for testing.
            self.state_manager = StateManagerRedis.create(self.app_instance._state)
        else:
            self.state_manager = (
                self.app_instance._state_manager if self.app_instance else None
            )

    def _reload_state_module(self):
        """Reload the rx.State module to avoid conflict when reloading."""
        reload_state_module(module=f"{self.app_name}.{self.app_name}")

    def _get_backend_shutdown_handler(self):
        if self.backend is None:
            msg = "Backend was not initialized."
            raise RuntimeError(msg)

        original_shutdown = self.backend.shutdown

        async def _shutdown(*args, **kwargs) -> None:
            # ensure redis is closed before event loop
            if self.app_instance is not None and isinstance(
                self.app_instance._state_manager, StateManagerRedis
            ):
                with contextlib.suppress(ValueError):
                    await self.app_instance._state_manager.close()

            # socketio shutdown handler
            if self.app_instance is not None and self.app_instance.sio is not None:
                with contextlib.suppress(TypeError):
                    await self.app_instance.sio.shutdown()

            # sqlalchemy async engine shutdown handler
            try:
                async_engine = reflex.model.get_async_engine(None)
            except ValueError:
                pass
            else:
                await async_engine.dispose()

            await original_shutdown(*args, **kwargs)

        return _shutdown

    def _start_backend(self, port: int = 0):
        if self.app_asgi is None:
            msg = "App was not initialized."
            raise RuntimeError(msg)
        self.backend = uvicorn.Server(
            uvicorn.Config(
                app=self.app_asgi,
                host="127.0.0.1",
                port=port,
            )
        )
        self.backend.shutdown = self._get_backend_shutdown_handler()
        with chdir(self.app_path):
            print(  # noqa: T201
                "Creating backend in a new thread..."
            )  # for pytest diagnosis
            self.backend_thread = threading.Thread(target=self.backend.run)
        self.backend_thread.start()
        print("Backend started.")  # for pytest diagnosis #noqa: T201

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

    def _start_frontend(self):
        # Set up the frontend.
        with chdir(self.app_path):
            config = reflex.config.get_config()
            print("Polling for servers...")  # for pytest diagnosis #noqa: T201
            config.api_url = "http://{}:{}".format(
                *self._poll_for_servers(timeout=30).getsockname(),
            )
            print("Building frontend...")  # for pytest diagnosis #noqa: T201
            reflex.utils.build.setup_frontend(self.app_path)

        print("Frontend starting...")  # for pytest diagnosis #noqa: T201

        # Start the frontend.
        self.frontend_process = reflex.utils.processes.new_process(
            [
                *reflex.utils.prerequisites.get_js_package_executor(raise_on_none=True)[
                    0
                ],
                "run",
                "dev",
            ],
            cwd=self.app_path / reflex.utils.prerequisites.get_web_dir(),
            env={"PORT": "0", "NO_COLOR": "1"},
            **FRONTEND_POPEN_ARGS,
        )

    def _wait_frontend(self):
        if self.frontend_process is None or self.frontend_process.stdout is None:
            msg = "Frontend process has no stdout."
            raise RuntimeError(msg)
        while self.frontend_url is None:
            line = self.frontend_process.stdout.readline()
            if not line:
                break
            print(line)  # for pytest diagnosis #noqa: T201
            m = re.search(reflex.constants.ReactRouter.FRONTEND_LISTENING_REGEX, line)
            if m is not None:
                self.frontend_url = m.group(1)
                config = reflex.config.get_config()
                config.deploy_url = self.frontend_url
                break
        if self.frontend_url is None:
            msg = "Frontend did not start"
            raise RuntimeError(msg)

        def consume_frontend_output():
            while True:
                try:
                    line = (
                        self.frontend_process.stdout.readline()  # pyright: ignore [reportOptionalMemberAccess]
                    )
                # catch I/O operation on closed file.
                except ValueError as e:
                    console.error(str(e))
                    break
                if not line:
                    break

        self.frontend_output_thread = threading.Thread(target=consume_frontend_output)
        self.frontend_output_thread.start()

    def start(self) -> AppHarness:
        """Start the backend in a new thread and dev frontend as a separate process.

        Returns:
            self
        """
        self._initialize_app()
        self._start_backend()
        self._start_frontend()
        self._wait_frontend()
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
        """Stop the frontend and backend servers."""
        import psutil

        # Quit browsers first to avoid any lingering events being sent during shutdown.
        for driver in self._frontends:
            driver.quit()

        self._reload_state_module()

        if self.backend is not None:
            self.backend.should_exit = True
        if self.frontend_process is not None:
            # https://stackoverflow.com/a/70565806
            frontend_children = psutil.Process(self.frontend_process.pid).children(
                recursive=True,
            )
            if sys.platform == "win32":
                self.frontend_process.terminate()
            else:
                pgrp = os.getpgid(self.frontend_process.pid)
                os.killpg(pgrp, signal.SIGTERM)
            # kill any remaining child processes
            for child in frontend_children:
                # It's okay if the process is already gone.
                with contextlib.suppress(psutil.NoSuchProcess):
                    child.terminate()
            _, still_alive = psutil.wait_procs(frontend_children, timeout=3)
            for child in still_alive:
                # It's okay if the process is already gone.
                with contextlib.suppress(psutil.NoSuchProcess):
                    child.kill()
            # wait for main process to exit
            self.frontend_process.communicate()
        if self.backend_thread is not None:
            self.backend_thread.join()
        if self.frontend_output_thread is not None:
            self.frontend_output_thread.join()

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

    def _poll_for_servers(self, timeout: TimeoutType = None) -> socket.socket:
        """Poll backend server for listening sockets.

        Args:
            timeout: how long to wait for listening socket.

        Returns:
            first active listening socket on the backend

        Raises:
            RuntimeError: when the backend hasn't started running
            TimeoutError: when server or sockets are not ready
        """
        if self.backend is None:
            msg = "Backend is not running."
            raise RuntimeError(msg)
        backend = self.backend
        # check for servers to be initialized
        if not self._poll_for(
            target=lambda: getattr(backend, "servers", False),
            timeout=timeout,
        ):
            msg = "Backend servers are not initialized."
            raise TimeoutError(msg)
        # check for sockets to be listening
        if not self._poll_for(
            target=lambda: getattr(backend.servers[0], "sockets", False),
            timeout=timeout,
        ):
            msg = "Backend is not listening."
            raise TimeoutError(msg)
        return backend.servers[0].sockets[0]

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
            RuntimeError: when the app hasn't started running
        """
        if self.state_manager is None:
            msg = "state_manager is not set."
            raise RuntimeError(msg)
        try:
            return await self.state_manager.get_state(token)
        finally:
            if isinstance(self.state_manager, StateManagerRedis):
                await self.state_manager.close()

    async def set_state(self, token: str, **kwargs) -> None:
        """Set the state associated with the given token.

        Args:
            token: The state token to set.
            kwargs: Attributes to set on the state.

        Raises:
            RuntimeError: when the app hasn't started running
        """
        if self.state_manager is None:
            msg = "state_manager is not set."
            raise RuntimeError(msg)
        state = await self.get_state(token)
        for key, value in kwargs.items():
            setattr(state, key, value)
        try:
            await self.state_manager.set_state(token, state)
        finally:
            if isinstance(self.state_manager, StateManagerRedis):
                await self.state_manager.close()

    @contextlib.asynccontextmanager
    async def modify_state(self, token: str) -> AsyncIterator[BaseState]:
        """Modify the state associated with the given token and send update to frontend.

        Args:
            token: The state token to modify

        Yields:
            The state instance associated with the given token

        Raises:
            RuntimeError: when the app hasn't started running
        """
        if self.state_manager is None:
            msg = "state_manager is not set."
            raise RuntimeError(msg)
        if self.app_instance is None:
            msg = "App is not running."
            raise RuntimeError(msg)
        app_state_manager = self.app_instance.state_manager
        if isinstance(self.state_manager, StateManagerRedis):
            # Temporarily replace the app's state manager with our own, since
            # the redis connection is on the backend_thread event loop
            self.app_instance._state_manager = self.state_manager
        try:
            async with self.app_instance.modify_state(token) as state:
                yield state
        finally:
            if isinstance(self.state_manager, StateManagerRedis):
                self.app_instance._state_manager = app_state_manager
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
            self.frontend_url = "http://localhost:{1}".format(
                *self.frontend_server.socket.getsockname()
            )
            self.frontend_server.serve_forever()

    def _start_frontend(self):
        # Set up the frontend.
        with chdir(self.app_path):
            config = reflex.config.get_config()
            print("Polling for servers...")  # for pytest diagnosis #noqa: T201
            config.api_url = "http://{}:{}".format(
                *self._poll_for_servers(timeout=30).getsockname(),
            )
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

    def _start_backend(self):
        if self.app_asgi is None:
            msg = "App was not initialized."
            raise RuntimeError(msg)
        environment.REFLEX_SKIP_COMPILE.set(True)
        self.backend = uvicorn.Server(
            uvicorn.Config(
                app=self.app_asgi,
                host="127.0.0.1",
                port=0,
                workers=reflex.utils.processes.get_num_workers(),
            ),
        )
        self.backend.shutdown = self._get_backend_shutdown_handler()
        print(  # noqa: T201
            "Creating backend in a new thread..."
        )
        self.backend_thread = threading.Thread(target=self.backend.run)
        self.backend_thread.start()
        print("Backend started.")  # for pytest diagnosis #noqa: T201

    def _poll_for_servers(self, timeout: TimeoutType = None) -> socket.socket:
        try:
            return super()._poll_for_servers(timeout)
        finally:
            environment.REFLEX_SKIP_COMPILE.set(None)

    def stop(self):
        """Stop the frontend python webserver."""
        super().stop()
        if self.frontend_server is not None:
            self.frontend_server.shutdown()
        if self.frontend_thread is not None:
            self.frontend_thread.join()
