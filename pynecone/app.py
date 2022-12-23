"""The main Pynecone app."""

from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, Type, Union

from fastapi import FastAPI, WebSocket,APIRouter
from fastapi.middleware import cors

from pynecone import constants, utils
from pynecone.base import Base
from pynecone.compiler import compiler
from pynecone.compiler import utils as compiler_utils
from pynecone.components.component import Component, ComponentStyle
from pynecone.event import Event
from pynecone.middleware import HydrateMiddleware, Middleware
from pynecone.model import Model
from pynecone.state import DefaultState, Delta, State, StateManager, StateUpdate

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

    # The state class to use for the app.
    state: Type[State] = DefaultState

    # Class to manage many client states.
    state_manager: StateManager = StateManager()

    # The styling to apply to each component.
    style: ComponentStyle = {}

    # Middleware to add to the app.
    middleware: List[Middleware] = []

    def __init__(self, *args, **kwargs):
        """Initialize the app.

        Args:
            *args: Args to initialize the app with.
            **kwargs: Kwargs to initialize the app with.
        """
        super().__init__(*args, **kwargs)

        # Add middleware.
        self.middleware.append(HydrateMiddleware())

        # Set up the state manager.
        self.state_manager.setup(state=self.state)

        # Set up the API.
        
        self.api = FastAPI()
        self.add_cors()
        self.add_default_endpoints()

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
        self.api.get(str(constants.Endpoint.PING))(_ping)

        # To make state changes.
        self.api.websocket(str(constants.Endpoint.EVENT))(_event(app=self))

    def add_cors(self):
        """Add CORS middleware to the app."""
        self.api.add_middleware(
            cors.CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def preprocess(self, state: State, event: Event) -> Optional[Delta]:
        """Preprocess the event.

        This is where middleware can modify the event before it is processed.
        Each middleware is called in the order it was added to the app.

        If a middleware returns a delta, the event is not processed and the
        delta is returned.

        Args:
            state: The state to preprocess.
            event: The event to preprocess.

        Returns:
            An optional state to return.
        """
        for middleware in self.middleware:
            out = middleware.preprocess(app=self, state=state, event=event)
            if out is not None:
                return out

    def postprocess(self, state: State, event: Event, delta: Delta) -> Optional[Delta]:
        """Postprocess the event.

        This is where middleware can modify the delta after it is processed.
        Each middleware is called in the order it was added to the app.

        If a middleware returns a delta, the delta is not processed and the
        delta is returned.

        Args:
            state: The state to postprocess.
            event: The event to postprocess.
            delta: The delta to postprocess.

        Returns:
            An optional state to return.
        """
        for middleware in self.middleware:
            out = middleware.postprocess(
                app=self, state=state, event=event, delta=delta
            )
            if out is not None:
                return out

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
        path: Optional[str] = None,
        title: str = constants.DEFAULT_TITLE,
        description: str = constants.DEFAULT_DESCRIPTION,
        image=constants.DEFAULT_IMAGE,
    ):
        """Add a page to the app.

        If the component is a callable, by default the route is the name of the
        function. Otherwise, a route must be provided.

        Args:
            component: The component to display at the page.
            path: The path to display the component at.
            title: The title of the page.
            description: The description of the page.
            image: The image to display on the page.
        """
        # If the path is not set, get it from the callable.
        if path is None:
            assert isinstance(
                component, Callable
            ), "Path must be set if component is not a callable."
            path = component.__name__

        # Get args from the path for dynamic routes.
        args = utils.get_path_args(path)

        # Generate the component if it is a callable.
        component = component if isinstance(component, Component) else component(*args)

        # Add meta information to the component.
        compiler_utils.add_meta(
            component, title=title, image=image, description=description
        )

        # Format the route.
        route = utils.format_route(path)

        # Add the page.
        self.pages[route] = component

    def compile(self, force_compile: bool = False):
        """Compile the app and output it to the pages folder.

        If the config environment is set to production, the app will
        not be compiled.

        Args:
            force_compile: Whether to force the app to compile.
        """
        # Get the env mode.
        config = utils.get_config()
        if config.env != constants.Env.DEV and not force_compile:
            print("Skipping compilation in non-dev mode.")
            return

        # Create the database models.
        Model.create_all()

        # Create the root document with base styles and fonts.
        self.pages[constants.DOCUMENT_ROOT] = compiler_utils.create_document_root(
            self.stylesheets
        )
        self.pages[constants.THEME] = compiler_utils.create_theme(self.style)  # type: ignore

        # Compile the pages.
        for path, component in self.pages.items():
            self.compile_page(path, component)

    def compile_page(
        self, path: str, component: Component, write: bool = True
    ) -> Tuple[str, str]:
        """Compile a single page.

        Args:
            path: The path to compile the page to.
            component: The component to compile.
            write: Whether to write the page to the pages folder.

        Returns:
            The path and code of the compiled page.
        """
        # Get the path for the output file.
        output_path = utils.get_page_path(path)

        # Compile the document root.
        if path == constants.DOCUMENT_ROOT:
            code = compiler.compile_document_root(component)

        # Compile the theme.
        elif path == constants.THEME:
            output_path = utils.get_theme_path()
            code = compiler.compile_theme(component)  # type: ignore

        # Compile all other pages.
        else:
            # Add the style to the component.
            component.add_style(self.style)
            code = compiler.compile_component(
                component=component,
                state=self.state,
            )

        # Write the page to the pages folder.
        if write:
            utils.write_page(output_path, code)

        return output_path, code

    def get_state(self, token: str) -> State:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        return self.state_manager.get_state(token)

    def set_state(self, token: str, state: State):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
        """
        self.state_manager.set_state(token, state)


async def _ping() -> str:
    """Test API endpoint.

    Returns:
        The response.
    """
    return "pong"


def _event(app: App):
    """Websocket endpoint for events.

    Args:
        app: The app to add the endpoint to.

    Returns:
        The websocket endpoint.
    """

    async def ws(websocket: WebSocket):
        """Create websocket endpoint.

        Args:
            websocket: The websocket sending events.
        """
        # Accept the connection.
        await websocket.accept()

        # Process events until the connection is closed.
        while True:
            # Get the event.
            event = Event.parse_raw(await websocket.receive_text())

            # Process the event.
            update = await process(app, event)

            # Send the update.
            await websocket.send_text(update.json())

    return ws


async def process(app: App, event: Event) -> StateUpdate:
    """Process an event.

    Args:
        app: The app to process the event for.
        event: The event to process.

    Returns:
        The state update after processing the event.
    """
    # Get the state for the session.
    state = app.get_state(event.token)

    # Preprocess the event.
    pre = app.preprocess(state, event)
    if pre is not None:
        return StateUpdate(delta=pre)

    # Apply the event to the state.
    update = await state.process(event)
    app.set_state(event.token, state)

    # Postprocess the event.
    post = app.postprocess(state, event, update.delta)
    if post is not None:
        return StateUpdate(delta=post)

    # Return the update.
    return update
