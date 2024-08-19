"""reflex.testing - tools for testing reflex apps."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import inspect
import os
import pathlib
import platform
import re
import signal
import socket
import socketserver
import subprocess
import textwrap
import threading
import time
import types
from http.server import SimpleHTTPRequestHandler
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)

import psutil
import uvicorn

import reflex
import reflex.reflex
import reflex.utils.build
import reflex.utils.exec
import reflex.utils.format
import reflex.utils.prerequisites
import reflex.utils.processes
from reflex.state import (
    BaseState,
    StateManagerMemory,
    StateManagerRedis,
    reload_state_module,
)

try:
    from selenium import webdriver  # pyright: ignore [reportMissingImports]
    from selenium.webdriver.remote.webdriver import (  # pyright: ignore [reportMissingImports]
        WebDriver,
    )

    if TYPE_CHECKING:
        from selenium.webdriver.common.options import (
            ArgOptions,  # pyright: ignore [reportMissingImports]
        )
        from selenium.webdriver.remote.webelement import (  # pyright: ignore [reportMissingImports]
            WebElement,
        )

    has_selenium = True
except ImportError:
    has_selenium = False

# The timeout (minutes) to check for the port.
DEFAULT_TIMEOUT = 15
POLL_INTERVAL = 0.25
FRONTEND_POPEN_ARGS = {}
T = TypeVar("T")
TimeoutType = Optional[Union[int, float]]

if platform.system() == "Windows":
    FRONTEND_POPEN_ARGS["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore
    FRONTEND_POPEN_ARGS["shell"] = True
else:
    FRONTEND_POPEN_ARGS["start_new_session"] = True


# borrowed from py3.11
class chdir(contextlib.AbstractContextManager):
    """Non thread-safe context manager to change the current working directory."""

    def __init__(self, path):
        """Prepare contextmanager.

        Args:
            path: the path to change to
        """
        self.path = path
        self._old_cwd = []

    def __enter__(self):
        """Save current directory and perform chdir."""
        self._old_cwd.append(os.getcwd())
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
    app_source: Optional[
        types.FunctionType | types.ModuleType | str | functools.partial[Any]
    ]
    app_path: pathlib.Path
    app_module_path: pathlib.Path
    app_module: Optional[types.ModuleType] = None
    app_instance: Optional[reflex.App] = None
    frontend_process: Optional[subprocess.Popen] = None
    frontend_url: Optional[str] = None
    frontend_output_thread: Optional[threading.Thread] = None
    backend_thread: Optional[threading.Thread] = None
    backend: Optional[uvicorn.Server] = None
    state_manager: Optional[StateManagerMemory | StateManagerRedis] = None
    _frontends: list["WebDriver"] = dataclasses.field(default_factory=list)
    _decorated_pages: list = dataclasses.field(default_factory=list)

    @classmethod
    def create(
        cls,
        root: pathlib.Path,
        app_source: Optional[
            types.FunctionType | types.ModuleType | str | functools.partial[Any]
        ] = None,
        app_name: Optional[str] = None,
    ) -> "AppHarness":
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
                raise ValueError(
                    "app_name must be provided when app_source is a string."
                )
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

    def get_full_state_name(self, path: List[str]) -> str:
        """Get the full state name for the given state class name.

        Args:
            path: A list of state class names

        Returns:
            The full state name
        """
        # NOTE: using State.get_name() somehow causes trouble here
        # path = [State.get_name()] + [self.get_state_name(p) for p in path]
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
        os.environ["TELEMETRY_ENABLED"] = ""  # disable telemetry reporting for tests
        self.app_path.mkdir(parents=True, exist_ok=True)
        if self.app_source is not None:
            app_globals = self._get_globals_from_signature(self.app_source)
            if isinstance(self.app_source, functools.partial):
                self.app_source = self.app_source.func  # type: ignore
            # get the source from a function or module object
            source_code = "\n".join(
                [
                    "\n".join(
                        self.get_app_global_source(k, v) for k, v in app_globals.items()
                    ),
                    self._get_source_from_app_source(self.app_source),
                ]
            )
            with chdir(self.app_path):
                reflex.reflex._init(
                    name=self.app_name,
                    template=reflex.constants.Templates.DEFAULT,
                    loglevel=reflex.constants.LogLevel.INFO,
                )
                self.app_module_path.write_text(source_code)
        with chdir(self.app_path):
            # ensure config and app are reloaded when testing different app
            reflex.config.get_config(reload=True)
            # Save decorated pages before importing the test app module
            before_decorated_pages = reflex.app.DECORATED_PAGES[self.app_name].copy()
            # Ensure the AppHarness test does not skip State assignment due to running via pytest
            os.environ.pop(reflex.constants.PYTEST_CURRENT_TEST, None)
            self.app_module = reflex.utils.prerequisites.get_compiled_app(
                # Do not reload the module for pre-existing apps (only apps generated from source)
                reload=self.app_source is not None
            )
            # Save the pages that were added during testing
            self._decorated_pages = [
                p
                for p in reflex.app.DECORATED_PAGES[self.app_name]
                if p not in before_decorated_pages
            ]
        self.app_instance = self.app_module.app
        if isinstance(self.app_instance._state_manager, StateManagerRedis):
            # Create our own redis connection for testing.
            self.state_manager = StateManagerRedis.create(self.app_instance.state)
        else:
            self.state_manager = self.app_instance._state_manager

    def _reload_state_module(self):
        """Reload the rx.State module to avoid conflict when reloading."""
        reload_state_module(module=f"{self.app_name}.{self.app_name}")

    def _get_backend_shutdown_handler(self):
        if self.backend is None:
            raise RuntimeError("Backend was not initialized.")

        original_shutdown = self.backend.shutdown

        async def _shutdown_redis(*args, **kwargs) -> None:
            # ensure redis is closed before event loop
            try:
                if self.app_instance is not None and isinstance(
                    self.app_instance.state_manager, StateManagerRedis
                ):
                    await self.app_instance.state_manager.close()
            except ValueError:
                pass
            await original_shutdown(*args, **kwargs)

        return _shutdown_redis

    def _start_backend(self, port=0):
        if self.app_instance is None:
            raise RuntimeError("App was not initialized.")
        self.backend = uvicorn.Server(
            uvicorn.Config(
                app=self.app_instance.api,
                host="127.0.0.1",
                port=port,
            )
        )
        self.backend.shutdown = self._get_backend_shutdown_handler()
        self.backend_thread = threading.Thread(target=self.backend.run)
        self.backend_thread.start()

    async def _reset_backend_state_manager(self):
        """Reset the StateManagerRedis event loop affinity.

        This is necessary when the backend is restarted and the state manager is a
        StateManagerRedis instance.
        """
        if (
            self.app_instance is not None
            and isinstance(
                self.app_instance.state_manager,
                StateManagerRedis,
            )
            and self.app_instance.state is not None
        ):
            with contextlib.suppress(RuntimeError):
                await self.app_instance.state_manager.close()
            self.app_instance._state_manager = StateManagerRedis.create(
                state=self.app_instance.state,
            )
            assert isinstance(self.app_instance.state_manager, StateManagerRedis)

    def _start_frontend(self):
        # Set up the frontend.
        with chdir(self.app_path):
            config = reflex.config.get_config()
            config.api_url = "http://{0}:{1}".format(
                *self._poll_for_servers().getsockname(),
            )
            reflex.utils.build.setup_frontend(self.app_path)

        # Start the frontend.
        self.frontend_process = reflex.utils.processes.new_process(
            [reflex.utils.prerequisites.get_package_manager(), "run", "dev"],
            cwd=self.app_path / reflex.utils.prerequisites.get_web_dir(),
            env={"PORT": "0"},
            **FRONTEND_POPEN_ARGS,
        )

    def _wait_frontend(self):
        while self.frontend_url is None:
            line = (
                self.frontend_process.stdout.readline()  # pyright: ignore [reportOptionalMemberAccess]
            )
            if not line:
                break
            print(line)  # for pytest diagnosis
            m = re.search(reflex.constants.Next.FRONTEND_LISTENING_REGEX, line)
            if m is not None:
                self.frontend_url = m.group(1)
                config = reflex.config.get_config()
                config.deploy_url = self.frontend_url
                break
        if self.frontend_url is None:
            raise RuntimeError("Frontend did not start")

        def consume_frontend_output():
            while True:
                line = (
                    self.frontend_process.stdout.readline()  # pyright: ignore [reportOptionalMemberAccess]
                )
                if not line:
                    break
                print(line)

        self.frontend_output_thread = threading.Thread(target=consume_frontend_output)
        self.frontend_output_thread.start()

    def start(self) -> "AppHarness":
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
    def get_app_global_source(key, value):
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

    def __enter__(self) -> "AppHarness":
        """Contextmanager protocol for `start()`.

        Returns:
            Instance of AppHarness after calling start()
        """
        return self.start()

    def stop(self) -> None:
        """Stop the frontend and backend servers."""
        self._reload_state_module()

        if self.backend is not None:
            self.backend.should_exit = True
        if self.frontend_process is not None:
            # https://stackoverflow.com/a/70565806
            frontend_children = psutil.Process(self.frontend_process.pid).children(
                recursive=True,
            )
            if platform.system() == "Windows":
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
        for driver in self._frontends:
            driver.quit()

        # Cleanup decorated pages added during testing
        for page in self._decorated_pages:
            reflex.app.DECORATED_PAGES[self.app_name].remove(page)

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
    ) -> T | bool:
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
            raise RuntimeError("Backend is not running.")
        backend = self.backend
        # check for servers to be initialized
        if not self._poll_for(
            target=lambda: getattr(backend, "servers", False),
            timeout=timeout,
        ):
            raise TimeoutError("Backend servers are not initialized.")
        # check for sockets to be listening
        if not self._poll_for(
            target=lambda: getattr(backend.servers[0], "sockets", False),
            timeout=timeout,
        ):
            raise TimeoutError("Backend is not listening.")
        return backend.servers[0].sockets[0]

    def frontend(
        self,
        driver_clz: Optional[Type["WebDriver"]] = None,
        driver_kwargs: dict[str, Any] | None = None,
        driver_options: ArgOptions | None = None,
        driver_option_args: List[str] | None = None,
        driver_option_capabilities: dict[str, Any] | None = None,
    ) -> "WebDriver":
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
            raise RuntimeError(
                "Frontend functionality requires `selenium` to be installed, "
                "and it could not be imported."
            )
        if self.frontend_url is None:
            raise RuntimeError("Frontend is not running.")
        want_headless = False
        if os.environ.get("APP_HARNESS_HEADLESS"):
            want_headless = True
        if driver_clz is None:
            requested_driver = os.environ.get("APP_HARNESS_DRIVER", "Chrome")
            driver_clz = getattr(webdriver, requested_driver)
            if driver_options is None:
                driver_options = getattr(webdriver, f"{requested_driver}Options")()
        if driver_clz is webdriver.Chrome:
            if driver_options is None:
                driver_options = webdriver.ChromeOptions()
            driver_options.add_argument("--class=AppHarness")
            if want_headless:
                driver_options.add_argument("--headless=new")
        elif driver_clz is webdriver.Firefox:
            if driver_options is None:
                driver_options = webdriver.FirefoxOptions()
            if want_headless:
                driver_options.add_argument("-headless")
        elif driver_clz is webdriver.Edge:
            if driver_options is None:
                driver_options = webdriver.EdgeOptions()
            if want_headless:
                driver_options.add_argument("headless")
        if driver_options is None:
            raise RuntimeError(f"Could not determine options for {driver_clz}")
        if args := os.environ.get("APP_HARNESS_DRIVER_ARGS"):
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
        driver = driver_clz(options=driver_options, **driver_kwargs)  # type: ignore
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
            raise RuntimeError("state_manager is not set.")
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
            raise RuntimeError("state_manager is not set.")
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
            raise RuntimeError("state_manager is not set.")
        if self.app_instance is None:
            raise RuntimeError("App is not running.")
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
        element: "WebElement",
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
            raise TimeoutError(
                f"{element} content remains {exp_not_equal!r} while polling.",
            )
        return element.text

    def poll_for_value(
        self,
        element: "WebElement",
        timeout: TimeoutType = None,
        exp_not_equal: str = "",
    ) -> Optional[str]:
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
        if not self._poll_for(
            target=lambda: element.get_attribute("value") != exp_not_equal,
            timeout=timeout,
        ):
            raise TimeoutError(
                f"{element} content remains {exp_not_equal!r} while polling.",
            )
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
        """
        if self.app_instance is None:
            raise RuntimeError("App is not running.")
        state_manager = self.app_instance.state_manager
        assert isinstance(
            state_manager, StateManagerMemory
        ), "Only works with memory state manager"
        if not self._poll_for(
            target=lambda: state_manager.states,
            timeout=timeout,
        ):
            raise TimeoutError("No states were observed while polling.")
        return state_manager.states


class SimpleHTTPRequestHandlerCustomErrors(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with custom error page handling."""

    def __init__(self, *args, error_page_map: dict[int, pathlib.Path], **kwargs):
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
        root: pathlib.Path,
        error_page_map: dict[int, pathlib.Path] | None,
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
            client_address: (host, port) referring to the client’s address.
        """
        self.RequestHandlerClass(
            request,
            client_address,
            self,
            directory=str(self.root),  # type: ignore
            error_page_map=self.error_page_map,  # type: ignore
        )


class AppHarnessProd(AppHarness):
    """AppHarnessProd executes a reflex app in-process for testing.

    In prod mode, instead of running `next dev` the app is exported as static
    files and served via the builtin python http.server with custom 404 redirect
    handling. Additionally, the backend runs in multi-worker mode.
    """

    frontend_thread: Optional[threading.Thread] = None
    frontend_server: Optional[Subdir404TCPServer] = None

    def _run_frontend(self):
        web_root = (
            self.app_path
            / reflex.utils.prerequisites.get_web_dir()
            / reflex.constants.Dirs.STATIC
        )
        error_page_map = {
            404: web_root / "404.html",
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
            config.api_url = "http://{0}:{1}".format(
                *self._poll_for_servers().getsockname(),
            )
            reflex.reflex.export(
                zipping=False,
                frontend=True,
                backend=False,
                loglevel=reflex.constants.LogLevel.INFO,
            )

        self.frontend_thread = threading.Thread(target=self._run_frontend)
        self.frontend_thread.start()

    def _wait_frontend(self):
        self._poll_for(lambda: self.frontend_server is not None)
        if self.frontend_server is None or not self.frontend_server.socket.fileno():
            raise RuntimeError("Frontend did not start")

    def _start_backend(self):
        if self.app_instance is None:
            raise RuntimeError("App was not initialized.")
        os.environ[reflex.constants.SKIP_COMPILE_ENV_VAR] = "yes"
        self.backend = uvicorn.Server(
            uvicorn.Config(
                app=self.app_instance,
                host="127.0.0.1",
                port=0,
                workers=reflex.utils.processes.get_num_workers(),
            ),
        )
        self.backend.shutdown = self._get_backend_shutdown_handler()
        self.backend_thread = threading.Thread(target=self.backend.run)
        self.backend_thread.start()

    def _poll_for_servers(self, timeout: TimeoutType = None) -> socket.socket:
        try:
            return super()._poll_for_servers(timeout)
        finally:
            os.environ.pop(reflex.constants.SKIP_COMPILE_ENV_VAR, None)

    def stop(self):
        """Stop the frontend python webserver."""
        super().stop()
        if self.frontend_server is not None:
            self.frontend_server.shutdown()
        if self.frontend_thread is not None:
            self.frontend_thread.join()
