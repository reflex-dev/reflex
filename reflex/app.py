"""The main Reflex app."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import copy
import functools
import inspect
import io
import multiprocessing
import os
import platform
import sys
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
    Type,
    Union,
    get_args,
    get_type_hints,
)

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware import cors
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn
from socketio import ASGIApp, AsyncNamespace, AsyncServer
from starlette_admin.contrib.sqla.admin import Admin
from starlette_admin.contrib.sqla.view import ModelView

from reflex import constants
from reflex.admin import AdminDash
from reflex.base import Base
from reflex.compiler import compiler
from reflex.compiler import utils as compiler_utils
from reflex.compiler.compiler import ExecutorSafeFunctions
from reflex.components.base.app_wrap import AppWrap
from reflex.components.base.fragment import Fragment
from reflex.components.component import (
    Component,
    ComponentStyle,
    evaluate_style_namespaces,
)
from reflex.components.core.banner import connection_pulser, connection_toaster
from reflex.components.core.client_side_routing import (
    Default404Page,
    wait_for_client_redirect,
)
from reflex.components.core.upload import Upload, get_upload_dir
from reflex.components.radix import themes
from reflex.config import get_config
from reflex.event import Event, EventHandler, EventSpec
from reflex.middleware import HydrateMiddleware, Middleware
from reflex.model import Model
from reflex.page import (
    DECORATED_PAGES,
)
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
    _substate_key,
    code_uses_state_contexts,
)
from reflex.utils import console, exceptions, format, prerequisites, types
from reflex.utils.exec import is_testing_env, should_skip_compile
from reflex.utils.imports import ImportVar

# Define custom types.
ComponentCallable = Callable[[], Component]
Reducer = Callable[[Event], Coroutine[Any, Any, StateUpdate]]


def default_overlay_component() -> Component:
    """Default overlay_component attribute for App.

    Returns:
        The default overlay_component, which is a connection_modal.
    """
    return Fragment.create(connection_pulser(), connection_toaster())


class OverlayFragment(Fragment):
    """Alias for Fragment, used to wrap the overlay_component."""

    pass


class LifespanMixin(Base):
    """A Mixin that allow tasks to run during the whole app lifespan."""

    # Lifespan tasks that are planned to run.
    lifespan_tasks: Set[Union[asyncio.Task, Callable]] = set()

    @contextlib.asynccontextmanager
    async def _run_lifespan_tasks(self, app: FastAPI):
        running_tasks = []
        try:
            async with contextlib.AsyncExitStack() as stack:
                for task in self.lifespan_tasks:
                    if isinstance(task, asyncio.Task):
                        running_tasks.append(task)
                    else:
                        signature = inspect.signature(task)
                        if "app" in signature.parameters:
                            task = functools.partial(task, app=app)
                        _t = task()
                        if isinstance(_t, contextlib._AsyncGeneratorContextManager):
                            await stack.enter_async_context(_t)
                        elif isinstance(_t, Coroutine):
                            running_tasks.append(asyncio.create_task(_t))
                yield
        finally:
            cancel_kwargs = (
                {"msg": "lifespan_cleanup"} if sys.version_info >= (3, 9) else {}
            )
            for task in running_tasks:
                task.cancel(**cancel_kwargs)

    def register_lifespan_task(self, task: Callable | asyncio.Task, **task_kwargs):
        """Register a task to run during the lifespan of the app.

        Args:
            task: The task to register.
            task_kwargs: The kwargs of the task.
        """
        if task_kwargs:
            task = functools.partial(task, **task_kwargs)  # type: ignore
        self.lifespan_tasks.add(task)  # type: ignore


class App(LifespanMixin, Base):
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
    theme: Optional[Component] = themes.theme(accent_color="blue")

    # The [global style](https://reflex.dev/docs/styling/overview/#global-styles}) for the app.
    style: ComponentStyle = {}

    # A list of URLs to [stylesheets](https://reflex.dev/docs/styling/custom-stylesheets/) to include in the app.
    stylesheets: List[str] = []

    # A component that is present on every page (defaults to the Connection Error banner).
    overlay_component: Optional[
        Union[Component, ComponentCallable]
    ] = default_overlay_component

    # Components to add to the head of every page.
    head_components: List[Component] = []

    # The Socket.IO AsyncServer instance.
    sio: Optional[AsyncServer] = None

    # The language to add to the html root tag of every page.
    html_lang: Optional[str] = None

    # Attributes to add to the html root tag of every page.
    html_custom_attrs: Optional[Dict[str, str]] = None

    # A map from a page route to the component to render. Users should use `add_page`. PRIVATE.
    pages: Dict[str, Component] = {}

    # The backend API object. PRIVATE.
    api: FastAPI = None  # type: ignore

    # The state class to use for the app. PRIVATE.
    state: Optional[Type[BaseState]] = None

    # Class to manage many client states.
    _state_manager: Optional[StateManager] = None

    # Middleware to add to the app. Users should use `add_middleware`. PRIVATE.
    middleware: List[Middleware] = []

    # Mapping from a route to event handlers to trigger when the page loads. PRIVATE.
    load_events: Dict[str, List[Union[EventHandler, EventSpec]]] = {}

    # Admin dashboard to view and manage the database. PRIVATE.
    admin_dash: Optional[AdminDash] = None

    # The async server name space. PRIVATE.
    event_namespace: Optional[EventNamespace] = None

    # Background tasks that are currently running. PRIVATE.
    background_tasks: Set[asyncio.Task] = set()

    def __init__(self, **kwargs):
        """Initialize the app.

        Args:
            **kwargs: Kwargs to initialize the app with.

        Raises:
            ValueError: If the event namespace is not provided in the config.
                        Also, if there are multiple client subclasses of rx.BaseState(Subclasses of rx.BaseState should consist
                        of the DefaultState and the client app state).
        """
        if "connect_error_component" in kwargs:
            raise ValueError(
                "`connect_error_component` is deprecated, use `overlay_component` instead"
            )
        super().__init__(**kwargs)
        base_state_subclasses = BaseState.__subclasses__()

        # Special case to allow test cases have multiple subclasses of rx.BaseState.
        if not is_testing_env() and len(base_state_subclasses) > 1:
            # Only one Base State class is allowed.
            raise ValueError(
                "rx.BaseState cannot be subclassed multiple times. use rx.State instead"
            )

        # Add middleware.
        self.middleware.append(HydrateMiddleware())

        # Set up the API.
        self.api = FastAPI(lifespan=self._run_lifespan_tasks)
        self._add_cors()
        self._add_default_endpoints()

        self._setup_state()

        # Set up the admin dash.
        self._setup_admin_dash()

    def _enable_state(self) -> None:
        """Enable state for the app."""
        if not self.state:
            self.state = State
            self._setup_state()

    def _setup_state(self) -> None:
        """Set up the state for the app.

        Raises:
            RuntimeError: If the socket server is invalid.
        """
        if not self.state:
            return

        config = get_config()

        # Set up the state manager.
        self._state_manager = StateManager.create(state=self.state)

        # Set up the Socket.IO AsyncServer.
        if not self.sio:
            self.sio = AsyncServer(
                async_mode="asgi",
                cors_allowed_origins=(
                    "*"
                    if config.cors_allowed_origins == ["*"]
                    else config.cors_allowed_origins
                ),
                cors_credentials=True,
                max_http_buffer_size=constants.POLLING_MAX_HTTP_BUFFER_SIZE,
                ping_interval=constants.Ping.INTERVAL,
                ping_timeout=constants.Ping.TIMEOUT,
            )
        elif getattr(self.sio, "async_mode", "") != "asgi":
            raise RuntimeError(
                f"Custom `sio` must use `async_mode='asgi'`, not '{self.sio.async_mode}'."
            )

        # Create the socket app. Note event endpoint constant replaces the default 'socket.io' path.
        socket_app = ASGIApp(self.sio, socketio_path="")
        namespace = config.get_event_namespace()

        # Create the event namespace and attach the main app. Not related to any paths.
        self.event_namespace = EventNamespace(namespace, self)

        # Register the event namespace with the socket.
        self.sio.register_namespace(self.event_namespace)
        # Mount the socket app with the API.
        self.api.mount(str(constants.Endpoint.EVENT), socket_app)

    def __repr__(self) -> str:
        """Get the string representation of the app.

        Returns:
            The string representation of the app.
        """
        return f"<App state={self.state.__name__ if self.state else None}>"

    def __call__(self) -> FastAPI:
        """Run the backend api instance.

        Returns:
            The backend api.
        """
        return self.api

    def _add_default_endpoints(self):
        """Add default api endpoints (ping)."""
        # To test the server.
        self.api.get(str(constants.Endpoint.PING))(ping)

    def _add_optional_endpoints(self):
        """Add optional api endpoints (_upload)."""
        # To upload files.
        if Upload.is_used:
            self.api.post(str(constants.Endpoint.UPLOAD))(upload(self))

            # To access uploaded files.
            self.api.mount(
                str(constants.Endpoint.UPLOAD),
                StaticFiles(directory=get_upload_dir()),
                name="uploaded_files",
            )

    def _add_cors(self):
        """Add CORS middleware to the app."""
        self.api.add_middleware(
            cors.CORSMiddleware,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            allow_origins=["*"],
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
            raise ValueError("The state manager has not been initialized.")
        return self._state_manager

    async def _preprocess(self, state: BaseState, event: Event) -> StateUpdate | None:
        """Preprocess the event.

        This is where middleware can modify the event before it is processed.
        Each middleware is called in the order it was added to the app.

        If a middleware returns an update, the event is not processed and the
        update is returned.

        Args:
            state: The state to preprocess.
            event: The event to preprocess.

        Returns:
            An optional state to return.
        """
        for middleware in self.middleware:
            if asyncio.iscoroutinefunction(middleware.preprocess):
                out = await middleware.preprocess(app=self, state=state, event=event)  # type: ignore
            else:
                out = middleware.preprocess(app=self, state=state, event=event)  # type: ignore
            if out is not None:
                return out  # type: ignore

    async def _postprocess(
        self, state: BaseState, event: Event, update: StateUpdate
    ) -> StateUpdate:
        """Postprocess the event.

        This is where middleware can modify the delta after it is processed.
        Each middleware is called in the order it was added to the app.

        Args:
            state: The state to postprocess.
            event: The event to postprocess.
            update: The current state update.

        Returns:
            The state update to return.
        """
        for middleware in self.middleware:
            if asyncio.iscoroutinefunction(middleware.postprocess):
                out = await middleware.postprocess(
                    app=self,  # type: ignore
                    state=state,
                    event=event,
                    update=update,
                )
            else:
                out = middleware.postprocess(
                    app=self,  # type: ignore
                    state=state,
                    event=event,
                    update=update,
                )
            if out is not None:
                return out  # type: ignore
        return update

    def add_middleware(self, middleware: Middleware, index: int | None = None):
        """Add middleware to the app.

        Args:
            middleware: The middleware to add.
            index: The index to add the middleware at.
        """
        if index is None:
            self.middleware.append(middleware)
        else:
            self.middleware.insert(index, middleware)

    @staticmethod
    def _generate_component(component: Component | ComponentCallable) -> Component:
        """Generate a component from a callable.

        Args:
            component: The component function to call or Component to return as-is.

        Returns:
            The generated component.

        Raises:
            VarOperationTypeError: When an invalid component var related function is passed.
            TypeError: When an invalid component function is passed.
            exceptions.MatchTypeError: If the return types of match cases in rx.match are different.
        """
        from reflex.utils.exceptions import VarOperationTypeError

        try:
            return component if isinstance(component, Component) else component()
        except exceptions.MatchTypeError:
            raise
        except TypeError as e:
            message = str(e)
            if "BaseVar" in message or "ComputedVar" in message:
                raise VarOperationTypeError(
                    "You may be trying to use an invalid Python function on a state var. "
                    "When referencing a var inside your render code, only limited var operations are supported. "
                    "See the var operation docs here: https://reflex.dev/docs/vars/var-operations/"
                ) from e
            raise e

    def add_page(
        self,
        component: Component | ComponentCallable,
        route: str | None = None,
        title: str | None = None,
        description: str | None = None,
        image: str = constants.DefaultPage.IMAGE,
        on_load: (
            EventHandler | EventSpec | list[EventHandler | EventSpec] | None
        ) = None,
        meta: list[dict[str, str]] = constants.DefaultPage.META_LIST,
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

        Raises:
            ValueError: When the specified route name already exists.
        """
        # If the route is not set, get it from the callable.
        if route is None:
            assert isinstance(
                component, Callable
            ), "Route must be set if component is not a callable."
            # Format the route.
            route = format.format_route(component.__name__)
        else:
            route = format.format_route(route, format_case=False)

        # Check if the route given is valid
        verify_route_validity(route)

        if route in self.pages and os.getenv(constants.RELOAD_CONFIG):
            # when the app is reloaded(typically for app harness tests), we should maintain
            # the latest render function of a route.This applies typically to decorated pages
            # since they are only added when app._compile is called.
            self.pages.pop(route)

        if route in self.pages:
            route_name = (
                f"`{route}` or `/`"
                if route == constants.PageNames.INDEX_ROUTE
                else f"`{route}`"
            )
            raise ValueError(
                f"Duplicate page route {route_name} already exists. Make sure you do not have two"
                f" pages with the same route"
            )

        # Setup dynamic args for the route.
        # this state assignment is only required for tests using the deprecated state kwarg for App
        state = self.state if self.state else State
        state.setup_dynamic_args(get_route_args(route))

        # Generate the component if it is a callable.
        component = self._generate_component(component)

        # unpack components that return tuples in an rx.fragment.
        if isinstance(component, tuple):
            component = Fragment.create(*component)

        # Ensure state is enabled if this page uses state.
        if self.state is None:
            if on_load or component._has_event_triggers():
                self._enable_state()
            else:
                for var in component._get_vars(include_children=True):
                    if not var._var_data:
                        continue
                    if not var._var_data.state:
                        continue
                    self._enable_state()
                    break

        component = OverlayFragment.create(component)

        meta_args = {
            "title": (
                title
                if title is not None
                else format.make_default_page_title(get_config().app_name, route)
            ),
            "image": image,
            "meta": meta,
        }

        if description is not None:
            meta_args["description"] = description

        # Add meta information to the component.
        compiler_utils.add_meta(
            component,
            **meta_args,
        )

        # Add the page.
        self._check_routes_conflict(route)
        self.pages[route] = component

        # Add the load events.
        if on_load:
            if not isinstance(on_load, list):
                on_load = [on_load]
            self.load_events[route] = on_load

    def get_load_events(self, route: str) -> list[EventHandler | EventSpec]:
        """Get the load events for a route.

        Args:
            route: The route to get the load events for.

        Returns:
            The load events for the route.
        """
        route = route.lstrip("/")
        if route == "":
            route = constants.PageNames.INDEX_ROUTE
        return self.load_events.get(route, [])

    def _check_routes_conflict(self, new_route: str):
        """Verify if there is any conflict between the new route and any existing route.

        Based on conflicts that NextJS would throw if not intercepted.

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
            constants.RouteRegex.SINGLE_CATCHALL_SEGMENT,
            constants.RouteRegex.DOUBLE_CATCHALL_SEGMENT,
        )
        for route in self.pages:
            replaced_route = replace_brackets_with_keywords(route)
            for rw, r, nr in zip(
                replaced_route.split("/"), route.split("/"), new_route.split("/")
            ):
                if rw in segments and r != nr:
                    # If the slugs in the segments of both routes are not the same, then the route is invalid
                    raise RouteValueError(
                        f"You cannot use different slug names for the same dynamic path in  {route} and {new_route} ('{r}' != '{nr}')"
                    )
                elif rw not in segments and r != nr:
                    # if the section being compared in both routes is not a dynamic segment(i.e not wrapped in brackets)
                    # then we are guaranteed that the route is valid and there's no need checking the rest.
                    # eg. /posts/[id]/info/[slug1] and /posts/[id]/info1/[slug1] is always going to be valid since
                    # info1 will break away into its own tree.
                    break

    def add_custom_404_page(
        self,
        component: Component | ComponentCallable | None = None,
        title: str = constants.Page404.TITLE,
        image: str = constants.Page404.IMAGE,
        description: str = constants.Page404.DESCRIPTION,
        on_load: (
            EventHandler | EventSpec | list[EventHandler | EventSpec] | None
        ) = None,
        meta: list[dict[str, str]] = constants.DefaultPage.META_LIST,
    ):
        """Define a custom 404 page for any url having no match.

        If there is no page defined on 'index' route, add the 404 page to it.
        If there is no global catchall defined, add the 404 page with a catchall.

        Args:
            component: The component to display at the page.
            title: The title of the page.
            description: The description of the page.
            image: The image to display on the page.
            on_load: The event handler(s) that will be called each time the page load.
            meta: The metadata of the page.
        """
        if component is None:
            component = Default404Page.create()
        self.add_page(
            component=wait_for_client_redirect(self._generate_component(component)),
            route=constants.Page404.SLUG,
            title=title or constants.Page404.TITLE,
            image=image or constants.Page404.IMAGE,
            description=description or constants.Page404.DESCRIPTION,
            on_load=on_load,
            meta=meta,
        )

    def _setup_admin_dash(self):
        """Setup the admin dash."""
        # Get the admin dash.
        admin_dash = self.admin_dash

        if admin_dash and admin_dash.models:
            # Build the admin dashboard
            admin = (
                admin_dash.admin
                if admin_dash.admin
                else Admin(
                    engine=Model.get_db_engine(),
                    title="Reflex Admin Dashboard",
                    logo_url="https://reflex.dev/Reflex.svg",
                )
            )

            for model in admin_dash.models:
                view = admin_dash.view_overrides.get(model, ModelView)
                admin.add_view(view(model))

            admin.mount_to(self.api)

    def _get_frontend_packages(self, imports: Dict[str, set[ImportVar]]):
        """Gets the frontend packages to be installed and filters out the unnecessary ones.

        Args:
            imports: A dictionary containing the imports used in the current page.

        Example:
            >>> _get_frontend_packages({"react": "16.14.0", "react-dom": "16.14.0"})
        """
        page_imports = {
            i
            for i, tags in imports.items()
            if i not in constants.PackageJson.DEPENDENCIES
            and i not in constants.PackageJson.DEV_DEPENDENCIES
            and not any(i.startswith(prefix) for prefix in ["/", ".", "next/"])
            and i != ""
            and any(tag.install for tag in tags)
        }
        frontend_packages = get_config().frontend_packages
        _frontend_packages = []
        for package in frontend_packages:
            if package in (get_config().tailwind or {}).get("plugins", []):  # type: ignore
                console.warn(
                    f"Tailwind packages are inferred from 'plugins', remove `{package}` from `frontend_packages`"
                )
                continue
            if package in page_imports:
                console.warn(
                    f"React packages and their dependencies are inferred from Component.library and Component.lib_dependencies, remove `{package}` from `frontend_packages`"
                )
                continue
            _frontend_packages.append(package)
        page_imports.update(_frontend_packages)
        prerequisites.install_frontend_packages(page_imports, get_config())

    def _app_root(self, app_wrappers: dict[tuple[int, str], Component]) -> Component:
        for component in tuple(app_wrappers.values()):
            app_wrappers.update(component._get_all_app_wrap_components())
        order = sorted(app_wrappers, key=lambda k: k[0], reverse=True)
        root = parent = copy.deepcopy(app_wrappers[order[0]])
        for key in order[1:]:
            child = copy.deepcopy(app_wrappers[key])
            parent.children.append(child)
            parent = child
        return root

    def _should_compile(self) -> bool:
        """Check if the app should be compiled.

        Returns:
            Whether the app should be compiled.
        """
        # Check the environment variable.
        if should_skip_compile():
            return False

        # Check the nocompile file.
        if os.path.exists(constants.NOCOMPILE_FILE):
            # Delete the nocompile file
            os.remove(constants.NOCOMPILE_FILE)
            return False

        # By default, compile the app.
        return True

    def _add_overlay_to_component(self, component: Component) -> Component:
        if self.overlay_component is None:
            return component

        children = component.children
        overlay_component = self._generate_component(self.overlay_component)

        if children[0] == overlay_component:
            return component

        # recreate OverlayFragment with overlay_component as first child
        component = OverlayFragment.create(overlay_component, *children)

        return component

    def _setup_overlay_component(self):
        """If a State is not used and no overlay_component is specified, do not render the connection modal."""
        if self.state is None and self.overlay_component is default_overlay_component:
            self.overlay_component = None
        for k, component in self.pages.items():
            self.pages[k] = self._add_overlay_to_component(component)

    def _apply_decorated_pages(self):
        """Add @rx.page decorated pages to the app.

        This has to be done in the MainThread for py38 and py39 compatibility, so the
        decorated pages are added to the app before the app is compiled (in a thread)
        to workaround REF-2172.

        This can move back into `compile_` when py39 support is dropped.
        """
        # Add the @rx.page decorated pages to collect on_load events.
        for render, kwargs in DECORATED_PAGES[get_config().app_name]:
            self.add_page(render, **kwargs)

    def _compile(self, export: bool = False):
        """Compile the app and output it to the pages folder.

        Args:
            export: Whether to compile the app for export.

        Raises:
            ReflexRuntimeError: When any page uses state, but no rx.State subclass is defined.
        """
        from reflex.utils.exceptions import ReflexRuntimeError

        # Render a default 404 page if the user didn't supply one
        if constants.Page404.SLUG not in self.pages:
            self.add_custom_404_page()

        # Add the optional endpoints (_upload)
        self._add_optional_endpoints()

        if not self._should_compile():
            return

        self._setup_overlay_component()

        # Create a progress bar.
        progress = Progress(
            *Progress.get_default_columns()[:-1],
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        )

        # try to be somewhat accurate - but still not 100%
        adhoc_steps_without_executor = 6
        fixed_pages_within_executor = 5
        progress.start()
        task = progress.add_task(
            "Compiling:",
            total=len(self.pages)
            + fixed_pages_within_executor
            + adhoc_steps_without_executor,
        )

        # Get the env mode.
        config = get_config()

        # Store the compile results.
        compile_results = []

        # Add the app wrappers.
        app_wrappers: Dict[tuple[int, str], Component] = {
            # Default app wrap component renders {children}
            (0, "AppWrap"): AppWrap.create()
        }
        if self.theme is not None:
            # If a theme component was provided, wrap the app with it
            app_wrappers[(20, "Theme")] = self.theme

        progress.advance(task)

        # Fix up the style.
        self.style = evaluate_style_namespaces(self.style)

        # Track imports and custom components found.
        all_imports = {}
        custom_components = set()

        for _route, component in self.pages.items():
            # Merge the component style with the app style.
            component._add_style_recursive(self.style, self.theme)

            # Add component._get_all_imports() to all_imports.
            all_imports.update(component._get_all_imports())

            # Add the app wrappers from this component.
            app_wrappers.update(component._get_all_app_wrap_components())

            # Add the custom components from the page to the set.
            custom_components |= component._get_all_custom_components()

        progress.advance(task)

        # Perform auto-memoization of stateful components.
        (
            stateful_components_path,
            stateful_components_code,
            page_components,
        ) = compiler.compile_stateful_components(self.pages.values())

        progress.advance(task)

        # Catch "static" apps (that do not define a rx.State subclass) which are trying to access rx.State.
        if code_uses_state_contexts(stateful_components_code) and self.state is None:
            raise ReflexRuntimeError(
                "To access rx.State in frontend components, at least one "
                "subclass of rx.State must be defined in the app."
            )
        compile_results.append((stateful_components_path, stateful_components_code))

        # Compile the root document before fork.
        compile_results.append(
            compiler.compile_document_root(
                self.head_components,
                html_lang=self.html_lang,
                html_custom_attrs=self.html_custom_attrs,  # type: ignore
            )
        )

        # Compile the contexts before fork.
        compile_results.append(
            compiler.compile_contexts(self.state, self.theme),
        )
        # Fix #2992 by removing the top-level appearance prop
        if self.theme is not None:
            self.theme.appearance = None

        app_root = self._app_root(app_wrappers=app_wrappers)

        progress.advance(task)

        # Prepopulate the global ExecutorSafeFunctions class with input data required by the compile functions.
        # This is required for multiprocessing to work, in presence of non-picklable inputs.
        for route, component in zip(self.pages, page_components):
            ExecutorSafeFunctions.COMPILE_PAGE_ARGS_BY_ROUTE[route] = (
                route,
                component,
                self.state,
            )

        ExecutorSafeFunctions.COMPILE_APP_APP_ROOT = app_root
        ExecutorSafeFunctions.CUSTOM_COMPONENTS = custom_components
        ExecutorSafeFunctions.STYLE = self.style

        # Use a forking process pool, if possible.  Much faster, especially for large sites.
        # Fallback to ThreadPoolExecutor as something that will always work.
        executor = None
        if (
            platform.system() in ("Linux", "Darwin")
            and os.environ.get("REFLEX_COMPILE_PROCESSES") is not None
        ):
            executor = concurrent.futures.ProcessPoolExecutor(
                max_workers=int(os.environ.get("REFLEX_COMPILE_PROCESSES", 0)) or None,
                mp_context=multiprocessing.get_context("fork"),
            )
        else:
            executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=int(os.environ.get("REFLEX_COMPILE_THREADS", 0)) or None,
            )

        with executor:
            result_futures = []
            custom_components_future = None

            def _mark_complete(_=None):
                progress.advance(task)

            def _submit_work(fn, *args, **kwargs):
                f = executor.submit(fn, *args, **kwargs)
                f.add_done_callback(_mark_complete)
                result_futures.append(f)

            # Compile all page components.
            for route in self.pages:
                _submit_work(ExecutorSafeFunctions.compile_page, route)

            # Compile the app wrapper.
            _submit_work(ExecutorSafeFunctions.compile_app)

            # Compile the custom components.
            custom_components_future = executor.submit(
                ExecutorSafeFunctions.compile_custom_components,
            )
            custom_components_future.add_done_callback(_mark_complete)

            # Compile the root stylesheet with base styles.
            _submit_work(compiler.compile_root_stylesheet, self.stylesheets)

            # Compile the theme.
            _submit_work(ExecutorSafeFunctions.compile_theme)

            # Compile the Tailwind config.
            if config.tailwind is not None:
                config.tailwind["content"] = config.tailwind.get(
                    "content", constants.Tailwind.CONTENT
                )
                _submit_work(compiler.compile_tailwind, config.tailwind)
            else:
                _submit_work(compiler.remove_tailwind_from_postcss)

            # Wait for all compilation tasks to complete.
            for future in concurrent.futures.as_completed(result_futures):
                compile_results.append(future.result())

            # Special case for custom_components, since we need the compiled imports
            # to install proper frontend packages.
            (
                *custom_components_result,
                custom_components_imports,
            ) = custom_components_future.result()
            compile_results.append(custom_components_result)
            all_imports.update(custom_components_imports)

        # Get imports from AppWrap components.
        all_imports.update(app_root._get_all_imports())

        progress.advance(task)

        # Empty the .web pages directory.
        compiler.purge_web_pages_dir()

        progress.advance(task)
        progress.stop()

        # Install frontend packages.
        self._get_frontend_packages(all_imports)

        # Setup the next.config.js
        transpile_packages = [
            package
            for package, import_vars in all_imports.items()
            if any(import_var.transpile for import_var in import_vars)
        ]
        prerequisites.update_next_config(
            export=export,
            transpile_packages=transpile_packages,
        )

        for output_path, code in compile_results:
            compiler_utils.write_page(output_path, code)

    @contextlib.asynccontextmanager
    async def modify_state(self, token: str) -> AsyncIterator[BaseState]:
        """Modify the state out of band.

        Args:
            token: The token to modify the state for.

        Yields:
            The state to modify.

        Raises:
            RuntimeError: If the app has not been initialized yet.
        """
        if self.event_namespace is None:
            raise RuntimeError("App has not been initialized yet.")

        # Get exclusive access to the state.
        async with self.state_manager.modify_state(token) as state:
            # No other event handler can modify the state while in this context.
            yield state
            delta = state.get_delta()
            if delta:
                # When the state is modified reset dirty status and emit the delta to the frontend.
                state._clean()
                await self.event_namespace.emit_update(
                    update=StateUpdate(delta=delta),
                    sid=state.router.session.session_id,
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
                raise RuntimeError("App has not been initialized yet.")

            # Process the event.
            async for update in state._process_event(
                handler=handler, state=substate, payload=event.payload
            ):
                # Postprocess the event.
                update = await self._postprocess(state, event, update)

                # Send the update to the client.
                await self.event_namespace.emit_update(
                    update=update,
                    sid=state.router.session.session_id,
                )

        task = asyncio.create_task(_coro())
        self.background_tasks.add(task)
        # Clean up task from background_tasks set when complete.
        task.add_done_callback(self.background_tasks.discard)
        return task


async def process(
    app: App, event: Event, sid: str, headers: Dict, client_ip: str
) -> AsyncIterator[StateUpdate]:
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
        router_data.update(
            {
                constants.RouteVar.QUERY: format.format_query_params(event.router_data),
                constants.RouteVar.CLIENT_TOKEN: event.token,
                constants.RouteVar.SESSION_ID: sid,
                constants.RouteVar.HEADERS: headers,
                constants.RouteVar.CLIENT_IP: client_ip,
            }
        )
        # Get the state for the session exclusively.
        async with app.state_manager.modify_state(event.substate_token) as state:
            # re-assign only when the value is different
            if state.router_data != router_data:
                # assignment will recurse into substates and force recalculation of
                # dependent ComputedVar (dynamic route variables)
                state.router_data = router_data
                state.router = RouterData(router_data)

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
                    return

                # Process the event synchronously.
                async for update in state._process(event):
                    # Postprocess the event.
                    update = await app._postprocess(state, event, update)

                    # Yield the update.
                    yield update
    except Exception as ex:
        telemetry.send_error(ex, context="backend")
        raise


async def ping() -> str:
    """Test API endpoint.

    Returns:
        The response.
    """
    return "pong"


def upload(app: App):
    """Upload a file.

    Args:
        app: The app to upload the file for.

    Returns:
        The upload function.
    """

    async def upload_file(request: Request, files: List[UploadFile]):
        """Upload a file.

        Args:
            request: The FastAPI request object.
            files: The file(s) to upload.

        Returns:
            StreamingResponse yielding newline-delimited JSON of StateUpdate
            emitted by the upload handler.

        Raises:
            UploadValueError: if there are no args with supported annotation.
            UploadTypeError: if a background task is used as the handler.
            HTTPException: when the request does not include token / handler headers.
        """
        from reflex.utils.exceptions import UploadTypeError, UploadValueError

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

        # check if there exists any handler args with annotation, List[UploadFile]
        if isinstance(func, EventHandler):
            if func.is_background:
                raise UploadTypeError(
                    f"@rx.background is not supported for upload handler `{handler}`.",
                )
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
            raise UploadValueError(
                f"`{handler}` handler should have a parameter annotated as "
                "List[rx.UploadFile]"
            )

        # Make a copy of the files as they are closed after the request.
        # This behaviour changed from fastapi 0.103.0 to 0.103.1 as the
        # AsyncExitStack was removed from the request scope and is now
        # part of the routing function which closes this before the
        # event is handled.
        file_copies = []
        for file in files:
            content_copy = io.BytesIO()
            content_copy.write(await file.read())
            content_copy.seek(0)
            file_copies.append(
                UploadFile(
                    file=content_copy,
                    filename=file.filename,
                    size=file.size,
                    headers=file.headers,
                )
            )

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

    # Keep a mapping between socket ID and client token.
    token_to_sid: dict[str, str] = {}

    # Keep a mapping between client token and socket ID.
    sid_to_token: dict[str, str] = {}

    def __init__(self, namespace: str, app: App):
        """Initialize the event namespace.

        Args:
            namespace: The namespace.
            app: The application object.
        """
        super().__init__(namespace)
        self.app = app

    def on_connect(self, sid, environ):
        """Event for when the websocket is connected.

        Args:
            sid: The Socket.IO session id.
            environ: The request information, including HTTP headers.
        """
        pass

    def on_disconnect(self, sid):
        """Event for when the websocket disconnects.

        Args:
            sid: The Socket.IO session id.
        """
        disconnect_token = self.sid_to_token.pop(sid, None)
        if disconnect_token:
            self.token_to_sid.pop(disconnect_token, None)

    async def emit_update(self, update: StateUpdate, sid: str) -> None:
        """Emit an update to the client.

        Args:
            update: The state update to send.
            sid: The Socket.IO session id.
        """
        # Creating a task prevents the update from being blocked behind other coroutines.
        await asyncio.create_task(
            self.emit(str(constants.SocketEvent.EVENT), update.json(), to=sid)
        )

    async def on_event(self, sid, data):
        """Event for receiving front-end websocket events.

        Args:
            sid: The Socket.IO session id.
            data: The event data.
        """
        # Get the event.
        event = Event.parse_raw(data)

        self.token_to_sid[event.token] = sid
        self.sid_to_token[sid] = event.token

        # Get the event environment.
        assert self.app.sio is not None
        environ = self.app.sio.get_environ(sid, self.namespace)
        assert environ is not None

        # Get the client headers.
        headers = {
            k.decode("utf-8"): v.decode("utf-8")
            for (k, v) in environ["asgi.scope"]["headers"]
        }

        # Get the client IP
        try:
            client_ip = environ["asgi.scope"]["client"][0]
        except (KeyError, IndexError):
            client_ip = environ.get("REMOTE_ADDR", "0.0.0.0")

        # Process the events.
        async for update in process(self.app, event, sid, headers, client_ip):
            # Emit the update from processing the event.
            await self.emit_update(update=update, sid=sid)

    async def on_ping(self, sid):
        """Event for testing the API endpoint.

        Args:
            sid: The Socket.IO session id.
        """
        # Emit the test event.
        await self.emit(str(constants.SocketEvent.PING), "pong", to=sid)
