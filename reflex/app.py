"""The main Reflex app."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import copy
import dataclasses
import functools
import inspect
import io
import json
import operator
import sys
import time
import traceback
import urllib.parse
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Coroutine,
    Mapping,
    Sequence,
)
from datetime import datetime
from itertools import chain
from pathlib import Path
from timeit import default_timer as timer
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, BinaryIO, ParamSpec, get_args, get_type_hints

from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn
from socketio import ASGIApp as EngineIOApp
from socketio import AsyncNamespace, AsyncServer
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.exceptions import HTTPException
from starlette.middleware import cors
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.staticfiles import StaticFiles

from reflex import constants
from reflex.admin import AdminDash
from reflex.app_mixins import AppMixin, LifespanMixin, MiddlewareMixin
from reflex.compiler import compiler
from reflex.compiler import utils as compiler_utils
from reflex.compiler.compiler import (
    ExecutorSafeFunctions,
    compile_theme,
    readable_name_from_component,
)
from reflex.components.base.app_wrap import AppWrap
from reflex.components.base.error_boundary import ErrorBoundary
from reflex.components.base.fragment import Fragment
from reflex.components.base.strict_mode import StrictMode
from reflex.components.component import (
    CUSTOM_COMPONENTS,
    Component,
    ComponentStyle,
    evaluate_style_namespaces,
)
from reflex.components.core.banner import (
    backend_disabled,
    connection_pulser,
    connection_toaster,
)
from reflex.components.core.breakpoints import set_breakpoints
from reflex.components.core.sticky import sticky
from reflex.components.radix import themes
from reflex.components.sonner.toast import toast
from reflex.config import get_config
from reflex.environment import ExecutorType, environment
from reflex.event import (
    _EVENT_FIELDS,
    Event,
    EventHandler,
    EventSpec,
    EventType,
    IndividualEventType,
    get_hydrate_event,
    noop,
)
from reflex.page import DECORATED_PAGES
from reflex.route import (
    get_route_args,
    replace_brackets_with_keywords,
    verify_route_validity,
)
from reflex.state import (
    BaseState,
    RouterData,
    State,
    StateManager,
    StateUpdate,
    _split_substate_key,
    _substate_key,
    all_base_state_classes,
    code_uses_state_contexts,
)
from reflex.utils import (
    codespaces,
    console,
    exceptions,
    format,
    frontend_skeleton,
    js_runtimes,
    path_ops,
    prerequisites,
    types,
)
from reflex.utils.exec import (
    get_compile_context,
    is_prod_mode,
    is_testing_env,
    should_prerender_routes,
)
from reflex.utils.imports import ImportVar
from reflex.utils.misc import run_in_thread
from reflex.utils.token_manager import RedisTokenManager, TokenManager
from reflex.utils.types import ASGIApp, Message, Receive, Scope, Send

if TYPE_CHECKING:
    from reflex.vars import Var

    # Define custom types.
    ComponentCallable = Callable[[], Component | tuple[Component, ...] | str | Var]
else:
    ComponentCallable = Callable[[], Component | tuple[Component, ...] | str]

Reducer = Callable[[Event], Coroutine[Any, Any, StateUpdate]]


def default_frontend_exception_handler(exception: Exception) -> None:
    """Default frontend exception handler function.

    Args:
        exception: The exception.

    """
    console.error(f"[Reflex Frontend Exception]\n {exception}\n")


def default_backend_exception_handler(exception: Exception) -> EventSpec:
    """Default backend exception handler function.

    Args:
        exception: The exception.

    Returns:
        EventSpec: The window alert event.

    """
    from reflex.components.sonner.toast import toast

    error = traceback.format_exc()

    console.error(f"[Reflex Backend Exception]\n {error}\n")

    error_message = (
        ["Contact the website administrator."]
        if is_prod_mode()
        else [f"{type(exception).__name__}: {exception}.", "See logs for details."]
    )

    return toast(
        "An error occurred.",
        level="error",
        fallback_to_alert=True,
        description="<br/>".join(error_message),
        position="top-center",
        id="backend_error",
        style={"width": "500px"},
    )


def extra_overlay_function() -> Component | None:
    """Extra overlay function to add to the overlay component.

    Returns:
        The extra overlay function.
    """
    config = get_config()

    extra_config = config.extra_overlay_function
    config_overlay = None
    if extra_config:
        module, _, function_name = extra_config.rpartition(".")
        try:
            module = __import__(module)
            config_overlay = Fragment.create(getattr(module, function_name)())
            config_overlay._get_all_imports()
        except Exception as e:
            from reflex.compiler.utils import save_error

            log_path = save_error(e)

            console.error(
                f"Error loading extra_overlay_function {extra_config}. Error saved to {log_path}"
            )

    return config_overlay


def default_overlay_component() -> Component:
    """Default overlay_component attribute for App.

    Returns:
        The default overlay_component, which is a connection_modal.
    """
    from reflex.components.component import memo

    def default_overlay_components():
        return Fragment.create(
            connection_pulser(),
            connection_toaster(),
            *(
                [backend_disabled()]
                if get_compile_context() == constants.CompileContext.DEPLOY
                else []
            ),
            *codespaces.codespaces_auto_redirect(),
        )

    return Fragment.create(memo(default_overlay_components)())


def default_error_boundary(*children: Component, **props) -> Component:
    """Default error_boundary attribute for App.

    Args:
        *children: The children to render in the error boundary.
        **props: The props to pass to the error boundary.

    Returns:
        The default error_boundary, which is an ErrorBoundary.

    """
    return ErrorBoundary.create(
        *children,
        **props,
    )


@dataclasses.dataclass(frozen=True)
class UploadFile(StarletteUploadFile):
    """A file uploaded to the server.

    Args:
        file: The standard Python file object (non-async).
        filename: The original file name.
        size: The size of the file in bytes.
        headers: The headers of the request.
    """

    file: BinaryIO

    path: Path | None = dataclasses.field(default=None)

    size: int | None = dataclasses.field(default=None)

    headers: Headers = dataclasses.field(default_factory=Headers)

    @property
    def filename(self) -> str | None:
        """Get the name of the uploaded file.

        Returns:
            The name of the uploaded file.
        """
        return self.name

    @property
    def name(self) -> str | None:
        """Get the name of the uploaded file.

        Returns:
            The name of the uploaded file.
        """
        if self.path:
            return self.path.name
        return None


@dataclasses.dataclass(
    frozen=True,
)
class UnevaluatedPage:
    """An uncompiled page."""

    component: Component | ComponentCallable
    route: str
    title: Var | str | None
    description: Var | str | None
    image: str
    on_load: EventType[()] | None
    meta: Sequence[Mapping[str, str]]
    context: Mapping[str, Any]

    def merged_with(self, other: UnevaluatedPage) -> UnevaluatedPage:
        """Merge the other page into this one.

        Args:
            other: The other page to merge with.

        Returns:
            The merged page.
        """
        return dataclasses.replace(
            self,
            title=self.title if self.title is not None else other.title,
            description=self.description
            if self.description is not None
            else other.description,
            on_load=self.on_load if self.on_load is not None else other.on_load,
            context=self.context if self.context is not None else other.context,
        )


P = ParamSpec("P")


@dataclasses.dataclass()
class App(MiddlewareMixin, LifespanMixin):
    """The main Reflex app that encapsulates the backend and frontend.

    Every Reflex app needs an app defined in its main module.

    ```python
    # app.py
    import reflex as rx

    # Define state and pages
    ...

    app = rx.App(
        # Set global level style.
        style={...},
        # Set the top level theme.
        theme=rx.theme(accent_color="blue"),
    )
    ```
    """

    # The global [theme](https://reflex.dev/docs/styling/theming/#theme) for the entire app.
    theme: Component | None = dataclasses.field(
        default_factory=lambda: themes.theme(accent_color="blue")
    )

    # The [global style](https://reflex.dev/docs/styling/overview/#global-styles}) for the app.
    style: ComponentStyle = dataclasses.field(default_factory=dict)

    # A list of URLs to [stylesheets](https://reflex.dev/docs/styling/custom-stylesheets/) to include in the app.
    stylesheets: list[str] = dataclasses.field(default_factory=list)

    # Whether to include CSS reset for margin and padding (defaults to True).
    reset_style: bool = dataclasses.field(default=True)

    # A component that is present on every page (defaults to the Connection Error banner).
    overlay_component: Component | ComponentCallable | None = dataclasses.field(
        default=None
    )

    # App wraps to be applied to the whole app. Expected to be a dictionary of (order, name) to a function that takes whether the state is enabled and optionally returns a component.
    app_wraps: dict[tuple[int, str], Callable[[bool], Component | None]] = (
        dataclasses.field(
            default_factory=lambda: {
                (55, "ErrorBoundary"): (
                    lambda stateful: default_error_boundary(
                        **({"on_error": noop()} if not stateful else {})
                    )
                ),
                (5, "Overlay"): (
                    lambda stateful: default_overlay_component() if stateful else None
                ),
                (4, "ExtraOverlay"): lambda stateful: extra_overlay_function(),
            }
        )
    )

    # Extra app wraps to be applied to the whole app.
    extra_app_wraps: dict[tuple[int, str], Callable[[bool], Component | None]] = (
        dataclasses.field(default_factory=dict)
    )

    # Components to add to the head of every page.
    head_components: list[Component] = dataclasses.field(default_factory=list)

    # The Socket.IO AsyncServer instance.
    sio: AsyncServer | None = None

    # The language to add to the html root tag of every page.
    html_lang: str | None = None

    # Attributes to add to the html root tag of every page.
    html_custom_attrs: dict[str, str] | None = None

    # A map from a route to an unevaluated page.
    _unevaluated_pages: dict[str, UnevaluatedPage] = dataclasses.field(
        default_factory=dict
    )

    # A map from a page route to the component to render. Users should use `add_page`.
    _pages: dict[str, Component] = dataclasses.field(default_factory=dict)

    # A mapping of pages which created states as they were being evaluated.
    _stateful_pages: dict[str, None] = dataclasses.field(default_factory=dict)

    # The backend API object.
    _api: Starlette | None = None

    # The state class to use for the app.
    _state: type[BaseState] | None = None

    # Whether to enable state for the app. If False, the app will not use state.
    enable_state: bool = True

    # Class to manage many client states.
    _state_manager: StateManager | None = None

    # Mapping from a route to event handlers to trigger when the page loads.
    _load_events: dict[str, list[IndividualEventType[()]]] = dataclasses.field(
        default_factory=dict
    )

    # Admin dashboard to view and manage the database.
    admin_dash: AdminDash | None = None

    # The async server name space.
    _event_namespace: EventNamespace | None = None

    # Background tasks that are currently running.
    _background_tasks: set[asyncio.Task] = dataclasses.field(default_factory=set)

    # Frontend Error Handler Function
    frontend_exception_handler: Callable[[Exception], None] = (
        default_frontend_exception_handler
    )

    # Backend Error Handler Function
    backend_exception_handler: Callable[
        [Exception], EventSpec | list[EventSpec] | None
    ] = default_backend_exception_handler

    # Put the toast provider in the app wrap.
    toaster: Component | None = dataclasses.field(default_factory=toast.provider)

    # Transform the ASGI app before running it.
    api_transformer: (
        Sequence[Callable[[ASGIApp], ASGIApp] | Starlette]
        | Callable[[ASGIApp], ASGIApp]
        | Starlette
        | None
    ) = None

    @property
    def event_namespace(self) -> EventNamespace | None:
        """Get the event namespace.

        Returns:
            The event namespace.
        """
        return self._event_namespace

    def __post_init__(self):
        """Initialize the app.

        Raises:
            ValueError: If the event namespace is not provided in the config.
                        Also, if there are multiple client subclasses of rx.BaseState(Subclasses of rx.BaseState should consist
                        of the DefaultState and the client app state).
        """
        # Special case to allow test cases have multiple subclasses of rx.BaseState.
        if not is_testing_env() and BaseState.__subclasses__() != [State]:
            # Only rx.State is allowed as Base State subclass.
            msg = "rx.BaseState cannot be subclassed directly. Use rx.State instead"
            raise ValueError(msg)

        get_config(reload=True)

        if "breakpoints" in self.style:
            set_breakpoints(self.style.pop("breakpoints"))

        # Set up the API.
        self._api = Starlette()
        App._add_cors(self._api)
        self._add_default_endpoints()

        for clz in App.__mro__:
            if clz == App:
                continue
            if issubclass(clz, AppMixin):
                clz._init_mixin(self)

        if self.enable_state:
            self._enable_state()

        # Set up the admin dash.
        self._setup_admin_dash()

        if sys.platform == "win32" and not is_prod_mode():
            # Hack to fix Windows hot reload issue.
            from reflex.utils.compat import windows_hot_reload_lifespan_hack

            self.register_lifespan_task(windows_hot_reload_lifespan_hack)

    def _enable_state(self) -> None:
        """Enable state for the app."""
        if not self._state:
            self._state = State
        self._setup_state()

    def _setup_state(self) -> None:
        """Set up the state for the app.

        Raises:
            RuntimeError: If the socket server is invalid.
        """
        if not self._state:
            return

        config = get_config()

        # Set up the state manager.
        self._state_manager = StateManager.create(state=self._state)

        # Set up the Socket.IO AsyncServer.
        if not self.sio:
            self.sio = AsyncServer(
                async_mode="asgi",
                cors_allowed_origins=(
                    (
                        "*"
                        if config.cors_allowed_origins == ("*",)
                        else list(config.cors_allowed_origins)
                    )
                    if config.transport == "websocket"
                    else []
                ),
                cors_credentials=config.transport == "websocket",
                max_http_buffer_size=environment.REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE.get(),
                ping_interval=environment.REFLEX_SOCKET_INTERVAL.get(),
                ping_timeout=environment.REFLEX_SOCKET_TIMEOUT.get(),
                json=SimpleNamespace(
                    dumps=staticmethod(format.json_dumps),
                    loads=staticmethod(json.loads),
                ),
                allow_upgrades=False,
                transports=[config.transport],
            )
        elif getattr(self.sio, "async_mode", "") != "asgi":
            msg = f"Custom `sio` must use `async_mode='asgi'`, not '{self.sio.async_mode}'."
            raise RuntimeError(msg)

        # Create the socket app. Note event endpoint constant replaces the default 'socket.io' path.
        socket_app = EngineIOApp(self.sio, socketio_path="")
        namespace = config.get_event_namespace()

        # Create the event namespace and attach the main app. Not related to any paths.
        self._event_namespace = EventNamespace(namespace, self)

        # Register the event namespace with the socket.
        self.sio.register_namespace(self.event_namespace)
        # Mount the socket app with the API.
        if self._api:

            class HeaderMiddleware:
                def __init__(self, app: ASGIApp):
                    self.app = app

                async def __call__(self, scope: Scope, receive: Receive, send: Send):
                    original_send = send

                    async def modified_send(message: Message):
                        if message["type"] == "websocket.accept":
                            if scope.get("subprotocols"):
                                # The following *does* say "subprotocol" instead of "subprotocols", intentionally.
                                message["subprotocol"] = scope["subprotocols"][0]

                            headers = dict(message.get("headers", []))
                            header_key = b"sec-websocket-protocol"
                            if subprotocol := headers.get(header_key):
                                message["headers"] = [
                                    *message.get("headers", []),
                                    (header_key, subprotocol),
                                ]

                        return await original_send(message)

                    return await self.app(scope, receive, modified_send)

            socket_app_with_headers = HeaderMiddleware(socket_app)
            self._api.mount(str(constants.Endpoint.EVENT), socket_app_with_headers)

        # Check the exception handlers
        self._validate_exception_handlers()

    def __repr__(self) -> str:
        """Get the string representation of the app.

        Returns:
            The string representation of the app.
        """
        return f"<App state={self._state.__name__ if self._state else None}>"

    def __call__(self) -> ASGIApp:
        """Run the backend api instance.

        Raises:
            ValueError: If the app has not been initialized.

        Returns:
            The backend api.
        """
        from reflex.vars.base import GLOBAL_CACHE

        self._compile(prerender_routes=should_prerender_routes())

        config = get_config()

        for plugin in config.plugins:
            plugin.post_compile(app=self)

        # We will not be making more vars, so we can clear the global cache to free up memory.
        GLOBAL_CACHE.clear()

        if not self._api:
            msg = "The app has not been initialized."
            raise ValueError(msg)

        asgi_app = self._api

        if environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP.get():
            asgi_app.mount(
                "/" + config.frontend_path.strip("/"),
                StaticFiles(
                    directory=prerequisites.get_web_dir()
                    / constants.Dirs.STATIC
                    / config.frontend_path.strip("/"),
                    html=True,
                ),
                name="frontend",
            )

        if self.api_transformer is not None:
            api_transformers: Sequence[Starlette | Callable[[ASGIApp], ASGIApp]] = (
                [self.api_transformer]
                if not isinstance(self.api_transformer, Sequence)
                else self.api_transformer
            )

            for api_transformer in api_transformers:
                if isinstance(api_transformer, Starlette):
                    # Mount the api to the starlette app.
                    App._add_cors(api_transformer)
                    api_transformer.mount("", asgi_app)
                    asgi_app = api_transformer
                else:
                    # Transform the asgi app.
                    asgi_app = api_transformer(asgi_app)

        top_asgi_app = Starlette(lifespan=self._run_lifespan_tasks)
        top_asgi_app.mount("", asgi_app)
        App._add_cors(top_asgi_app)

        return top_asgi_app

    def _add_default_endpoints(self):
        """Add default api endpoints (ping)."""
        # To test the server.
        if not self._api:
            return

        self._api.add_route(
            str(constants.Endpoint.PING),
            ping,
            methods=["GET"],
        )
        self._api.add_route(
            str(constants.Endpoint.HEALTH),
            health,
            methods=["GET"],
        )

    def _add_optional_endpoints(self):
        """Add optional api endpoints (_upload)."""
        from reflex.components.core.upload import Upload, get_upload_dir

        if not self._api:
            return
        upload_is_used_marker = (
            prerequisites.get_backend_dir() / constants.Dirs.UPLOAD_IS_USED
        )
        if Upload.is_used or upload_is_used_marker.exists():
            # To upload files.
            self._api.add_route(
                str(constants.Endpoint.UPLOAD),
                upload(self),
                methods=["POST"],
            )

            # To access uploaded files.
            self._api.mount(
                str(constants.Endpoint.UPLOAD),
                StaticFiles(directory=get_upload_dir()),
                name="uploaded_files",
            )

            upload_is_used_marker.parent.mkdir(parents=True, exist_ok=True)
            upload_is_used_marker.touch()
        if codespaces.is_running_in_codespaces():
            self._api.add_route(
                str(constants.Endpoint.AUTH_CODESPACE),
                codespaces.auth_codespace,
                methods=["GET"],
            )
        if environment.REFLEX_ADD_ALL_ROUTES_ENDPOINT.get():
            self.add_all_routes_endpoint()

    @staticmethod
    def _add_cors(api: Starlette):
        """Add CORS middleware to the app.

        Args:
            api: The Starlette app to add CORS middleware to.
        """
        api.add_middleware(
            cors.CORSMiddleware,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            allow_origins=get_config().cors_allowed_origins,
        )

    @property
    def state_manager(self) -> StateManager:
        """Get the state manager.

        Returns:
            The initialized state manager.

        Raises:
            ValueError: if the state has not been initialized.
        """
        if self._state_manager is None:
            msg = "The state manager has not been initialized."
            raise ValueError(msg)
        return self._state_manager

    @staticmethod
    def _generate_component(component: Component | ComponentCallable) -> Component:
        """Generate a component from a callable.

        Args:
            component: The component function to call or Component to return as-is.

        Returns:
            The generated component.
        """
        from reflex.compiler.compiler import into_component

        return into_component(component)

    def add_page(
        self,
        component: Component | ComponentCallable | None = None,
        route: str | None = None,
        title: str | Var | None = None,
        description: str | Var | None = None,
        image: str = constants.DefaultPage.IMAGE,
        on_load: EventType[()] | None = None,
        meta: list[dict[str, str]] = constants.DefaultPage.META_LIST,
        context: dict[str, Any] | None = None,
    ):
        """Add a page to the app.

        If the component is a callable, by default the route is the name of the
        function. Otherwise, a route must be provided.

        Args:
            component: The component to display at the page.
            route: The route to display the component at.
            title: The title of the page.
            description: The description of the page.
            image: The image to display on the page.
            on_load: The event handler(s) that will be called each time the page load.
            meta: The metadata of the page.
            context: Values passed to page for custom page-specific logic.

        Raises:
            PageValueError: When the component is not set for a non-404 page.
            RouteValueError: When the specified route name already exists.
        """
        # If the route is not set, get it from the callable.
        if route is None:
            if not isinstance(component, Callable):
                msg = "Route must be set if component is not a callable."
                raise exceptions.RouteValueError(msg)
            # Format the route.
            route = format.format_route(format.to_kebab_case(component.__name__))
        else:
            route = format.format_route(route)

        if route == constants.Page404.SLUG:
            if component is None:
                from reflex.components.el.elements import span

                component = span("404: Page not found")
            component = self._generate_component(component)
            title = title or constants.Page404.TITLE
            description = description or constants.Page404.DESCRIPTION
            image = image or constants.Page404.IMAGE
        else:
            if component is None:
                msg = "Component must be set for a non-404 page."
                raise exceptions.PageValueError(msg)

        # Check if the route given is valid
        verify_route_validity(route)

        unevaluated_page = UnevaluatedPage(
            component=component,
            route=route,
            title=title,
            description=description,
            image=image,
            on_load=on_load,
            meta=meta,
            context=context or {},
        )

        if route in self._unevaluated_pages:
            if self._unevaluated_pages[route].component is component:
                unevaluated_page = unevaluated_page.merged_with(
                    self._unevaluated_pages[route]
                )
                console.warn(
                    f"Page {route} is being redefined with the same component."
                )
            else:
                route_name = (
                    f"`{route}` or `/`"
                    if route == constants.PageNames.INDEX_ROUTE
                    else f"`{route}`"
                )
                existing_component = self._unevaluated_pages[route].component
                msg = (
                    f"Tried to add page {readable_name_from_component(component)} with route {route_name} but "
                    f"page {readable_name_from_component(existing_component)} with the same route already exists. "
                    "Make sure you do not have two pages with the same route."
                )
                raise exceptions.RouteValueError(msg)

        # Setup dynamic args for the route.
        # this state assignment is only required for tests using the deprecated state kwarg for App
        state = self._state or State
        state.setup_dynamic_args(get_route_args(route))

        self._load_events[route] = (
            (on_load if isinstance(on_load, list) else [on_load])
            if on_load is not None
            else []
        )

        self._unevaluated_pages[route] = unevaluated_page

    def _compile_page(self, route: str, save_page: bool = True):
        """Compile a page.

        Args:
            route: The route of the page to compile.
            save_page: If True, the compiled page is saved to self._pages.
        """
        n_states_before = len(all_base_state_classes)
        component = compiler.compile_unevaluated_page(
            route, self._unevaluated_pages[route], self.style, self.theme
        )

        # Indicate that evaluating this page creates one or more state classes.
        if len(all_base_state_classes) > n_states_before:
            self._stateful_pages[route] = None

        # Add the page.
        self._check_routes_conflict(route)
        if save_page:
            self._pages[route] = component

    @functools.cached_property
    def router(self) -> Callable[[str], str | None]:
        """Get the route computer function.

        Returns:
            The route computer function.
        """
        from reflex.route import get_router

        return get_router(list(dict.fromkeys([*self._unevaluated_pages, *self._pages])))

    def get_load_events(self, path: str) -> list[IndividualEventType[()]]:
        """Get the load events for a route.

        Args:
            path: The route to get the load events for.

        Returns:
            The load events for the route.
        """
        four_oh_four_load_events = self._load_events.get("404", [])
        route = self.router(path)
        if not route:
            # If the path is not a valid route, return the 404 page load events.
            return four_oh_four_load_events
        return self._load_events.get(
            route,
            four_oh_four_load_events,
        )

    def _check_routes_conflict(self, new_route: str):
        """Verify if there is any conflict between the new route and any existing route.

        Based on conflicts that React Router would throw if not intercepted.

        Raises:
            RouteValueError: exception showing which conflict exist with the route to be added

        Args:
            new_route: the route being newly added.
        """
        from reflex.utils.exceptions import RouteValueError

        if "[" not in new_route:
            return

        segments = (
            constants.RouteRegex.SINGLE_SEGMENT,
            constants.RouteRegex.DOUBLE_SEGMENT,
            constants.RouteRegex.DOUBLE_CATCHALL_SEGMENT,
        )
        for route in self._pages:
            replaced_route = replace_brackets_with_keywords(route)
            for rw, r, nr in zip(
                replaced_route.split("/"),
                route.split("/"),
                new_route.split("/"),
                strict=False,
            ):
                if rw in segments and r != nr:
                    # If the slugs in the segments of both routes are not the same, then the route is invalid
                    msg = f"You cannot use different slug names for the same dynamic path in  {route} and {new_route} ('{r}' != '{nr}')"
                    raise RouteValueError(msg)
                if rw not in segments and r != nr:
                    # if the section being compared in both routes is not a dynamic segment(i.e not wrapped in brackets)
                    # then we are guaranteed that the route is valid and there's no need checking the rest.
                    # eg. /posts/[id]/info/[slug1] and /posts/[id]/info1/[slug1] is always going to be valid since
                    # info1 will break away into its own tree.
                    break

    def _setup_admin_dash(self):
        """Setup the admin dash."""
        try:
            from starlette_admin.contrib.sqla.admin import Admin
            from starlette_admin.contrib.sqla.view import ModelView

            from reflex.model import Model
        except ImportError:
            return

        # Get the admin dash.
        if not self._api:
            return

        admin_dash = self.admin_dash

        if admin_dash and admin_dash.models:
            # Build the admin dashboard
            admin = admin_dash.admin or Admin(
                engine=Model.get_db_engine(),
                title="Reflex Admin Dashboard",
                logo_url="https://reflex.dev/Reflex.svg",
            )

            for model in admin_dash.models:
                view = admin_dash.view_overrides.get(model, ModelView)
                admin.add_view(view(model))

            admin.mount_to(self._api)

    def _get_frontend_packages(self, imports: dict[str, set[ImportVar]]):
        """Gets the frontend packages to be installed and filters out the unnecessary ones.

        Args:
            imports: A dictionary containing the imports used in the current page.

        Example:
            >>> _get_frontend_packages({"react": "16.14.0", "react-dom": "16.14.0"})
        """
        dependencies = constants.PackageJson.DEPENDENCIES
        dev_dependencies = constants.PackageJson.DEV_DEPENDENCIES
        page_imports = {
            i
            for i, tags in imports.items()
            if i not in dependencies
            and i not in dev_dependencies
            and not any(i.startswith(prefix) for prefix in ["/", "$/", "."])
            and i != ""
            and any(tag.install for tag in tags)
        }
        pinned = {i.rpartition("@")[0] for i in page_imports if "@" in i}
        page_imports = {i for i in page_imports if i not in pinned}

        frontend_packages = get_config().frontend_packages
        filtered_frontend_packages = []
        for package in frontend_packages:
            if package in page_imports:
                console.warn(
                    f"React packages and their dependencies are inferred from Component.library and Component.lib_dependencies, remove `{package}` from `frontend_packages`"
                )
                continue
            filtered_frontend_packages.append(package)
        page_imports.update(filtered_frontend_packages)
        js_runtimes.install_frontend_packages(page_imports, get_config())

    def _app_root(self, app_wrappers: dict[tuple[int, str], Component]) -> Component:
        for component in tuple(app_wrappers.values()):
            app_wrappers.update(component._get_all_app_wrap_components())
        order = sorted(app_wrappers, key=operator.itemgetter(0), reverse=True)
        root = copy.deepcopy(app_wrappers[order[0]])

        def reducer(parent: Component, key: tuple[int, str]) -> Component:
            child = copy.deepcopy(app_wrappers[key])
            parent.children.append(child)
            return child

        functools.reduce(
            lambda parent, key: reducer(parent, key),
            order[1:],
            root,
        )
        return root

    def _should_compile(self) -> bool:
        """Check if the app should be compiled.

        Returns:
            Whether the app should be compiled.
        """
        # Check the environment variable.
        if environment.REFLEX_SKIP_COMPILE.get():
            return False

        nocompile = prerequisites.get_web_dir() / constants.NOCOMPILE_FILE

        # Check the nocompile file.
        if nocompile.exists():
            # Delete the nocompile file
            nocompile.unlink(missing_ok=True)
            return False

        # By default, compile the app.
        return True

    def _add_overlay_to_component(
        self, component: Component, overlay_component: Component
    ) -> Component:
        children = component.children

        if children[0] == overlay_component:
            return component

        return Fragment.create(overlay_component, *children)

    def _setup_overlay_component(self):
        """If a State is not used and no overlay_component is specified, do not render the connection modal."""
        if self.overlay_component is None:
            return
        console.deprecate(
            feature_name="overlay_component",
            reason="Use `extra_app_wraps` to add the overlay component instead.",
            deprecation_version="0.8.2",
            removal_version="0.9.0",
        )
        overlay_component = self._generate_component(self.overlay_component)
        for k, component in self._pages.items():
            self._pages[k] = self._add_overlay_to_component(
                component, overlay_component
            )

    def _setup_sticky_badge(self):
        """Add the sticky badge to the app."""
        from reflex.components.component import memo

        @memo
        def memoized_badge():
            sticky_badge = sticky()
            sticky_badge._add_style_recursive({})
            return sticky_badge

        self.app_wraps[0, "StickyBadge"] = lambda _: memoized_badge()

    def _apply_decorated_pages(self):
        """Add @rx.page decorated pages to the app."""
        app_name = get_config().app_name
        for render, kwargs in DECORATED_PAGES[app_name]:
            self.add_page(render, **kwargs)

    def _validate_var_dependencies(self, state: type[BaseState] | None = None) -> None:
        """Validate the dependencies of the vars in the app.

        Args:
            state: The state to validate the dependencies for.

        Raises:
            VarDependencyError: When a computed var has an invalid dependency.
        """
        if not self._state:
            return

        if not state:
            state = self._state

        for var in state.computed_vars.values():
            if not var._cache:
                continue
            deps = var._deps(objclass=state)
            for state_name, dep_set in deps.items():
                state_cls = (
                    state.get_root_state().get_class_substate(state_name)
                    if state_name != state.get_full_name()
                    else state
                )
                for dep in dep_set:
                    if dep not in state_cls.vars and dep not in state_cls.backend_vars:
                        msg = f"ComputedVar {var._name} on state {state.__name__} has an invalid dependency {state_name}.{dep}"
                        raise exceptions.VarDependencyError(msg)

        for substate in state.class_subclasses:
            self._validate_var_dependencies(substate)

    def _compile(
        self,
        prerender_routes: bool = False,
        dry_run: bool = False,
        use_rich: bool = True,
    ):
        """Compile the app and output it to the pages folder.

        Args:
            prerender_routes: Whether to prerender the routes.
            dry_run: Whether to compile the app without saving it.
            use_rich: Whether to use rich progress bars.

        Raises:
            ReflexRuntimeError: When any page uses state, but no rx.State subclass is defined.
            FileNotFoundError: When a plugin requires a file that does not exist.
        """
        from reflex.utils.exceptions import ReflexRuntimeError

        self._apply_decorated_pages()

        self._pages = {}

        def get_compilation_time() -> str:
            return str(datetime.now().time()).split(".")[0]

        should_compile = self._should_compile()
        backend_dir = prerequisites.get_backend_dir()
        if not dry_run and not should_compile and backend_dir.exists():
            stateful_pages_marker = backend_dir / constants.Dirs.STATEFUL_PAGES
            if stateful_pages_marker.exists():
                with stateful_pages_marker.open("r") as f:
                    stateful_pages = json.load(f)
                for route in stateful_pages:
                    console.debug(f"BE Evaluating stateful page: {route}")
                    self._compile_page(route, save_page=False)
            self._add_optional_endpoints()
            return

        # Render a default 404 page if the user didn't supply one
        if constants.Page404.SLUG not in self._unevaluated_pages:
            self.add_page(route=constants.Page404.SLUG)

        # Fix up the style.
        self.style = evaluate_style_namespaces(self.style)

        # Add the app wrappers.
        app_wrappers: dict[tuple[int, str], Component] = {
            # Default app wrap component renders {children}
            (0, "AppWrap"): AppWrap.create()
        }

        if self.theme is not None:
            # If a theme component was provided, wrap the app with it
            app_wrappers[20, "Theme"] = self.theme

        # Get the env mode.
        config = get_config()

        if config.react_strict_mode:
            app_wrappers[200, "StrictMode"] = StrictMode.create()

        if not should_compile and not dry_run:
            with console.timing("Evaluate Pages (Backend)"):
                for route in self._unevaluated_pages:
                    console.debug(f"Evaluating page: {route}")
                    self._compile_page(route, save_page=should_compile)

            # Save the pages which created new states at eval time.
            self._write_stateful_pages_marker()

            # Add the optional endpoints (_upload)
            self._add_optional_endpoints()

            return

        # Create a progress bar.
        progress = (
            Progress(
                *Progress.get_default_columns()[:-1],
                MofNCompleteColumn(),
                TimeElapsedColumn(),
            )
            if use_rich
            else console.PoorProgress()
        )

        # try to be somewhat accurate - but still not 100%
        adhoc_steps_without_executor = 7
        fixed_pages_within_executor = 4
        plugin_count = len(config.plugins)
        progress.start()
        task = progress.add_task(
            f"[{get_compilation_time()}] Compiling:",
            total=len(self._unevaluated_pages)
            + ((len(self._unevaluated_pages) + len(self._pages)) * 3)
            + fixed_pages_within_executor
            + adhoc_steps_without_executor
            + plugin_count,
        )

        with console.timing("Evaluate Pages (Frontend)"):
            performance_metrics: list[tuple[str, float]] = []
            for route in self._unevaluated_pages:
                console.debug(f"Evaluating page: {route}")
                start = timer()
                self._compile_page(route, save_page=should_compile)
                end = timer()
                performance_metrics.append((route, end - start))
                progress.advance(task)
            console.debug(
                "Slowest pages:\n"
                + "\n".join(
                    f"{route}: {time * 1000:.1f}ms"
                    for route, time in sorted(
                        performance_metrics, key=operator.itemgetter(1), reverse=True
                    )[:10]
                )
            )
            # Save the pages which created new states at eval time.
            self._write_stateful_pages_marker()

        # Add the optional endpoints (_upload)
        self._add_optional_endpoints()

        self._validate_var_dependencies()
        self._setup_overlay_component()

        if config.show_built_with_reflex is None:
            if (
                get_compile_context() == constants.CompileContext.DEPLOY
                and prerequisites.get_user_tier() in ["pro", "team", "enterprise"]
            ):
                config.show_built_with_reflex = False
            else:
                config.show_built_with_reflex = True

        if is_prod_mode() and config.show_built_with_reflex:
            self._setup_sticky_badge()

        progress.advance(task)

        # Store the compile results.
        compile_results: list[tuple[str, str]] = []

        progress.advance(task)

        # Track imports found.
        all_imports = {}

        if (toaster := self.toaster) is not None:
            from reflex.components.component import memo

            @memo
            def memoized_toast_provider():
                return toaster

            toast_provider = Fragment.create(memoized_toast_provider())

            app_wrappers[44, "ToasterProvider"] = toast_provider

        # Add the app wraps to the app.
        for key, app_wrap in chain(
            self.app_wraps.items(), self.extra_app_wraps.items()
        ):
            # If the app wrap is a callable, generate the component
            component = app_wrap(self._state is not None)
            if component is not None:
                app_wrappers[key] = component

        # Compile custom components.
        (
            memo_components_output,
            memo_components_result,
            memo_components_imports,
        ) = compiler.compile_memo_components(dict.fromkeys(CUSTOM_COMPONENTS.values()))
        compile_results.append((memo_components_output, memo_components_result))
        all_imports.update(memo_components_imports)
        progress.advance(task)

        with console.timing("Collect all imports and app wraps"):
            # This has to happen before compiling stateful components as that
            # prevents recursive functions from reaching all components.
            for component in self._pages.values():
                # Add component._get_all_imports() to all_imports.
                all_imports.update(component._get_all_imports())

                # Add the app wrappers from this component.
                app_wrappers.update(component._get_all_app_wrap_components())

                progress.advance(task)

        # Perform auto-memoization of stateful components.
        with console.timing("Auto-memoize StatefulComponents"):
            (
                stateful_components_path,
                stateful_components_code,
                page_components,
            ) = compiler.compile_stateful_components(
                self._pages.values(),
                progress_function=lambda task=task: progress.advance(task),
            )
            progress.advance(task)

        # Catch "static" apps (that do not define a rx.State subclass) which are trying to access rx.State.
        if code_uses_state_contexts(stateful_components_code) and self._state is None:
            msg = (
                "To access rx.State in frontend components, at least one "
                "subclass of rx.State must be defined in the app."
            )
            raise ReflexRuntimeError(msg)
        compile_results.append((stateful_components_path, stateful_components_code))

        progress.advance(task)

        # Compile the root document before fork.
        compile_results.append(
            compiler.compile_document_root(
                self.head_components,
                html_lang=self.html_lang,
                html_custom_attrs=(
                    {"suppressHydrationWarning": True, **self.html_custom_attrs}
                    if self.html_custom_attrs
                    else {"suppressHydrationWarning": True}
                ),
            )
        )

        progress.advance(task)

        # Copy the assets.
        assets_src = Path.cwd() / constants.Dirs.APP_ASSETS
        if assets_src.is_dir() and not dry_run:
            with console.timing("Copy assets"):
                path_ops.update_directory_tree(
                    src=assets_src,
                    dest=(
                        Path.cwd() / prerequisites.get_web_dir() / constants.Dirs.PUBLIC
                    ),
                )

        executor = ExecutorType.get_executor_from_environment()

        for route, component in zip(self._pages, page_components, strict=True):
            ExecutorSafeFunctions.COMPONENTS[route] = component

        modify_files_tasks: list[tuple[str, str, Callable[[str], str]]] = []

        with console.timing("Compile to Javascript"), executor as executor:
            result_futures: list[
                concurrent.futures.Future[
                    list[tuple[str, str]] | tuple[str, str] | None
                ]
            ] = []

            def _submit_work(
                fn: Callable[P, list[tuple[str, str]] | tuple[str, str] | None],
                *args: P.args,
                **kwargs: P.kwargs,
            ):
                f = executor.submit(fn, *args, **kwargs)
                f.add_done_callback(lambda _: progress.advance(task))
                result_futures.append(f)

            # Compile the pre-compiled pages.
            for route in self._pages:
                _submit_work(
                    ExecutorSafeFunctions.compile_page,
                    route,
                )

            # Compile the root stylesheet with base styles.
            _submit_work(
                compiler.compile_root_stylesheet, self.stylesheets, self.reset_style
            )

            # Compile the theme.
            _submit_work(compile_theme, self.style)

            def _submit_work_without_advancing(
                fn: Callable[P, list[tuple[str, str]] | tuple[str, str] | None],
                *args: P.args,
                **kwargs: P.kwargs,
            ):
                f = executor.submit(fn, *args, **kwargs)
                result_futures.append(f)

            for plugin in config.plugins:
                plugin.pre_compile(
                    add_save_task=_submit_work_without_advancing,
                    add_modify_task=(
                        lambda *args, plugin=plugin: modify_files_tasks.append((
                            plugin.__class__.__module__ + plugin.__class__.__name__,
                            *args,
                        ))
                    ),
                    unevaluated_pages=list(self._unevaluated_pages.values()),
                )

            # Wait for all compilation tasks to complete.
            for future in concurrent.futures.as_completed(result_futures):
                if (result := future.result()) is not None:
                    if isinstance(result, list):
                        compile_results.extend(result)
                    else:
                        compile_results.append(result)

        progress.advance(task, advance=len(config.plugins))

        app_root = self._app_root(app_wrappers=app_wrappers)

        # Get imports from AppWrap components.
        all_imports.update(app_root._get_all_imports())

        progress.advance(task)

        # Compile the contexts.
        compile_results.append(
            compiler.compile_contexts(self._state, self.theme),
        )
        if self.theme is not None:
            # Fix #2992 by removing the top-level appearance prop
            self.theme.appearance = None  # pyright: ignore[reportAttributeAccessIssue]
        progress.advance(task)

        # Compile the app root.
        compile_results.append(
            compiler.compile_app(app_root),
        )
        progress.advance(task)

        progress.stop()

        if dry_run:
            return

        # Install frontend packages.
        with console.timing("Install Frontend Packages"):
            self._get_frontend_packages(all_imports)

        # Setup the react-router.config.js
        frontend_skeleton.update_react_router_config(
            prerender_routes=prerender_routes,
        )

        if is_prod_mode():
            # Empty the .web pages directory.
            compiler.purge_web_pages_dir()
        else:
            # In dev mode, delete removed pages and update existing pages.
            keep_files = [Path(output_path) for output_path, _ in compile_results]
            for p in Path(
                prerequisites.get_web_dir()
                / constants.Dirs.PAGES
                / constants.Dirs.ROUTES
            ).rglob("*"):
                if p.is_file() and p not in keep_files:
                    # Remove pages that are no longer in the app.
                    p.unlink()

        output_mapping: dict[Path, str] = {}
        for output_path, code in compile_results:
            path = compiler_utils.resolve_path_of_web_dir(output_path)
            if path in output_mapping:
                console.warn(
                    f"Path {path} has two different outputs. The first one will be used."
                )
            else:
                output_mapping[path] = code

        for plugin in config.plugins:
            for static_file_path, content in plugin.get_static_assets():
                path = compiler_utils.resolve_path_of_web_dir(static_file_path)
                if path in output_mapping:
                    console.warn(
                        f"Plugin {plugin.__class__.__name__} is trying to write to {path} but it already exists. The plugin file will be ignored."
                    )
                else:
                    output_mapping[path] = (
                        content.decode("utf-8")
                        if isinstance(content, bytes)
                        else content
                    )

        for plugin_name, file_path, modify_fn in modify_files_tasks:
            path = compiler_utils.resolve_path_of_web_dir(file_path)
            file_content = output_mapping.get(path)
            if file_content is None:
                if path.exists():
                    file_content = path.read_text()
                else:
                    msg = f"Plugin {plugin_name} is trying to modify {path} but it does not exist."
                    raise FileNotFoundError(msg)
            output_mapping[path] = modify_fn(file_content)

        with console.timing("Write to Disk"):
            for output_path, code in output_mapping.items():
                compiler_utils.write_file(output_path, code)

    def _write_stateful_pages_marker(self):
        """Write list of routes that create dynamic states for the backend to use later."""
        if self._state is not None:
            stateful_pages_marker = (
                prerequisites.get_backend_dir() / constants.Dirs.STATEFUL_PAGES
            )
            stateful_pages_marker.parent.mkdir(parents=True, exist_ok=True)
            with stateful_pages_marker.open("w") as f:
                json.dump(list(self._stateful_pages), f)

    def add_all_routes_endpoint(self):
        """Add an endpoint to the app that returns all the routes."""
        if not self._api:
            return

        def all_routes(_request: Request) -> Response:
            return JSONResponse(list(self._unevaluated_pages.keys()))

        self._api.add_route(
            str(constants.Endpoint.ALL_ROUTES), all_routes, methods=["GET"]
        )

    @contextlib.asynccontextmanager
    async def modify_state(
        self, token: str, background: bool = False
    ) -> AsyncIterator[BaseState]:
        """Modify the state out of band.

        Args:
            token: The token to modify the state for.
            background: Whether the modification is happening in a background task.

        Yields:
            The state to modify.

        Raises:
            RuntimeError: If the app has not been initialized yet.
        """
        if self.event_namespace is None:
            msg = "App has not been initialized yet."
            raise RuntimeError(msg)

        # Get exclusive access to the state.
        async with self.state_manager.modify_state(token) as state:
            # No other event handler can modify the state while in this context.
            yield state
            delta = await state._get_resolved_delta()
            state._clean()
            if delta:
                # When the frontend vars are modified emit the delta to the frontend.
                await self.event_namespace.emit_update(
                    update=StateUpdate(
                        delta=delta,
                        final=True if not background else None,
                    ),
                    token=token,
                )

    def _process_background(
        self, state: BaseState, event: Event
    ) -> asyncio.Task | None:
        """Process an event in the background and emit updates as they arrive.

        Args:
            state: The state to process the event for.
            event: The event to process.

        Returns:
            Task if the event was backgroundable, otherwise None
        """
        substate, handler = state._get_event_handler(event)

        if not handler.is_background:
            return None

        async def _coro():
            """Coroutine to process the event and emit updates inside an asyncio.Task.

            Raises:
                RuntimeError: If the app has not been initialized yet.
            """
            if self.event_namespace is None:
                msg = "App has not been initialized yet."
                raise RuntimeError(msg)

            # Process the event.
            async for update in state._process_event(
                handler=handler, state=substate, payload=event.payload
            ):
                # Postprocess the event.
                update = await self._postprocess(state, event, update)

                # Send the update to the client.
                await self.event_namespace.emit_update(
                    update=update,
                    token=event.token,
                )

        task = asyncio.create_task(
            _coro(),
            name=f"reflex_background_task|{event.name}|{time.time()}|{event.token}",
        )
        self._background_tasks.add(task)
        # Clean up task from background_tasks set when complete.
        task.add_done_callback(self._background_tasks.discard)
        return task

    def _validate_exception_handlers(self):
        """Validate the custom event exception handlers for front- and backend.

        Raises:
            ValueError: If the custom exception handlers are invalid.

        """
        frontend_arg_spec = {
            "exception": Exception,
        }

        backend_arg_spec = {
            "exception": Exception,
        }

        for handler_domain, handler_fn, handler_spec in zip(
            ["frontend", "backend"],
            [self.frontend_exception_handler, self.backend_exception_handler],
            [
                frontend_arg_spec,
                backend_arg_spec,
            ],
            strict=True,
        ):
            if hasattr(handler_fn, "__name__"):
                fn_name_ = handler_fn.__name__
            else:
                fn_name_ = type(handler_fn).__name__

            if isinstance(handler_fn, functools.partial):
                msg = f"Provided custom {handler_domain} exception handler `{fn_name_}` is a partial function. Please provide a named function instead."
                raise ValueError(msg)

            if not callable(handler_fn):
                msg = f"Provided custom {handler_domain} exception handler `{fn_name_}` is not a function."
                raise ValueError(msg)

            # Allow named functions only as lambda functions cannot be introspected
            if fn_name_ == "<lambda>":
                msg = f"Provided custom {handler_domain} exception handler `{fn_name_}` is a lambda function. Please use a named function instead."
                raise ValueError(msg)

            # Check if the function has the necessary annotations and types in the right order
            argspec = inspect.getfullargspec(handler_fn)
            arg_annotations = {
                k: eval(v) if isinstance(v, str) else v
                for k, v in argspec.annotations.items()
                if k not in ["args", "kwargs", "return"]
            }

            for required_arg_index, required_arg in enumerate(handler_spec):
                if required_arg not in arg_annotations:
                    msg = f"Provided custom {handler_domain} exception handler `{fn_name_}` does not take the required argument `{required_arg}`"
                    raise ValueError(msg)
                if list(arg_annotations.keys())[required_arg_index] != required_arg:
                    msg = (
                        f"Provided custom {handler_domain} exception handler `{fn_name_}` has the wrong argument order."
                        f"Expected `{required_arg}` as the {required_arg_index + 1} argument but got `{list(arg_annotations.keys())[required_arg_index]}`"
                    )
                    raise ValueError(msg)

                if not issubclass(arg_annotations[required_arg], Exception):
                    msg = (
                        f"Provided custom {handler_domain} exception handler `{fn_name_}` has the wrong type for {required_arg} argument."
                        f"Expected to be `Exception` but got `{arg_annotations[required_arg]}`"
                    )
                    raise ValueError(msg)

            # Check if the return type is valid for backend exception handler
            if handler_domain == "backend":
                sig = inspect.signature(self.backend_exception_handler)
                return_type = (
                    eval(sig.return_annotation)
                    if isinstance(sig.return_annotation, str)
                    else sig.return_annotation
                )

                valid = bool(
                    return_type == EventSpec
                    or return_type == EventSpec | None
                    or return_type == list[EventSpec]
                    or return_type == inspect.Signature.empty
                    or return_type is None
                )

                if not valid:
                    msg = (
                        f"Provided custom {handler_domain} exception handler `{fn_name_}` has the wrong return type."
                        f"Expected `EventSpec | list[EventSpec] | None` but got `{return_type}`"
                    )
                    raise ValueError(msg)


async def process(
    app: App, event: Event, sid: str, headers: dict, client_ip: str
) -> AsyncGenerator[StateUpdate]:
    """Process an event.

    Args:
        app: The app to process the event for.
        event: The event to process.
        sid: The Socket.IO session id.
        headers: The client headers.
        client_ip: The client_ip.

    Raises:
        Exception: If a reflex specific error occurs during processing the event.

    Yields:
        The state updates after processing the event.
    """
    from reflex.utils import telemetry

    try:
        # Add request data to the state.
        router_data = event.router_data
        router_data.update({
            constants.RouteVar.QUERY: format.format_query_params(event.router_data),
            constants.RouteVar.CLIENT_TOKEN: event.token,
            constants.RouteVar.SESSION_ID: sid,
            constants.RouteVar.HEADERS: headers,
            constants.RouteVar.CLIENT_IP: client_ip,
        })
        # Get the state for the session exclusively.
        async with app.state_manager.modify_state(
            event.substate_token, event=event
        ) as state:
            # When this is a brand new instance of the state, signal the
            # frontend to reload before processing it.
            if (
                not state.router_data
                and event.name != get_hydrate_event(state)
                and app.event_namespace is not None
            ):
                await asyncio.create_task(
                    app.event_namespace.emit(
                        "reload",
                        data=event,
                        to=sid,
                    ),
                    name=f"reflex_emit_reload|{event.name}|{time.time()}|{event.token}",
                )
                return
            router_data[constants.RouteVar.PATH] = "/" + (
                app.router(path) or "404"
                if (path := router_data.get(constants.RouteVar.PATH))
                else "404"
            ).removeprefix("/")
            # re-assign only when the value is different
            if state.router_data != router_data:
                # assignment will recurse into substates and force recalculation of
                # dependent ComputedVar (dynamic route variables)
                state.router_data = router_data
                state.router = RouterData.from_router_data(router_data)

            # Preprocess the event.
            update = await app._preprocess(state, event)

            # If there was an update, yield it.
            if update is not None:
                yield update

            # Only process the event if there is no update.
            else:
                if app._process_background(state, event) is not None:
                    # `final=True` allows the frontend send more events immediately.
                    yield StateUpdate(final=True)
                else:
                    # Process the event synchronously.
                    async for update in state._process(event):
                        # Postprocess the event.
                        update = await app._postprocess(state, event, update)

                        # Yield the update.
                        yield update
    except Exception as ex:
        telemetry.send_error(ex, context="backend")

        app.backend_exception_handler(ex)
        raise


def ping(_request: Request) -> Response:
    """Test API endpoint.

    Args:
        _request: The Starlette request object.

    Returns:
        The response.
    """
    return JSONResponse("pong")


async def health(_request: Request) -> JSONResponse:
    """Health check endpoint to assess the status of the database and Redis services.

    Args:
        _request: The Starlette request object.

    Returns:
        JSONResponse: A JSON object with the health status:
            - "status" (bool): Overall health, True if all checks pass.
            - "db" (bool or str): Database status - True, False, or "NA".
            - "redis" (bool or str): Redis status - True, False, or "NA".
    """
    health_status = {"status": True}
    status_code = 200

    tasks = []

    if prerequisites.check_db_used():
        from reflex.model import get_db_status

        tasks.append(run_in_thread(get_db_status))
    if prerequisites.check_redis_used():
        tasks.append(prerequisites.get_redis_status())

    results = await asyncio.gather(*tasks)

    for result in results:
        health_status |= result

    if "redis" in health_status and health_status["redis"] is None:
        health_status["redis"] = False

    if not all(health_status.values()):
        health_status["status"] = False
        status_code = 503

    return JSONResponse(content=health_status, status_code=status_code)


def upload(app: App):
    """Upload a file.

    Args:
        app: The app to upload the file for.

    Returns:
        The upload function.
    """

    async def upload_file(request: Request):
        """Upload a file.

        Args:
            request: The Starlette request object.

        Returns:
            StreamingResponse yielding newline-delimited JSON of StateUpdate
            emitted by the upload handler.

        Raises:
            UploadValueError: if there are no args with supported annotation.
            UploadTypeError: if a background task is used as the handler.
            HTTPException: when the request does not include token / handler headers.
        """
        from reflex.utils.exceptions import UploadTypeError, UploadValueError

        # Get the files from the request.
        try:
            files = await request.form()
        except ClientDisconnect:
            return Response()  # user cancelled
        files = files.getlist("files")
        if not files:
            msg = "No files were uploaded."
            raise UploadValueError(msg)

        token = request.headers.get("reflex-client-token")
        handler = request.headers.get("reflex-event-handler")

        if not token or not handler:
            raise HTTPException(
                status_code=400,
                detail="Missing reflex-client-token or reflex-event-handler header.",
            )

        # Get the state for the session.
        substate_token = _substate_key(token, handler.rpartition(".")[0])
        state = await app.state_manager.get_state(substate_token)

        # get the current session ID
        # get the current state(parent state/substate)
        path = handler.split(".")[:-1]
        current_state = state.get_substate(path)
        handler_upload_param = ()

        # get handler function
        func = getattr(type(current_state), handler.split(".")[-1])

        # check if there exists any handler args with annotation, list[UploadFile]
        if isinstance(func, EventHandler):
            if func.is_background:
                msg = f"@rx.event(background=True) is not supported for upload handler `{handler}`."
                raise UploadTypeError(msg)
            func = func.fn
        if isinstance(func, functools.partial):
            func = func.func
        for k, v in get_type_hints(func).items():
            if types.is_generic_alias(v) and types._issubclass(
                get_args(v)[0],
                UploadFile,
            ):
                handler_upload_param = (k, v)
                break

        if not handler_upload_param:
            msg = (
                f"`{handler}` handler should have a parameter annotated as "
                "list[rx.UploadFile]"
            )
            raise UploadValueError(msg)

        # Make a copy of the files as they are closed after the request.
        # This behaviour changed from fastapi 0.103.0 to 0.103.1 as the
        # AsyncExitStack was removed from the request scope and is now
        # part of the routing function which closes this before the
        # event is handled.
        file_copies = []
        for file in files:
            if not isinstance(file, StarletteUploadFile):
                raise UploadValueError(
                    "Uploaded file is not an UploadFile." + str(file)
                )
            content_copy = io.BytesIO()
            content_copy.write(await file.read())
            content_copy.seek(0)
            file_copies.append(
                UploadFile(
                    file=content_copy,
                    path=Path(file.filename.lstrip("/")) if file.filename else None,
                    size=file.size,
                    headers=file.headers,
                )
            )

        for file in files:
            if not isinstance(file, StarletteUploadFile):
                raise UploadValueError(
                    "Uploaded file is not an UploadFile." + str(file)
                )
            await file.close()

        event = Event(
            token=token,
            name=handler,
            payload={handler_upload_param[0]: file_copies},
        )

        async def _ndjson_updates():
            """Process the upload event, generating ndjson updates.

            Yields:
                Each state update as JSON followed by a new line.
            """
            # Process the event.
            async with app.state_manager.modify_state(event.substate_token) as state:
                async for update in state._process(event):
                    # Postprocess the event.
                    update = await app._postprocess(state, event, update)
                    yield update.json() + "\n"

        # Stream updates to client
        return StreamingResponse(
            _ndjson_updates(),
            media_type="application/x-ndjson",
        )

    return upload_file


class EventNamespace(AsyncNamespace):
    """The event namespace."""

    # The application object.
    app: App

    def __init__(self, namespace: str, app: App):
        """Initialize the event namespace.

        Args:
            namespace: The namespace.
            app: The application object.
        """
        super().__init__(namespace)
        self.app = app

        # Use TokenManager for distributed duplicate tab prevention
        self._token_manager = TokenManager.create()

    @property
    def token_to_sid(self) -> Mapping[str, str]:
        """Get token to SID mapping for backward compatibility.

        Note: this mapping is read-only.

        Returns:
            The token to SID mapping.
        """
        # For backward compatibility, expose the underlying dict
        return self._token_manager.token_to_sid

    @property
    def sid_to_token(self) -> dict[str, str]:
        """Get SID to token mapping for backward compatibility.

        Returns:
            The SID to token mapping dict.
        """
        # For backward compatibility, expose the underlying dict
        return self._token_manager.sid_to_token

    async def on_connect(self, sid: str, environ: dict):
        """Event for when the websocket is connected.

        Args:
            sid: The Socket.IO session id.
            environ: The request information, including HTTP headers.
        """
        if isinstance(self._token_manager, RedisTokenManager):
            # Make sure this instance is watching for updates from other instances.
            self._token_manager.ensure_lost_and_found_task(self.emit_update)
        query_params = urllib.parse.parse_qs(environ.get("QUERY_STRING", ""))
        token_list = query_params.get("token", [])
        if token_list:
            await self.link_token_to_sid(sid, token_list[0])
        else:
            console.warn(f"No token provided in connection for session {sid}")

        subprotocol = environ.get("HTTP_SEC_WEBSOCKET_PROTOCOL")
        if subprotocol and subprotocol != constants.Reflex.VERSION:
            console.warn(
                f"Frontend version {subprotocol} for session {sid} does not match the backend version {constants.Reflex.VERSION}."
            )

    def on_disconnect(self, sid: str) -> asyncio.Task | None:
        """Event for when the websocket disconnects.

        Args:
            sid: The Socket.IO session id.

        Returns:
            An asyncio Task for cleaning up the token, or None.
        """
        # Get token before cleaning up
        disconnect_token = self.sid_to_token.get(sid)
        if disconnect_token:
            # Use async cleanup through token manager
            task = asyncio.create_task(
                self._token_manager.disconnect_token(disconnect_token, sid),
                name=f"reflex_disconnect_token|{disconnect_token}|{time.time()}",
            )
            # Don't await to avoid blocking disconnect, but handle potential errors
            task.add_done_callback(
                lambda t: t.exception()
                and console.error(f"Token cleanup error: {t.exception()}")
            )
            return task
        return None

    async def emit_update(self, update: StateUpdate, token: str) -> None:
        """Emit an update to the client.

        Args:
            update: The state update to send.
            token: The client token (tab) associated with the event.
        """
        client_token, _ = _split_substate_key(token)
        socket_record = self._token_manager.token_to_socket.get(client_token)
        if (
            socket_record is None
            or socket_record.instance_id != self._token_manager.instance_id
        ):
            if isinstance(self._token_manager, RedisTokenManager):
                # The socket belongs to another instance of the app, send it to the lost and found.
                if not await self._token_manager.emit_lost_and_found(
                    client_token, update
                ):
                    console.warn(
                        f"Failed to send delta to lost and found for client {token!r}"
                    )
            else:
                # If the socket record is None, we are not connected to a client. Prevent sending
                # updates to all clients.
                console.warn(
                    f"Attempting to send delta to disconnected client {token!r}"
                )
            return
        # Creating a task prevents the update from being blocked behind other coroutines.
        await asyncio.create_task(
            self.emit(str(constants.SocketEvent.EVENT), update, to=socket_record.sid),
            name=f"reflex_emit_event|{token}|{socket_record.sid}|{time.time()}",
        )

    async def on_event(self, sid: str, data: Any):
        """Event for receiving front-end websocket events.

        Raises:
            RuntimeError: If the Socket.IO is badly initialized.

        Args:
            sid: The Socket.IO session id.
            data: The event data.

        Raises:
            EventDeserializationError: If the event data is not a dictionary.
        """
        fields = data

        if isinstance(fields, str):
            console.warn(
                "Received event data as a string. This generally should not happen and may indicate a bug."
                f" Event data: {fields}"
            )
            try:
                fields = json.loads(fields)
            except json.JSONDecodeError as ex:
                msg = f"Failed to deserialize event data: {fields}."
                raise exceptions.EventDeserializationError(msg) from ex

        if not isinstance(fields, dict):
            msg = f"Event data must be a dictionary, but received {fields} of type {type(fields)}."
            raise exceptions.EventDeserializationError(msg)

        try:
            # Get the event.
            event = Event(**{k: v for k, v in fields.items() if k in _EVENT_FIELDS})
        except (TypeError, ValueError) as ex:
            msg = f"Failed to deserialize event data: {fields}."
            raise exceptions.EventDeserializationError(msg) from ex

        # Correct the token if it doesn't match what we expect for this SID
        expected_token = self.sid_to_token.get(sid)
        if expected_token and event.token != expected_token:
            # Create new event with corrected token since Event is frozen
            from dataclasses import replace

            event = replace(event, token=expected_token)

        # Get the event environment.
        if self.app.sio is None:
            msg = "Socket.IO is not initialized."
            raise RuntimeError(msg)
        environ = self.app.sio.get_environ(sid, self.namespace)
        if environ is None:
            msg = "Socket.IO environ is not initialized."
            raise RuntimeError(msg)

        # Get the client headers.
        headers = {
            k.decode("utf-8"): v.decode("utf-8")
            for (k, v) in environ["asgi.scope"]["headers"]
        }

        # Get the client IP
        try:
            client_ip = environ["asgi.scope"]["client"][0]
            headers["asgi-scope-client"] = client_ip
        except (KeyError, IndexError):
            client_ip = environ.get("REMOTE_ADDR", "0.0.0.0")

        # Unroll reverse proxy forwarded headers.
        client_ip = (
            headers.get(
                "x-forwarded-for",
                client_ip,
            )
            .partition(",")[0]
            .strip()
        )

        async with contextlib.aclosing(
            process(self.app, event, sid, headers, client_ip)
        ) as updates_gen:
            # Process the events.
            async for update in updates_gen:
                # Emit the update from processing the event.
                await self.emit_update(update=update, token=event.token)

    async def on_ping(self, sid: str):
        """Event for testing the API endpoint.

        Args:
            sid: The Socket.IO session id.
        """
        # Emit the test event.
        await self.emit(str(constants.SocketEvent.PING), "pong", to=sid)

    async def link_token_to_sid(self, sid: str, token: str):
        """Link a token to a session id.

        Args:
            sid: The Socket.IO session id.
            token: The client token.
        """
        # Use TokenManager for duplicate detection and Redis support
        new_token = await self._token_manager.link_token_to_sid(token, sid)

        if new_token:
            # Duplicate detected, emit new token to client
            await self.emit("new_token", new_token, to=sid)

        # Update client state to apply new sid/token for running background tasks.
        async with self.app.state_manager.modify_state(
            _substate_key(new_token or token, self.app.state_manager.state)
        ) as state:
            state.router_data[constants.RouteVar.SESSION_ID] = sid
            state.router = RouterData.from_router_data(state.router_data)
