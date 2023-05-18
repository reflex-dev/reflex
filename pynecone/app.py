"""The main Pynecone app."""

import asyncio
import inspect
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, Type, Union

from fastapi import FastAPI, UploadFile
from fastapi.middleware import cors
from socketio import ASGIApp, AsyncNamespace, AsyncServer

from pynecone import constants
from pynecone.base import Base
from pynecone.compiler import compiler
from pynecone.compiler import utils as compiler_utils
from pynecone.components.component import Component, ComponentStyle
from pynecone.config import get_config
from pynecone.event import Event, EventHandler
from pynecone.middleware import HydrateMiddleware, Middleware
from pynecone.model import Model
from pynecone.route import (
    DECORATED_ROUTES,
    catchall_in_route,
    catchall_prefix,
    get_route_args,
    verify_route_validity,
)
from pynecone.state import DefaultState, State, StateManager, StateUpdate
from pynecone.utils import format, types

# Define custom types.
ComponentCallable = Callable[[], Component]
Reducer = Callable[[Event], Coroutine[Any, Any, StateUpdate]]


class App(Base):
    """A Pynecone application."""

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
    load_events: Dict[str, List[EventHandler]] = {}

    def __init__(self, *args, **kwargs):
        """Initialize the app.

        Args:
            *args: Args to initialize the app with.
            **kwargs: Kwargs to initialize the app with.
        """
        super().__init__(*args, **kwargs)

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

        # Set up CORS options.
        cors_allowed_origins = config.cors_allowed_origins
        if config.cors_allowed_origins == [constants.CORS_ALLOWED_ORIGINS]:
            cors_allowed_origins = "*"

        # Set up the Socket.IO AsyncServer.
        self.sio = AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=cors_allowed_origins,
            cors_credentials=config.cors_credentials,
            max_http_buffer_size=config.polling_max_http_buffer_size,
            ping_interval=constants.PING_INTERVAL,
            ping_timeout=constants.PING_TIMEOUT,
        )

        # Create the socket app. Note event endpoint constant replaces the default 'socket.io' path.
        self.socket_app = ASGIApp(self.sio, socketio_path="")

        # Create the event namespace and attach the main app. Not related to any paths.
        event_namespace = EventNamespace("/event", self)

        # Register the event namespace with the socket.
        self.sio.register_namespace(event_namespace)

        # Mount the socket app with the API.
        self.api.mount(str(constants.Endpoint.EVENT), self.socket_app)

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
        on_load: Optional[Union[EventHandler, List[EventHandler]]] = None,
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

        # Add meta information to the component.
        compiler_utils.add_meta(
            component, title=title, image=image, description=description, meta=meta
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

    def get_load_events(self, route: str) -> List[EventHandler]:
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
            component, title=title, image=image, description=description, meta=meta
        )

        froute = format.format_route
        if (froute(constants.ROOT_404) not in self.pages) and (
            not any(page.startswith("[[...") for page in self.pages)
        ):
            self.pages[froute(constants.ROOT_404)] = component
        if not any(
            page.startswith("[...") or page.startswith("[[...") for page in self.pages
        ):
            self.pages[froute(constants.SLUG_404)] = component

    def compile(self):
        """Compile the app and output it to the pages folder."""
        for render, kwargs in DECORATED_ROUTES:
            self.add_page(render, **kwargs)

        # Get the env mode.
        config = get_config()

        # Update models during hot reload.
        if config.db_url is not None:
            Model.create_all()

        # Empty the .web pages directory
        compiler.purge_web_pages_dir()

        # Compile the root document with base styles and fonts.
        compiler.compile_document_root(self.stylesheets)

        # Compile the theme.
        compiler.compile_theme(self.style)

        # Compile the pages.
        custom_components = set()
        for route, component in self.pages.items():
            component.add_style(self.style)
            compiler.compile_page(route, component, self.state)

            # Add the custom components from the page to the set.
            custom_components |= component.get_custom_components()

        # Compile the custom components.
        compiler.compile_components(custom_components)


async def process(
    app: App, event: Event, sid: str, headers: Dict, client_ip: str
) -> StateUpdate:
    """Process an event.

    Args:
        app: The app to process the event for.
        event: The event to process.
        sid: The Socket.IO session id.
        headers: The client headers.
        client_ip: The client_ip.

    Returns:
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

    # Only process the event if there is no update.
    if update is None:
        # Apply the event to the state.
        update = await state._process(event)

        # Postprocess the event.
        update = await app.postprocess(state, event, update)

    # Update the state.
    app.state_manager.set_state(event.token, state)

    # Return the update.
    return update


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

        Returns:
            The state update after processing the event.

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
                f"pc.UploadFile]"
            )

        event = Event(
            token=token,
            name=handler,
            payload={handler_upload_param[0]: files},
        )
        update = await state._process(event)
        return update

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
        update = await process(self.app, event, sid, headers, client_ip)

        # Emit the event.
        await self.emit(str(constants.SocketEvent.EVENT), update.json(), to=sid)  # type: ignore

    async def on_ping(self, sid):
        """Event for testing the API endpoint.

        Args:
            sid: The Socket.IO session id.
        """
        # Emit the test event.
        await self.emit(str(constants.SocketEvent.PING), "pong", to=sid)
