"""The main Reflex app."""

import asyncio
import inspect
import os
from multiprocessing.pool import ThreadPool
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from fastapi import FastAPI, UploadFile
from fastapi.middleware import cors
from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn
from socketio import ASGIApp, AsyncNamespace, AsyncServer
from starlette_admin.contrib.sqla.admin import Admin
from starlette_admin.contrib.sqla.view import ModelView

from reflex import constants
from reflex.admin import AdminDash
from reflex.base import Base
from reflex.compiler import compiler
from reflex.compiler import utils as compiler_utils
from reflex.components.component import Component, ComponentStyle
from reflex.components.layout.fragment import Fragment
from reflex.config import get_config
from reflex.event import Event, EventHandler, EventSpec
from reflex.middleware import HydrateMiddleware, Middleware
from reflex.model import Model
from reflex.route import (
    DECORATED_ROUTES,
    catchall_in_route,
    catchall_prefix,
    get_route_args,
    verify_route_validity,
)
from reflex.state import DefaultState, State, StateManager, StateUpdate
from reflex.utils import console, format, types

# Define custom types.
ComponentCallable = Callable[[], Component]
Reducer = Callable[[Event], Coroutine[Any, Any, StateUpdate]]


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
    state: Type[State] = DefaultState

    # Class to manage many client states.
    state_manager: StateManager = StateManager()

    # The styling to apply to each component.
    style: ComponentStyle = {}

    # Middleware to add to the app.
    middleware: List[Middleware] = []

    # List of event handlers to trigger when a page loads.
    load_events: Dict[str, List[Union[EventHandler, EventSpec]]] = {}

    # Admin dashboard
    admin_dash: Optional[AdminDash] = None

    # The component to render if there is a connection error to the server.
    connect_error_component: Optional[Component] = None

    # The async server name space
    event_namespace: Optional[AsyncNamespace] = None

    def __init__(self, *args, **kwargs):
        """Initialize the app.

        Args:
            *args: Args to initialize the app with.
            **kwargs: Kwargs to initialize the app with.

        Raises:
            ValueError: If the event namespace is not provided in the config.
                        Also, if there are multiple client subclasses of rx.State(Subclasses of rx.State should consist
                        of the DefaultState and the client app state).
        """
        super().__init__(*args, **kwargs)
        state_subclasses = State.__subclasses__()
        is_testing_env = constants.PYTEST_CURRENT_TEST in os.environ

        # Special case to allow test cases have multiple subclasses of rx.State.
        if not is_testing_env:
            # Only the default state and the client state should be allowed as subclasses.
            if len(state_subclasses) > 2:
                raise ValueError(
                    "rx.State has been subclassed multiple times. Only one subclass is allowed"
                )
            if self.state != DefaultState:
                console.deprecate(
                    "Passing the state as keyword argument to `rx.App` is deprecated. "
                    "The base state will automatically be inferred as the subclass of `rx.State`."
                )
            self.state = state_subclasses[-1]

        # Get the config
        config = get_config()

        # Add middleware.
        self.middleware.append(HydrateMiddleware())

        # Set up the state manager.
        self.state_manager.setup(state=self.state)

        # Set up the API.
        self.api = FastAPI()
        self.add_cors()
        self.add_default_endpoints()

        # Set up the Socket.IO AsyncServer.
        self.sio = AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*"
            if config.cors_allowed_origins == constants.CORS_ALLOWED_ORIGINS
            else config.cors_allowed_origins,
            cors_credentials=config.cors_credentials,
            max_http_buffer_size=config.polling_max_http_buffer_size,
            ping_interval=constants.PING_INTERVAL,
            ping_timeout=constants.PING_TIMEOUT,
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

        # Set up the admin dash.
        self.setup_admin_dash()

    def __repr__(self) -> str:
        """Get the string representation of the app.

        Returns:
            The string representation of the app.
        """
        return f"<App state={self.state.__name__}>"

    def __call__(self) -> FastAPI:
        """Run the backend api instance.

        Returns:
            The backend api.
        """
        return self.api

    def add_default_endpoints(self):
        """Add the default endpoints."""
        # To test the server.
        self.api.get(str(constants.Endpoint.PING))(ping)

        # To upload files.
        self.api.post(str(constants.Endpoint.UPLOAD))(upload(self))

    def add_cors(self):
        """Add CORS middleware to the app."""
        self.api.add_middleware(
            cors.CORSMiddleware,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            allow_origins=["*"],
        )

    async def preprocess(self, state: State, event: Event) -> Optional[StateUpdate]:
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
                out = await middleware.preprocess(app=self, state=state, event=event)
            else:
                out = middleware.preprocess(app=self, state=state, event=event)
            if out is not None:
                return out  # type: ignore

    async def postprocess(
        self, state: State, event: Event, update: StateUpdate
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
                    app=self, state=state, event=event, update=update
                )
            else:
                out = middleware.postprocess(
                    app=self, state=state, event=event, update=update
                )
            if out is not None:
                return out  # type: ignore
        return update

    def add_middleware(self, middleware: Middleware, index: Optional[int] = None):
        """Add middleware to the app.

        Args:
            middleware: The middleware to add.
            index: The index to add the middleware at.
        """
        if index is None:
            self.middleware.append(middleware)
        else:
            self.middleware.insert(index, middleware)

    def add_page(
        self,
        component: Union[Component, ComponentCallable],
        route: Optional[str] = None,
        title: str = constants.DEFAULT_TITLE,
        description: str = constants.DEFAULT_DESCRIPTION,
        image=constants.DEFAULT_IMAGE,
        on_load: Optional[
            Union[EventHandler, EventSpec, List[Union[EventHandler, EventSpec]]]
        ] = None,
        meta: List[Dict] = constants.DEFAULT_META_LIST,
        script_tags: Optional[List[Component]] = None,
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

        Raises:
            TypeError: If an invalid var operation is used.
        """
        # If the route is not set, get it from the callable.
        if route is None:
            assert isinstance(
                component, Callable
            ), "Route must be set if component is not a callable."
            route = component.__name__

        # Check if the route given is valid
        verify_route_validity(route)

        # Apply dynamic args to the route.
        self.state.setup_dynamic_args(get_route_args(route))

        # Generate the component if it is a callable.
        try:
            component = component if isinstance(component, Component) else component()
        except TypeError as e:
            message = str(e)
            if "BaseVar" in message or "ComputedVar" in message:
                raise TypeError(
                    "You may be trying to use an invalid Python function on a state var. "
                    "When referencing a var inside your render code, only limited var operations are supported. "
                    "See the var operation docs here: https://pynecone.io/docs/state/vars "
                ) from e
            raise e

        # Wrap the component in a fragment.
        component = Fragment.create(component)

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
            component.children.extend(script_tags)

        # Format the route.
        route = format.format_route(route)

        # Add the page.
        self._check_routes_conflict(route)
        self.pages[route] = component

        # Add the load events.
        if on_load:
            if not isinstance(on_load, list):
                on_load = [on_load]
            self.load_events[route] = on_load

    def get_load_events(self, route: str) -> List[Union[EventHandler, EventSpec]]:
        """Get the load events for a route.

        Args:
            route: The route to get the load events for.

        Returns:
            The load events for the route.
        """
        route = route.lstrip("/")
        if route == "":
            route = constants.INDEX_ROUTE
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
        component,
        title=None,
        image=None,
        description=None,
        meta=constants.DEFAULT_META_LIST,
    ):
        """Define a custom 404 page for any url having no match.

        If there is no page defined on 'index' route, add the 404 page to it.
        If there is no global catchall defined, add the 404 page with a catchall

        Args:
            component: The component to display at the page.
            title: The title of the page.
            description: The description of the page.
            image: The image to display on the page.
            meta: The metadata of the page.
        """
        title = title or constants.TITLE_404
        image = image or constants.FAVICON_404
        description = description or constants.DESCRIPTION_404

        component = component if isinstance(component, Component) else component()

        compiler_utils.add_meta(
            component,
            title=title,
            image=image,
            description=description,
            meta=meta,
        )

        froute = format.format_route
        self.pages[froute(constants.SLUG_404)] = component

    def setup_admin_dash(self):
        """Setup the admin dash."""
        # Get the config.
        config = get_config()
        if config.admin_dash and config.admin_dash.models:
            # Build the admin dashboard
            admin = (
                config.admin_dash.admin
                if config.admin_dash.admin
                else Admin(
                    engine=Model.get_db_engine(),
                    title="Reflex Admin Dashboard",
                    logo_url="https://pynecone.io/logo.png",
                )
            )

            for model in config.admin_dash.models:
                view = config.admin_dash.view_overrides.get(model, ModelView)
                admin.add_view(view(model))

            admin.mount_to(self.api)

    def compile(self):
        """Compile the app and output it to the pages folder."""
        # Create a progress bar.
        progress = Progress(
            *Progress.get_default_columns()[:-1],
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        )
        task = progress.add_task("Compiling: ", total=len(self.pages))

        for render, kwargs in DECORATED_ROUTES:
            self.add_page(render, **kwargs)

        # Get the env mode.
        config = get_config()

        # Empty the .web pages directory
        compiler.purge_web_pages_dir()

        # Store the compile results.
        compile_results = []

        # Compile the pages in parallel.
        custom_components = set()
        thread_pool = ThreadPool()
        with progress:
            for route, component in self.pages.items():
                progress.advance(task)
                component.add_style(self.style)
                compile_results.append(
                    thread_pool.apply_async(
                        compiler.compile_page,
                        args=(
                            route,
                            component,
                            self.state,
                            self.connect_error_component,
                        ),
                    )
                )
                # Add the custom components from the page to the set.
                custom_components |= component.get_custom_components()
        thread_pool.close()
        thread_pool.join()

        # Get the results.
        compile_results = [result.get() for result in compile_results]

        # Compile the custom components.
        compile_results.append(compiler.compile_components(custom_components))

        # Compile the root document with base styles and fonts.
        compile_results.append(compiler.compile_document_root(self.stylesheets))

        # Compile the theme.
        compile_results.append(compiler.compile_theme(self.style))

        # Compile the Tailwind config.
        if config.tailwind is not None:
            config.tailwind["content"] = config.tailwind.get(
                "content", constants.TAILWIND_CONTENT
            )
            compile_results.append(compiler.compile_tailwind(config.tailwind))

        # Write the pages at the end to trigger the NextJS hot reload only once.
        thread_pool = ThreadPool()
        for output_path, code in compile_results:
            compiler_utils.write_page(output_path, code)
            thread_pool.apply_async(compiler_utils.write_page, args=(output_path, code))
        thread_pool.close()
        thread_pool.join()


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
    # Get the state for the session.
    state = app.state_manager.get_state(event.token)

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
    # re-assign only when the value is different
    if state.router_data != router_data:
        # assignment will recurse into substates and force recalculation of
        # dependent ComputedVar (dynamic route variables)
        state.router_data = router_data

    # Preprocess the event.
    update = await app.preprocess(state, event)

    # If there was an update, yield it.
    if update is not None:
        yield update

    # Only process the event if there is no update.
    else:
        # Process the event.
        async for update in state._process(event):
            # Postprocess the event.
            update = await app.postprocess(state, event, update)

            # Yield the update.
            yield update

    # Set the state for the session.
    app.state_manager.set_state(event.token, state)


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

    async def upload_file(files: List[UploadFile]):
        """Upload a file.

        Args:
            files: The file(s) to upload.

        Raises:
            ValueError: if there are no args with supported annotation.
        """
        assert files[0].filename is not None
        token, handler = files[0].filename.split(":")[:2]
        for file in files:
            assert file.filename is not None
            file.filename = file.filename.split(":")[-1]
        # Get the state for the session.
        state = app.state_manager.get_state(token)
        # get the current session ID
        sid = state.get_sid()
        # get the current state(parent state/substate)
        path = handler.split(".")[:-1]
        current_state = state.get_substate(path)
        handler_upload_param: Tuple = ()

        # get handler function
        func = getattr(current_state, handler.split(".")[-1])

        # check if there exists any handler args with annotation, List[UploadFile]
        for k, v in inspect.getfullargspec(
            func.fn if isinstance(func, EventHandler) else func
        ).annotations.items():
            if types.is_generic_alias(v) and types._issubclass(
                v.__args__[0], UploadFile
            ):
                handler_upload_param = (k, v)
                break

        if not handler_upload_param:
            raise ValueError(
                f"`{handler}` handler should have a parameter annotated as List["
                f"rx.UploadFile]"
            )

        event = Event(
            token=token,
            name=handler,
            payload={handler_upload_param[0]: files},
        )
        async for update in state._process(event):
            # Postprocess the event.
            update = await app.postprocess(state, event, update)
            # Send update to client
            await asyncio.create_task(
                app.event_namespace.emit(str(constants.SocketEvent.EVENT), update.json(), to=sid)  # type: ignore
            )
        # Set the state for the session.
        app.state_manager.set_state(event.token, state)

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
        """Event for when the websocket disconnects.

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
            # Emit the event.
            await asyncio.create_task(
                self.emit(str(constants.SocketEvent.EVENT), update.json(), to=sid)
            )

    async def on_ping(self, sid):
        """Event for testing the API endpoint.

        Args:
            sid: The Socket.IO session id.
        """
        # Emit the test event.
        await self.emit(str(constants.SocketEvent.PING), "pong", to=sid)
