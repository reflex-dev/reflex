# pyright: reportDeprecated=true
"""A realistic user module type-checked with pyright and ty on 0.10.1a1 vs 0.10.0.

Covers #7406 (db helpers typed as defined), #7413 (optional object fields read
as ObjectVar[X] on the class), #7419 (upload handler called with the upload
spec), #7403 (LiteralObjectVar.create(dataclass)), #7401 (EventCallback stored
outside a state), and the rx.form(...) / rx.form.root(...) namespace.
"""

import dataclasses
from collections.abc import Callable
from typing import Any, TypedDict, assert_type, reveal_type

import sqlmodel
from reflex_base.event import EventCallback, EventSpec, EventType
from sqlalchemy import Engine, MetaData
from sqlalchemy.orm import Session
from sqlmodel.ext.asyncio.session import AsyncSession

import reflex as rx
from reflex.model import ModelRegistry, get_engine, sqla_session
from reflex.vars.object import LiteralObjectVar, ObjectVar


class User(rx.Model, table=True):
    name: str
    email: str


@dataclasses.dataclass
class Point:
    x: int
    y: int


class Filters(TypedDict):
    q: str
    page: int


class AppState(rx.State):
    user: rx.Field[User | None] = rx.field(None)
    point: rx.Field[Point | None] = rx.field(None)
    filters: rx.Field[Filters | None] = rx.field(None)
    required_point: rx.Field[Point] = rx.field(default_factory=lambda: Point(0, 0))
    plain_user: User | None = None
    name: str = ""
    uploaded: list[str] = []
    count: int = 0

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        for f in files:
            self.uploaded.append(f.name or "")

    @rx.event(background=True)
    async def handle_chunks(self, chunks: rx.UploadChunkIterator):
        async for _chunk in chunks:
            pass

    @rx.event
    def set_name_evt(self, name: str):
        self.name = name

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def submit_dict(self, form_data: dict[str, Any]):
        self.name = str(form_data.get("name", ""))

    @rx.event
    def load_user(self):
        with rx.session() as session:
            self.user = session.exec(sqlmodel.select(User)).first()

    @rx.event
    async def load_user_async(self):
        async with rx.asession() as session:
            result = await session.exec(sqlmodel.select(User))
            self.user = result.first()

    @rx.var
    def user_name(self) -> str:
        return self.user.name if self.user else ""


# #7406: database helpers typed as defined, not unioned with the stand-ins.
assert_type(rx.session(), sqlmodel.Session)
assert_type(rx.asession(), AsyncSession)
assert_type(ModelRegistry.get_metadata(), MetaData)
assert_type(get_engine(), Engine)
assert_type(sqla_session(), Session)
_metadata: MetaData = ModelRegistry.get_metadata()
ModelRegistry.register(sqlmodel.SQLModel)

# #7413: optional object fields read as ObjectVar[X] on the class.
assert_type(AppState.user, ObjectVar[User])
assert_type(AppState.point, ObjectVar[Point])
assert_type(AppState.filters, ObjectVar[Filters])
assert_type(AppState.required_point, ObjectVar[Point])
reveal_type(AppState.plain_user)
_user_name_var = AppState.user.name
_point_x = AppState.point.x
_filters_q = AppState.filters.q
_text = rx.text(AppState.user.email, AppState.point.y, AppState.filters.page)

# #7419: calling an upload handler with the upload spec.
assert_type(
    AppState.handle_upload(rx.upload_files(upload_id="u1")), EventCallback[()]
)
assert_type(
    AppState.handle_chunks(rx.upload_files_chunk(upload_id="u1")), EventCallback[()]
)
_upload_button = rx.button(
    "Upload", on_click=AppState.handle_upload(rx.upload_files(upload_id="u1"))
)
_chunk_button = rx.button(
    "Upload chunks",
    on_click=AppState.handle_chunks(rx.upload_files_chunk(upload_id="u1")),
)

# #7403: LiteralObjectVar.create takes anything that serializes to a mapping.
_point_var = LiteralObjectVar.create(Point(1, 2))
_mapping_var = LiteralObjectVar.create({"a": 1})


# #7401: an EventCallback stored outside a state stays an EventCallback.
@dataclasses.dataclass
class MenuEntry:
    label: str
    on_select: EventCallback[()] | None = None
    on_pick: EventCallback[str] | None = None


def render_entry(entry: MenuEntry) -> rx.Component:
    assert_type(entry.on_select, EventCallback[()] | None)
    assert_type(entry.on_pick, EventCallback[str] | None)
    return rx.button(entry.label, on_click=entry.on_select)


_entries = [
    MenuEntry("inc", on_select=AppState.increment),
    MenuEntry("name", on_pick=AppState.set_name_evt),
]
_menu = rx.vstack(*[render_entry(e) for e in _entries])


class Holder:
    on_name: EventCallback[str] | None = None


def reads(state: AppState, holder: Holder) -> None:
    assert_type(AppState.set_name_evt, EventCallback[str])
    assert_type(state.set_name_evt, Callable[[str], Any])
    assert_type(holder.on_name, EventCallback[str] | None)


def event_sequences(
    specs: list[EventSpec], handlers: tuple[EventCallback[()], ...]
) -> None:
    def prop(value: EventType[()]) -> None: ...

    prop(specs)
    prop(handlers)


# rx.form(...) and rx.form.root(...) still type as components.
_form = rx.form(rx.input(name="name"), on_submit=AppState.submit_dict)
_form_root = rx.form.root(rx.input(name="name"), on_submit=AppState.submit_dict)
_form_as_component: rx.Component = _form
_form_root_as_component: rx.Component = _form_root
reveal_type(_form)
reveal_type(_form_root)
_form_field = rx.form.field(
    rx.form.label("Name"),
    rx.form.control(rx.input(name="name"), as_child=True),
    rx.form.message("required", match="valueMissing"),
    name="name",
)


# Components with event handler props.
class MyComponent(rx.Component):
    library = "my-lib"
    tag = "MyThing"

    value: rx.Var[str]
    on_thing: rx.EventHandler[rx.event.no_args_event_spec]
    on_picked: rx.EventHandler[rx.event.passthrough_event_spec(str)]


_my = MyComponent.create(
    value="x", on_thing=AppState.increment, on_picked=AppState.set_name_evt
)


def page() -> rx.Component:
    return rx.vstack(
        _text,
        _upload_button,
        _chunk_button,
        _menu,
        _form,
        _form_root,
        _my,
        rx.moment(rx.Var("new Date()"), format="YYYY"),
        rx.data_editor(columns=["A", "B"], data=[["a", "b"]]),
        rx.icon("apple", size=AppState.count),
        rx.checkbox_group.root(
            rx.checkbox_group.item("A", value="a"), default_value=["a"]
        ),
        rx.radio_cards.root(rx.radio_cards.item(rx.text("1"), value="1")),
        rx.input(auto_complete=True),
        rx.progress(value=AppState.count, max=100),
    )
