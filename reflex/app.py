"""The main Reflex app."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import copy
import functools
import os
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
from reflex.components import connection_modal, connection_pulser
from reflex.components.base.app_wrap import AppWrap
from reflex.components.base.fragment import Fragment
from reflex.components.component import (
    Component,
    ComponentStyle,
    evaluate_style_namespaces,
)
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
    catchall_in_route,
    catchall_prefix,
    get_route_args,
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
from reflex.utils.exec import is_testing_env
from reflex.utils.imports import ImportVar

# Define custom types.
ComponentCallable = Callable[[], Component]
Reducer = Callable[[Event], Coroutine[Any, Any, StateUpdate]]


def default_overlay_component() -> Component:
    """Default overlay_component attribute for App.

    Returns:
        The default overlay_component, which is a connection_modal.
    """
    return Fragment.create(connection_pulser(), connection_modal())


class OverlayFragment(Fragment):
    """Alias for Fragment, used to wrap the overlay_component."""

    pass


class App(Base):
    """A Reflex application."""

    # A map from a page route to the component to render.
    pages: Dict[str, Component] = {}

    # A list of URLs to stylesheets to include in the app.
    stylesheets: List[str] = []

    # The backend API object.
    api: FastAPI = None  # type: ignore

    # The Socket.IO AsyncServer.
    sio: Optional[AsyncServer] = None

    # The socket app.
    socket_app: Optional[ASGIApp] = None

    # The state class to use for the app.
    state: Optional[Type[BaseState]] = None

    # Class to manage many client states.
    _state_manager: Optional[StateManager] = None

    # The styling to apply to each component.
    style: ComponentStyle = {}

    # Middleware to add to the app.
    middleware: List[Middleware] = []

    # List of event handlers to trigger when a page loads.
    load_events: Dict[str, List[Union[EventHandler, EventSpec]]] = {}

    # Admin dashboard
    admin_dash: Optional[AdminDash] = None

    # The async server name space
    event_namespace: Optional[EventNamespace] = None

    # Components to add to the head of every page.
    head_components: List[Component] = []

    # The language to add to the html root tag of every page.
    html_lang: Optional[str] = None

    # Attributes to add to the html root tag of every page.
    html_custom_attrs: Optional[Dict[str, str]] = None

    # A component that is present on every page.
    overlay_component: Optional[
        Union[Component, ComponentCallable]
    ] = default_overlay_component

    # Background tasks that are currently running
    background_tasks: Set[asyncio.Task] = set()

    # The radix theme for the entire app
    theme: Optional[Component] = themes.theme(accent_color="blue")

    def __init__(self, *args, **kwargs):
        """Initialize the app.

        Args:
            *args: Args to initialize the app with.
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
        super().__init__(*args, **kwargs)
        base_state_subclasses = BaseState.__subclasses__()

        # Special case to allow test cases have multiple subclasses of rx.BaseState.
        if not is_testing_env():
            # Only one Base State class is allowed.
            if len(base_state_subclasses) > 1:
                raise ValueError(
                    "rx.BaseState cannot be subclassed multiple times. use rx.State instead"
                )

            if "state" in kwargs:
                console.deprecate(
                    feature_name="`state` argument for App()",
                    reason="due to all `rx.State` subclasses being inferred.",
                    deprecation_version="0.3.5",
                    removal_version="0.5.0",
                )
        # Add middleware.
        self.middleware.append(HydrateMiddleware())

        # Set up the API.
        self.api = FastAPI()
        self.add_cors()
        self.add_default_endpoints()

        self.setup_state()

        # Set up the admin dash.
        self.setup_admin_dash()

    def enable_state(self) -> None:
        """Enable state for the app."""
        if not self.state:
            self.state = State
            self.setup_state()

    def setup_state(self) -> None:
        """Set up the state for the app.

        Raises:
            ValueError: If the event namespace is not provided in the config.
                        If the state has not been enabled.
        """
        if not self.state:
            return

        config = get_config()

        # Set up the state manager.
        self._state_manager = StateManager.create(state=self.state)

        # Set up the Socket.IO AsyncServer.
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

        # Create the socket app. Note event endpoint constant replaces the default 'socket.io' path.
        self.socket_app = ASGIApp(self.sio, socketio_path="")
        namespace = config.get_event_namespace()

        if not namespace:
            raise ValueError("event namespace must be provided in the config.")

        # Create the event namespace and attach the main app. Not related to any paths.
        self.event_namespace = EventNamespace(namespace, self)

        # Register the event namespace with the socket.
        self.sio.register_namespace(self.event_namespace)
        # Mount the socket app with the API.
        self.api.mount(str(constants.Endpoint.EVENT), self.socket_app)

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

    def add_default_endpoints(self):
        """Add default api endpoints (ping)."""
        # To test the server.
        self.api.get(str(constants.Endpoint.PING))(ping)

    def add_optional_endpoints(self):
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

    def add_cors(self):
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

    async def preprocess(self, state: BaseState, event: Event) -> StateUpdate | None:
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

    async def postprocess(
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
                    app=self, state=state, event=event, update=update  # type: ignore
                )
            else:
                out = middleware.postprocess(
                    app=self, state=state, event=event, update=update  # type: ignore
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
            TypeError: When an invalid component function is passed.
            exceptions.MatchTypeError: If the return types of match cases in rx.match are different.
        """
        try:
            return component if isinstance(component, Component) else component()
        except exceptions.MatchTypeError:
            raise
        except TypeError as e:
            message = str(e)
            if "BaseVar" in message or "ComputedVar" in message:
                raise TypeError(
                    "You may be trying to use an invalid Python function on a state var. "
                    "When referencing a var inside your render code, only limited var operations are supported. "
                    "See the var operation docs here: https://reflex.dev/docs/vars/var-operations/"
                ) from e
            raise e

    def add_page(
        self,
        component: Component | ComponentCallable,
        route: str | None = None,
        title: str = constants.DefaultPage.TITLE,
        description: str = constants.DefaultPage.DESCRIPTION,
        image: str = constants.DefaultPage.IMAGE,
        on_load: (
            EventHandler | EventSpec | list[EventHandler | EventSpec] | None
        ) = None,
        meta: list[dict[str, str]] = constants.DefaultPage.META_LIST,
        script_tags: list[Component] | None = None,
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
            script_tags: List of script tags to be added to component
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

        # Setup dynamic args for the route.
        # this state assignment is only required for tests using the deprecated state kwarg for App
        state = self.state if self.state else State
        state.setup_dynamic_args(get_route_args(route))

        # Generate the component if it is a callable.
        component = self._generate_component(component)

        # Ensure state is enabled if this page uses state.
        if self.state is None:
            if on_load or component._has_event_triggers():
                self.enable_state()
            else:
                for var in component._get_vars(include_children=True):
                    if not var._var_data:
                        continue
                    if not var._var_data.state:
                        continue
                    self.enable_state()
                    break

        component = OverlayFragment.create(component)

        # Add meta information to the component.
        compiler_utils.add_meta(
            component,
            title=title,
            image=image,
            description=description,
            meta=meta,
        )

        # Add script tags if given
        if script_tags:
            console.deprecate(
                feature_name="Passing script tags to add_page",
                reason="Add script components as children to the page component instead",
                deprecation_version="0.2.9",
                removal_version="0.5.0",
            )
            component.children.extend(script_tags)

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
            ValueError: exception showing which conflict exist with the route to be added

        Args:
            new_route: the route being newly added.
        """
        newroute_catchall = catchall_in_route(new_route)
        if not newroute_catchall:
            return

        for route in self.pages:
            route = "" if route == "index" else route

            if new_route.startswith(f"{route}/[[..."):
                raise ValueError(
                    f"You cannot define a route with the same specificity as a optional catch-all route ('{route}' and '{new_route}')"
                )

            route_catchall = catchall_in_route(route)
            if (
                route_catchall
                and newroute_catchall
                and catchall_prefix(route) == catchall_prefix(new_route)
            ):
                raise ValueError(
                    f"You cannot use multiple catchall for the same dynamic route ({route} !== {new_route})"
                )

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
        If there is no global catchall defined, add the 404 page with a catchall

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

    def setup_admin_dash(self):
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

    def get_frontend_packages(self, imports: Dict[str, set[ImportVar]]):
        """Gets the frontend packages to be installed and filters out the unnecessary ones.

        Args:
            imports: A dictionary containing the imports used in the current page.

        Example:
            >>> get_frontend_packages({"react": "16.14.0", "react-dom": "16.14.0"})
        """
        page_imports = {
            i
            for i, tags in imports.items()
            if i
            not in [
                *constants.PackageJson.DEPENDENCIES.keys(),
                *constants.PackageJson.DEV_DEPENDENCIES.keys(),
            ]
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
            app_wrappers.update(component.get_app_wrap_components())
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
        if os.environ.get(constants.SKIP_COMPILE_ENV_VAR) == "yes":
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

    def compile(self):
        """compile_() is the new function for performing compilation.
        Reflex framework will call it automatically as needed.
        """
        console.deprecate(
            feature_name="app.compile()",
            reason="Explicit calls to app.compile() are not needed."
            " Method will be removed in 0.4.0",
            deprecation_version="0.3.8",
            removal_version="0.5.0",
        )
        return

    def compile_(self):
        """Compile the app and output it to the pages folder.

        Raises:
            RuntimeError: When any page uses state, but no rx.State subclass is defined.
        """
        # add the pages before the compile check so App know onload methods
        for render, kwargs in DECORATED_PAGES:
            self.add_page(render, **kwargs)

        # Render a default 404 page if the user didn't supply one
        if constants.Page404.SLUG not in self.pages:
            self.add_custom_404_page()

        # Add the optional endpoints (_upload)
        self.add_optional_endpoints()

        if not self._should_compile():
            return

        self._setup_overlay_component()

        # Create a progress bar.
        progress = Progress(
            *Progress.get_default_columns()[:-1],
            MofNCompleteColumn(),
            TimeElapsedColumn(),
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

        # Fix up the style.
        self.style = evaluate_style_namespaces(self.style)

        # Track imports and custom components found.
        all_imports = {}
        custom_components = set()

        # Compile the pages in parallel.
        with progress, concurrent.futures.ThreadPoolExecutor() as thread_pool:
            fixed_pages = 7
            task = progress.add_task("Compiling:", total=len(self.pages) + fixed_pages)

            def mark_complete(_=None):
                progress.advance(task)

            for _route, component in self.pages.items():
                # Merge the component style with the app style.
                component.add_style(self.style)

                component.apply_theme(self.theme)

                # Add component.get_imports() to all_imports.
                all_imports.update(component.get_imports())

                # Add the app wrappers from this component.
                app_wrappers.update(component.get_app_wrap_components())

                # Add the custom components from the page to the set.
                custom_components |= component.get_custom_components()

            # Perform auto-memoization of stateful components.
            (
                stateful_components_path,
                stateful_components_code,
                page_components,
            ) = compiler.compile_stateful_components(self.pages.values())

            # Catch "static" apps (that do not define a rx.State subclass) which are trying to access rx.State.
            if (
                code_uses_state_contexts(stateful_components_code)
                and self.state is None
            ):
                raise RuntimeError(
                    "To access rx.State in frontend components, at least one "
                    "subclass of rx.State must be defined in the app."
                )
            compile_results.append((stateful_components_path, stateful_components_code))

            result_futures = []

            def submit_work(fn, *args, **kwargs):
                """Submit work to the thread pool and add a callback to mark the task as complete.

                The Future will be added to the `result_futures` list.

                Args:
                    fn: The function to submit.
                    *args: The args to submit.
                    **kwargs: The kwargs to submit.
                """
                f = thread_pool.submit(fn, *args, **kwargs)
                f.add_done_callback(mark_complete)
                result_futures.append(f)

            # Compile all page components.
            for route, component in zip(self.pages, page_components):
                submit_work(
                    compiler.compile_page,
                    route,
                    component,
                    self.state,
                )

            # Compile the app wrapper.
            app_root = self._app_root(app_wrappers=app_wrappers)
            submit_work(compiler.compile_app, app_root)

            # Compile the custom components.
            submit_work(compiler.compile_components, custom_components)

            # Compile the root stylesheet with base styles.
            submit_work(compiler.compile_root_stylesheet, self.stylesheets)

            # Compile the root document.
            submit_work(
                compiler.compile_document_root,
                self.head_components,
                html_lang=self.html_lang,
                html_custom_attrs=self.html_custom_attrs,
            )

            # Compile the theme.
            submit_work(compiler.compile_theme, style=self.style)

            # Compile the contexts.
            submit_work(compiler.compile_contexts, self.state, self.theme)

            # Compile the Tailwind config.
            if config.tailwind is not None:
                config.tailwind["content"] = config.tailwind.get(
                    "content", constants.Tailwind.CONTENT
                )
                submit_work(compiler.compile_tailwind, config.tailwind)
            else:
                submit_work(compiler.remove_tailwind_from_postcss)

            # Get imports from AppWrap components.
            all_imports.update(app_root.get_imports())

            # Iterate through all the custom components and add their imports to the all_imports.
            for component in custom_components:
                all_imports.update(component.get_imports())

            # Wait for all compilation tasks to complete.
            for future in concurrent.futures.as_completed(result_futures):
                compile_results.append(future.result())

            # Empty the .web pages directory.
            compiler.purge_web_pages_dir()

            # Avoid flickering when installing frontend packages
            progress.stop()

            # Install frontend packages.
            self.get_frontend_packages(all_imports)

            # Write the pages at the end to trigger the NextJS hot reload only once.
            write_page_futures = []
            for output_path, code in compile_results:
                write_page_futures.append(
                    thread_pool.submit(compiler_utils.write_page, output_path, code)
                )
            for future in concurrent.futures.as_completed(write_page_futures):
                future.result()

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
                update = await self.postprocess(state, event, update)

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

    Yields:
        The state updates after processing the event.
    """
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
        update = await app.preprocess(state, event)

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
                update = await app.postprocess(state, event, update)

                # Yield the update.
                yield update


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
            ValueError: if there are no args with supported annotation.
            TypeError: if a background task is used as the handler.
            HTTPException: when the request does not include token / handler headers.
        """
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
                raise TypeError(
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
            raise ValueError(
                f"`{handler}` handler should have a parameter annotated as "
                "List[rx.UploadFile]"
            )

        event = Event(
            token=token,
            name=handler,
            payload={handler_upload_param[0]: files},
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
                    update = await app.postprocess(state, event, update)
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
        pass

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
        client_ip = environ["REMOTE_ADDR"]

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
