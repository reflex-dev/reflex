""" Generated with stubgen from mypy, then manually edited, do not regen."""

import asyncio
from fastapi import FastAPI
from fastapi import UploadFile as UploadFile
from reflex import constants as constants
from reflex.admin import AdminDash as AdminDash
from reflex.base import Base as Base
from reflex.compiler import compiler as compiler
from reflex.components import connection_modal as connection_modal
from reflex.components.component import (
    Component as Component,
    ComponentStyle as ComponentStyle,
)
from reflex.components.base.fragment import Fragment as Fragment
from reflex.config import get_config as get_config
from reflex.event import (
    Event as Event,
    EventHandler as EventHandler,
    EventSpec as EventSpec,
)
from reflex.middleware import (
    HydrateMiddleware as HydrateMiddleware,
    Middleware as Middleware,
)
from reflex.model import Model as Model
from reflex.page import DECORATED_PAGES as DECORATED_PAGES
from reflex.route import (
    catchall_in_route as catchall_in_route,
    catchall_prefix as catchall_prefix,
    get_route_args as get_route_args,
    verify_route_validity as verify_route_validity,
)
from reflex.state import (
    State as State,
    BaseState as BaseState,
    StateManager as StateManager,
    StateUpdate as StateUpdate,
)
from reflex.utils import (
    console as console,
    format as format,
    prerequisites as prerequisites,
    types as types,
)
from socketio import ASGIApp, AsyncNamespace, AsyncServer
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
    Type,
    Union,
    overload,
)

ComponentCallable = Callable[[], Component]
Reducer = Callable[[Event], Coroutine[Any, Any, StateUpdate]]

def default_overlay_component() -> Component: ...

class OverlayFragment(Fragment):
    @overload
    @classmethod
    def create(cls, *children, **props) -> "OverlayFragment": ...  # type: ignore

class App(Base):
    pages: Dict[str, Component]
    stylesheets: List[str]
    api: FastAPI
    sio: Optional[AsyncServer]
    socket_app: Optional[ASGIApp]
    state: Type[BaseState]
    state_manager: StateManager
    style: ComponentStyle
    middleware: List[Middleware]
    load_events: Dict[str, List[Union[EventHandler, EventSpec]]]
    admin_dash: Optional[AdminDash]
    event_namespace: Optional[AsyncNamespace]
    overlay_component: Optional[Union[Component, ComponentCallable]]
    background_tasks: Set[asyncio.Task] = set()
    def __init__(
        self,
        *args,
        stylesheets: Optional[List[str]] = None,
        style: Optional[ComponentStyle] = None,
        admin_dash: Optional[AdminDash] = None,
        overlay_component: Optional[Union[Component, ComponentCallable]] = None,
        **kwargs
    ) -> None: ...
    def __call__(self) -> FastAPI: ...
    def add_default_endpoints(self) -> None: ...
    def add_cors(self) -> None: ...
    async def preprocess(self, state: State, event: Event) -> StateUpdate | None: ...
    async def postprocess(
        self, state: State, event: Event, update: StateUpdate
    ) -> StateUpdate: ...
    def add_middleware(self, middleware: Middleware, index: int | None = ...): ...
    def add_page(
        self,
        component: Component | ComponentCallable,
        route: str | None = ...,
        title: str = ...,
        description: str = ...,
        image=...,
        on_load: EventHandler | EventSpec | list[EventHandler | EventSpec] | None = ...,
        meta: list[dict[str, str]] = ...,
        script_tags: list[Component] | None = ...,
    ): ...
    def get_load_events(self, route: str) -> list[EventHandler | EventSpec]: ...
    def add_custom_404_page(
        self,
        component: Component | ComponentCallable | None = ...,
        title: str = ...,
        image: str = ...,
        description: str = ...,
        on_load: EventHandler | EventSpec | list[EventHandler | EventSpec] | None = ...,
        meta: list[dict[str, str]] = ...,
    ): ...
    def setup_admin_dash(self) -> None: ...
    def get_frontend_packages(self, imports: Dict[str, str]): ...
    def compile(self) -> None: ...
    def compile_(self) -> None: ...
    def modify_state(self, token: str) -> AsyncContextManager[State]: ...
    def _setup_overlay_component(self) -> None: ...
    def _process_background(
        self, state: State, event: Event
    ) -> asyncio.Task | None: ...

def process(
    app: App, event: Event, sid: str, headers: Dict, client_ip: str
) -> AsyncIterator[StateUpdate]: ...
async def ping() -> str: ...
def upload(app: App): ...

class EventNamespace(AsyncNamespace):
    app: App
    def __init__(self, namespace: str, app: App) -> None: ...
    def on_connect(self, sid, environ) -> None: ...
    def on_disconnect(self, sid) -> None: ...
    async def on_event(self, sid, data) -> None: ...
    async def on_ping(self, sid) -> None: ...
