"""reflex.testing - tools for testing reflex apps."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import dataclasses
import functools
import inspect
import logging
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import textwrap
import threading
import time
import types
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, TypeVar

from granian.constants import Interfaces
from granian.errors import FatalError
from granian.log import LogLevels
from granian.net import SocketHolder  # pyright: ignore[reportPrivateImportUsage]
from granian.server.embed import Server as EmbeddedGranian
from reflex_base.components.memo import MEMOS
from reflex_base.config import get_config, reload_config
from reflex_base.environment import environment
from reflex_base.registry import RegistrationContext
from reflex_base.utils import console
from reflex_base.utils.types import ASGIApp, Message, Receive, Scope, Send

import reflex
import reflex.reflex
import reflex.utils.build
import reflex.utils.exec
import reflex.utils.format
import reflex.utils.prerequisites
import reflex.utils.processes
from reflex.istate.shared import SharedState as SharedState  # To register it.
from reflex.state import reload_state_module
from reflex.utils import js_runtimes
from reflex.utils.exec import _with_development_condition
from reflex.utils.export import export
from reflex.utils.token_manager import TokenManager

logger = logging.getLogger(__name__)

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


class _PreboundGranian(EmbeddedGranian):
    """Embedded granian server serving a listening socket bound beforehand."""

    def __init__(self, listener: socket.socket, *args, **kwargs) -> None:
        """Create the server around a bound socket.

        Args:
            listener: the listening socket; granian owns it once serving starts.
            *args: positional arguments for the granian server.
            **kwargs: keyword arguments for the granian server.
        """
        super().__init__(*args, **kwargs)
        self._listener = listener

    def _init_shared_socket(self):
        """Hand the listening socket to granian instead of binding a new one."""
        fd = self._listener.detach()
        # SocketHolder takes its pickled state, whose shape differs per platform.
        if sys.platform == "win32":
            state = (fd,)
        elif sys.platform.startswith(("linux", "freebsd")):
            state = (fd, False, self.backlog)
        else:
            state = (fd, False)
        self._shd = SocketHolder(*state)
        self._sfd = fd

    def release_socket(self, served: bool) -> None:
        """Close the socket unless the worker serving it already did.

        Args:
            served: whether a worker took the socket over.
        """
        holder, self._shd = self._shd, None
        # Dropping the holder closes it on Windows, where workers serve a clone.
        if holder is not None and not served and sys.platform != "win32":
            os.close(self._sfd)


class _EmbeddedServer:
    """In-process granian server with a uvicorn-like control surface.

    Serves the given ASGI app object directly, so the harness shares the app
    and state instances with the running server. The listening socket is
    bound on construction, without SO_REUSEPORT, so the server owns its port
    (OS-assigned for port 0) before it serves.
    """

    def __init__(self, app: ASGIApp, host: str = "127.0.0.1", port: int = 0) -> None:
        """Bind the listening socket without serving yet.

        Args:
            app: the ASGI app object to serve.
            host: the address to bind to.
            port: the port to bind to; 0 lets the OS pick a free one.
        """
        self.app = app
        self.host = host
        self._listener = self._listen(host, port)
        self.port: int = self._listener.getsockname()[1]
        # Monkeypatchable async shutdown hook, mirroring uvicorn.Server.shutdown.
        self.shutdown: Callable[..., Coroutine[Any, Any, None]] = self._noop_shutdown
        self._should_exit = threading.Event()
        self._serving = False
        # Set once the server serves or stops.
        self._settled = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: _PreboundGranian | None = None

    @staticmethod
    def _listen(host: str, port: int) -> socket.socket:
        """Bind a listening socket that no other socket can share.

        Args:
            host: the address to bind to.
            port: the port to bind to.

        Returns:
            The listening socket.
        """
        sock = socket.socket()
        try:
            # On posix SO_REUSEADDR only allows rebinding a port in TIME_WAIT;
            # on Windows it would let other sockets share the port.
            sock.setsockopt(
                socket.SOL_SOCKET,
                getattr(socket, "SO_EXCLUSIVEADDRUSE", socket.SO_REUSEADDR),
                1,
            )
            sock.bind((host, port))
            sock.listen()
        except OSError:
            sock.close()
            raise
        return sock

    @staticmethod
    async def _noop_shutdown(*args, **kwargs) -> None:
        """Default shutdown hook.

        Args:
            *args: ignored.
            **kwargs: ignored.
        """

    def getsockname(self) -> tuple[str, int]:
        """The address the server is bound to.

        Returns:
            The (host, port) tuple the server serves on.
        """
        return (self.host, self.port)

    def wait_started(self, timeout: float | None = None) -> None:
        """Block until the server serves, after the app's lifespan startup.

        Args:
            timeout: how long to wait in seconds; None waits indefinitely.

        Raises:
            TimeoutError: when the server does not serve within the timeout.
            RuntimeError: when the server stopped without serving.
        """
        if not self._settled.wait(timeout):
            msg = f"Server on port {self.port} did not start within {timeout}s."
            raise TimeoutError(msg)
        if not self._serving:
            msg = f"Server on port {self.port} stopped without serving; see the log above."
            raise RuntimeError(msg)

    @property
    def started(self) -> bool:
        """Whether the server serves, like uvicorn's `Server.started`.

        Returns:
            True once the app's lifespan startup completed.
        """
        console.deprecate(
            feature_name="AppHarness.backend.started",
            reason="AppHarness.start() returns once the backend serves; "
            "call `wait_started()` to wait for a server yourself",
            deprecation_version="0.10.0",
            removal_version="1.0",
        )
        return self._serving

    @property
    def should_exit(self) -> bool:
        """Whether the server was asked to stop.

        Returns:
            True after `should_exit` has been set.
        """
        return self._should_exit.is_set()

    @should_exit.setter
    def should_exit(self, value: bool) -> None:
        if not value:
            return
        self._should_exit.set()
        loop, server = self._loop, self._server
        if loop is not None and server is not None:
            # A closed loop means the server is already down.
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(server.stop)

    def run(self) -> None:
        """Serve the app until `should_exit` is set; used as a thread target."""
        try:
            asyncio.run(self._serve())
        finally:
            # A no-op once granian took the socket over.
            self._listener.close()
            self._settled.set()

    def _mark_serving(self) -> None:
        """Record that the server serves."""
        self._serving = True
        self._settled.set()

    def _asgi(self, scope: Scope, receive: Receive, send: Send) -> Awaitable[None]:
        """Call the app, tracking its lifespan startup.

        Args:
            scope: the ASGI scope.
            receive: the ASGI receive callable.
            send: the ASGI send callable.

        Returns:
            The app's ASGI awaitable.
        """
        if scope["type"] == "lifespan":
            return self._lifespan(scope, receive, send)
        return self.app(scope, receive, send)

    async def _lifespan(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the app's lifespan, marking the server serving after startup.

        Args:
            scope: the ASGI lifespan scope.
            receive: the ASGI receive callable.
            send: the ASGI send callable.
        """
        failed = False

        async def tracking_send(message: Message) -> None:
            nonlocal failed
            await send(message)
            if message["type"] == "lifespan.startup.complete":
                self._mark_serving()
            elif message["type"] == "lifespan.startup.failed":
                failed = True

        try:
            await self.app(scope, receive, tracking_send)
        finally:
            # Like granian, serve without lifespan support unless startup failed.
            if not failed:
                self._mark_serving()

    async def _serve(self) -> None:
        server = _PreboundGranian(
            self._listener,
            self._asgi,
            address=self.host,
            port=self.port,
            interface=Interfaces.ASGI,
            # Keeps lifespan failures and unhandled app errors visible.
            log_level=LogLevels.error,
        )
        self._server = server
        self._loop = asyncio.get_running_loop()
        try:
            # A stop requested before this point found no server to interrupt.
            # A failed lifespan startup is logged by granian and reported by
            # wait_started().
            if not self._should_exit.is_set():
                with contextlib.suppress(FatalError):
                    await server.serve()
        finally:
            server.release_socket(served=self._serving)
            await self.shutdown()


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
    backend: _EmbeddedServer | None = None
    _frontends: list[WebDriver] = dataclasses.field(default_factory=list)
    _registry_token: contextvars.Token[RegistrationContext] | None = None
    _base_registration_context: ClassVar[RegistrationContext] | None = None

    @classmethod
    def create(
        cls,
        root: Path,
        app_source: (
            Callable[[], None] | types.ModuleType | str | functools.partial[Any] | None
        ) = None,
        app_name: str | None = None,
    ) -> Self:
        """Create an AppHarness instance at root.

        Args:
            root: the directory that will contain the app under test.
            app_source: if specified, the source code from this function or module is used
                as the main module for the app. It may also be the raw source code text, as a str.
                If unspecified, then root must already contain a working reflex app and will be used directly.
            app_name: provide the name of the app, otherwise will be derived from app_source or root.

        Returns:
            AppHarness instance

        Raises:
            ValueError: when app_source is a string and app_name is not provided.
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
        # Pin dev mode like `reflex run` does. A previous AppHarnessProd in
        # this process ran export(), which sets REFLEX_ENV_MODE=prod for the
        # whole process; compiling a dev app in leaked prod mode enables route
        # prerendering, so the dev server serves prerendered page HTML whose
        # hydration failures break event delivery (notably under vite >= 8.2).
        environment.REFLEX_ENV_MODE.set(reflex.constants.Env.DEV)
        # Reset the global memo registry so previous AppHarness apps do not
        # leak compiled component definitions into the next test app.
        MEMOS.clear()
        self.app_path.mkdir(parents=True, exist_ok=True)
        if self.app_source is not None:
            app_globals = self._get_globals_from_signature(self.app_source)
            if isinstance(self.app_source, functools.partial):
                self.app_source = self.app_source.func
            # get the source from a function or module object
            source_code = "\n".join([
                "\n".join([
                    self.get_app_global_source(k, v) for k, v in app_globals.items()
                ]),
                self._get_source_from_app_source(self.app_source),
            ])
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
            # Use a new registration context for a new app.
            if AppHarness._base_registration_context is None:
                # Save the initial RegistrationContext for the app if we haven't already
                AppHarness._base_registration_context = (
                    RegistrationContext.ensure_context()
                )
            new_registration_context = AppHarness._base_registration_context.fork()
            self._registry_token = RegistrationContext.set(new_registration_context)
            # ensure config and app are reloaded when testing different app
            config = reload_config()
            # Ensure the AppHarness test does not skip State assignment due to running via pytest
            os.environ.pop(reflex.constants.PYTEST_CURRENT_TEST, None)
            os.environ[reflex.constants.APP_HARNESS_FLAG] = "true"
            # Ensure we compile generated apps, and reload pre-existing app modules
            # that were already imported so they can re-register memo definitions.
            should_reload_app = (
                self.app_source is not None or config.module in sys.modules
            )
            self.app_instance, self.app_module = (
                reflex.utils.prerequisites.get_and_validate_app(
                    reload=should_reload_app
                )
            )
            self.app_asgi = self.app_instance()

    def _reload_state_module(self):
        """Forget the states of every module of the app's package, so they never reach the next app."""
        package = (
            self.app_module.__name__ if self.app_module else self.app_name
        ).partition(".")[0]
        prefix = f"{package}."
        for module in [
            name for name in sys.modules if name == package or name.startswith(prefix)
        ]:
            reload_state_module(module=module)

    def _get_backend_shutdown_handler(self):
        if self.backend is None:
            msg = "Backend was not initialized."
            raise RuntimeError(msg)

        original_shutdown = self.backend.shutdown

        async def _shutdown(*args, **kwargs) -> None:
            # ensure redis is closed before event loop
            if (
                self.app_instance is not None
                and self.app_instance._state_manager is not None
            ):
                with contextlib.suppress(ValueError):
                    await self.app_instance._state_manager.close()

            # socketio shutdown handler
            if self.app_instance is not None and self.app_instance.sio is not None:
                with contextlib.suppress(TypeError):
                    await self.app_instance.sio.shutdown()

            # sqlalchemy async engine shutdown handler
            if find_spec("sqlmodel"):
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
        self.backend = _EmbeddedServer(self.app_asgi, port=port)
        self.backend.shutdown = self._get_backend_shutdown_handler()

        def _run_backend(context: contextvars.Context) -> None:
            if self.backend is not None:
                context.run(self.backend.run)

        with chdir(self.app_path):
            print(  # noqa: T201
                "Creating backend in a new thread..."
            )  # for pytest diagnosis
            self.backend_thread = threading.Thread(
                target=_run_backend, args=(contextvars.copy_context(),)
            )
        self.backend_thread.start()
        print("Backend started.")  # for pytest diagnosis #noqa: T201

    def _start_frontend(self):
        # Set up the frontend.
        with chdir(self.app_path):
            config = get_config()
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
                *js_runtimes.get_js_package_executor(raise_on_none=True)[0],
                "run",
                "dev",
            ],
            cwd=self.app_path / reflex.utils.prerequisites.get_web_dir(),
            # The development condition lets react-router's dev CLI skip the
            # relaunch it otherwise needs to enable that condition.
            env=_with_development_condition({
                **os.environ,
                "PORT": "0",
                "NO_COLOR": "1",
            }),
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
                config = get_config()
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
                    logger.debug(str(e))
                    break
                if not line:
                    break

        self.frontend_output_thread = threading.Thread(target=consume_frontend_output)
        self.frontend_output_thread.start()

    def start(self) -> Self:
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
        if not isinstance(value, type) and not inspect.isfunction(value):
            return f"{key} = {value!r}"
        return inspect.getsource(value)

    def __enter__(self) -> Self:
        """Contextmanager protocol for `start()`.

        Returns:
            Instance of AppHarness after calling start()
        """
        return self.start()

    def stop(self) -> None:
        """Stop the frontend and backend servers."""
        try:
            import psutil
        except ImportError as exc:
            msg = (
                "AppHarness cleanup requires `psutil`. Install it with "
                "`pip install 'reflex[testing]'`."
            )
            raise ImportError(msg) from exc

        # Quit browsers first to avoid any lingering events being sent during shutdown.
        for driver in self._frontends:
            driver.quit()

        self._reload_state_module()
        if self._registry_token is not None:
            RegistrationContext.reset(self._registry_token)

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

    def _poll_for_servers(self, timeout: TimeoutType = None) -> _EmbeddedServer:
        """Wait for the backend server to serve.

        Args:
            timeout: how long to wait for the server.

        Returns:
            the backend server, exposing `getsockname()` for its bound address

        Raises:
            RuntimeError: when the backend hasn't started running, or stopped
                without serving
            TimeoutError: when the server is not ready
        """
        if self.backend is None:
            msg = "Backend is not running."
            raise RuntimeError(msg)
        self.backend.wait_started(DEFAULT_TIMEOUT if timeout is None else timeout)
        return self.backend

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
                from selenium.webdriver.chrome.options import Options

                driver_options = Options()  # pyright: ignore [reportPossiblyUnboundVariable]
            driver_options.add_argument("--class=AppHarness")
            if want_headless:
                driver_options.add_argument("--headless=new")
        elif driver_clz is webdriver.Firefox:  # pyright: ignore [reportPossiblyUnboundVariable]
            if driver_options is None:
                from selenium.webdriver.firefox.options import Options

                driver_options = Options()  # pyright: ignore [reportPossiblyUnboundVariable]
            if want_headless:
                driver_options.add_argument("-headless")
        elif driver_clz is webdriver.Edge:  # pyright: ignore [reportPossiblyUnboundVariable]
            if driver_options is None:
                from selenium.webdriver.edge.options import Options

                driver_options = Options()  # pyright: ignore [reportPossiblyUnboundVariable]
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

    def token_manager(self) -> TokenManager:
        """Get the token manager for the app instance.

        Returns:
            The current token_manager attached to the app's EventNamespace.
        """
        assert self.app_instance is not None
        app_event_namespace = self.app_instance.event_namespace
        assert app_event_namespace is not None
        app_token_manager = app_event_namespace._token_manager
        assert app_token_manager is not None
        return app_token_manager

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


class AppHarnessProd(AppHarness):
    """AppHarnessProd executes a reflex app in-process for testing.

    In prod mode, instead of running `react-router dev` the app is exported as static
    files and served via Starlette StaticFiles on a dedicated embedded server.
    """

    frontend_thread: threading.Thread | None = None
    frontend_server: _EmbeddedServer | None = None

    def _start_frontend(self):
        # Set up the frontend.
        with chdir(self.app_path):
            config = get_config()
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
            self.frontend_server = _EmbeddedServer(
                reflex.utils.exec._frontend_prod_app()
            )

        print("Frontend starting...")  # for pytest diagnosis #noqa: T201

        self.frontend_thread = threading.Thread(target=self.frontend_server.run)
        self.frontend_thread.start()

    def _wait_frontend(self):
        if self.frontend_server is None:
            msg = "Frontend did not start"
            raise RuntimeError(msg)
        self.frontend_server.wait_started(DEFAULT_TIMEOUT)
        config = get_config()
        self.frontend_url = "http://{}:{}".format(
            *self.frontend_server.getsockname()
        ) + config.prepend_frontend_path("/")
        config.deploy_url = self.frontend_url

    def _start_backend(self):
        if self.app_asgi is None:
            msg = "App was not initialized."
            raise RuntimeError(msg)
        environment.REFLEX_SKIP_COMPILE.set(True)
        self.backend = _EmbeddedServer(self.app_asgi)
        self.backend.shutdown = self._get_backend_shutdown_handler()

        def _run_backend(context: contextvars.Context) -> None:
            if self.backend is not None:
                context.run(self.backend.run)

        print(  # noqa: T201
            "Creating backend in a new thread..."
        )
        self.backend_thread = threading.Thread(
            target=_run_backend, args=(contextvars.copy_context(),)
        )
        self.backend_thread.start()
        print("Backend started.")  # for pytest diagnosis #noqa: T201

    def _poll_for_servers(self, timeout: TimeoutType = None) -> _EmbeddedServer:
        try:
            return super()._poll_for_servers(timeout)
        finally:
            environment.REFLEX_SKIP_COMPILE.set(None)

    def stop(self):
        """Stop the frontend and backend servers."""
        if self.frontend_server is not None:
            self.frontend_server.should_exit = True
        super().stop()
        if self.frontend_thread is not None:
            self.frontend_thread.join()
