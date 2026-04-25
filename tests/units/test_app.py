from __future__ import annotations

import asyncio
import contextlib
import contextvars
import functools
import io
import json
import unittest.mock
import uuid
from collections.abc import Generator
from contextlib import nullcontext as does_not_raise
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock

import pytest
from pytest_mock import MockerFixture
from reflex_base.components.component import Component
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.registry import RegistrationContext
from reflex_base.style import Style
from reflex_base.utils import console, exceptions, format
from reflex_base.vars.base import computed_var
from reflex_components_core.base.bare import Bare
from reflex_components_core.base.fragment import Fragment
from reflex_components_radix.themes.typography.text import Text
from starlette.applications import Starlette
from starlette.datastructures import FormData, Headers, UploadFile
from starlette.requests import ClientDisconnect
from starlette.responses import StreamingResponse
from starlette_admin.auth import AuthProvider

import reflex as rx
from reflex import AdminDash, constants
from reflex.app import App, ComponentCallable, upload
from reflex.environment import environment
from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis
from reflex.istate.manager.token import BaseStateToken
from reflex.model import Model
from reflex.state import (
    BaseState,
    OnLoadInternalState,
    RouterData,
    State,
    reload_state_module,
)

from .conftest import chdir
from .states import GenState
from .states.upload import (
    ChildFileUploadState,
    ChunkUploadState,
    FileUploadState,
    GrandChildFileUploadState,
)

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine


class EmptyState(BaseState):
    """An empty state."""


@pytest.fixture
def index_page() -> ComponentCallable:
    """An index page.

    Returns:
        The index page.
    """

    def index():
        return rx.box("Index")

    return index


@pytest.fixture
def about_page() -> ComponentCallable:
    """An about page.

    Returns:
        The about page.
    """

    def about():
        return rx.box("About")

    return about


class ATestState(BaseState):
    """A simple state for testing."""

    var: int


@pytest.fixture
def test_state() -> type[BaseState]:
    """A default state.

    Returns:
        A default state.
    """
    return ATestState


@pytest.fixture
def redundant_test_state() -> type[BaseState]:
    """A default state.

    Returns:
        A default state.
    """

    class RedundantTestState(BaseState):
        var: int

    return RedundantTestState


@pytest.fixture(scope="session")
def test_model() -> type[Model]:
    """A default model.

    Returns:
        A default model.
    """

    class TestModel(Model, table=True):
        pass

    return TestModel


@pytest.fixture(scope="session")
def test_model_auth() -> type[Model]:
    """A default model.

    Returns:
        A default model.
    """

    class TestModelAuth(Model, table=True):
        """A test model with auth."""

    return TestModelAuth


@pytest.fixture
def test_get_engine():
    """A default database engine.

    Returns:
        A default database engine.
    """
    import sqlmodel

    enable_admin = True
    url = "sqlite:///test.db"
    return sqlmodel.create_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False} if enable_admin else {},
    )


if TYPE_CHECKING:
    from starlette_admin.auth import AuthProvider


@pytest.fixture
def test_custom_auth_admin() -> type[AuthProvider]:
    """A default auth provider.

    Returns:
        A default default auth provider.
    """
    from starlette_admin.auth import AuthProvider

    class TestAuthProvider(AuthProvider):
        """A test auth provider."""

        login_path: str = "/login"
        logout_path: str = "/logout"

        def login(self):  # pyright: ignore [reportIncompatibleMethodOverride]
            """Login."""

        def is_authenticated(self):  # pyright: ignore [reportIncompatibleMethodOverride]
            """Is authenticated."""

        def get_admin_user(self):  # pyright: ignore [reportIncompatibleMethodOverride]
            """Get admin user."""

        def logout(self):  # pyright: ignore [reportIncompatibleMethodOverride]
            """Logout."""

    return TestAuthProvider


def test_default_app(app: App):
    """Test creating an app with no args.

    Args:
        app: The app to test.
    """
    assert app._middlewares == []
    assert app.style == Style()
    assert app.admin_dash is None


def test_multiple_states_error(
    monkeypatch: pytest.MonkeyPatch,
    test_state: BaseState,
    redundant_test_state: BaseState,
):
    """Test that an error is thrown when multiple classes subclass rx.BaseState.

    Args:
        monkeypatch: Pytest monkeypatch object.
        test_state: A test state subclassing rx.BaseState.
        redundant_test_state: Another test state subclassing rx.BaseState.
    """
    monkeypatch.delenv(constants.PYTEST_CURRENT_TEST)
    with pytest.raises(ValueError):
        App()


def test_add_page_default_route(
    app: App, index_page: ComponentCallable, about_page: ComponentCallable
):
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
        about_page: The about page.
    """
    assert app._pages == {}
    assert app._unevaluated_pages == {}
    app.add_page(index_page)
    app._compile_page("index")
    assert app._pages.keys() == {"index"}
    app.add_page(about_page)
    app._compile_page("about")
    assert app._pages.keys() == {"index", "about"}


def test_add_page_set_route(app: App, index_page: ComponentCallable):
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
    """
    route = "/test"
    assert app._unevaluated_pages == {}
    app.add_page(index_page, route=route)
    app._compile_page("test")
    assert app._pages.keys() == {"test"}


def test_add_page_set_route_dynamic(index_page: ComponentCallable):
    """Test adding a page with dynamic route variable to an app.

    Args:
        index_page: The index page.
    """
    app = App(_state=EmptyState)
    assert app._state is not None
    route = "/test/[dynamic]"
    assert app._unevaluated_pages == {}
    app.add_page(index_page, route=route)
    app._compile_page("test/[dynamic]")
    assert app._pages.keys() == {"test/[dynamic]"}
    assert "dynamic" in app._state.computed_vars
    assert app._state.computed_vars["dynamic"]._deps(objclass=EmptyState) == {
        EmptyState.get_full_name(): {constants.ROUTER},
    }
    assert constants.ROUTER in app._state()._var_dependencies


def test_add_page_set_route_nested(app: App, index_page: ComponentCallable):
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
    """
    route = "test/nested"
    assert app._unevaluated_pages == {}
    app.add_page(index_page, route=route)
    assert app._unevaluated_pages.keys() == {route}


def test_add_page_invalid_api_route(app: App, index_page: ComponentCallable):
    """Test adding a page with an invalid route to an app.

    Args:
        app: The app to test.
        index_page: The index page.
    """
    app.add_page(index_page, route="api")
    app.add_page(index_page, route="/api")
    app.add_page(index_page, route="/api/")
    app.add_page(index_page, route="api/foo")
    app.add_page(index_page, route="/api/foo")
    # These should be fine
    app.add_page(index_page, route="api2")
    app.add_page(index_page, route="/foo/api")


def page1():
    return rx.fragment()


def page2():
    return rx.fragment()


def index():
    return rx.fragment()


@pytest.mark.parametrize(
    ("first_page", "second_page", "route"),
    [
        (index, index, None),
        (page1, page1, None),
    ],
)
def test_add_the_same_page(
    mocker: MockerFixture, app: App, first_page, second_page, route
):
    app.add_page(first_page, route=route)
    mock_object = mocker.Mock()
    mocker.patch.object(
        console,
        "warn",
        mock_object,
    )
    app.add_page(second_page, route="/" + route.strip("/") if route else None)
    assert mock_object.call_count == 1


@pytest.mark.parametrize(
    ("first_page", "second_page", "route"),
    [
        (lambda: rx.fragment(), lambda: rx.fragment(rx.text("second")), "/"),
        (rx.fragment(rx.text("first")), rx.fragment(rx.text("second")), "/page1"),
        (
            lambda: rx.fragment(rx.text("first")),
            rx.fragment(rx.text("second")),
            "page3",
        ),
        (page1, page2, "page1"),
    ],
)
def test_add_duplicate_page_route_error(app: App, first_page, second_page, route):
    app.add_page(first_page, route=route)
    with pytest.raises(ValueError):
        app.add_page(second_page, route="/" + route.strip("/") if route else None)


@pytest.mark.skipif(
    not find_spec("starlette_admin")
    or not find_spec("sqlmodel")
    or not find_spec("pydantic"),
    reason="starlette_admin not installed or sqlmodel not installed or pydantic not installed",
)
def test_initialize_with_admin_dashboard(
    test_model: type[Model], mocker: MockerFixture
):
    """Test setting the admin dashboard of an app.

    Args:
        test_model: The default model.
        mocker: pytest mocker object.
    """
    conf = rx.Config(app_name="testing", db_url="sqlite:///reflex.db")
    mocker.patch("reflex_base.config._get_config", return_value=conf)
    app = App(admin_dash=AdminDash(models=[test_model]))
    assert app.admin_dash is not None
    assert len(app.admin_dash.models) > 0
    assert app.admin_dash.models[0] == test_model


@pytest.mark.skipif(
    not find_spec("starlette_admin")
    or not find_spec("sqlmodel")
    or not find_spec("pydantic"),
    reason="starlette_admin not installed or sqlmodel not installed or pydantic not installed",
)
def test_initialize_with_custom_admin_dashboard(
    test_get_engine: Engine,
    test_custom_auth_admin: type[AuthProvider],
    test_model_auth: Model,
):
    """Test setting the custom admin dashboard of an app.

    Args:
        test_get_engine: The default database engine.
        test_model_auth: The default model for an auth admin dashboard.
        test_custom_auth_admin: The custom auth provider.
    """
    from starlette_admin.contrib.sqla.admin import Admin

    custom_auth_provider = test_custom_auth_admin()
    custom_admin = Admin(engine=test_get_engine, auth_provider=custom_auth_provider)
    app = App(admin_dash=AdminDash(models=[test_model_auth], admin=custom_admin))
    assert app.admin_dash is not None
    assert app.admin_dash.admin is not None
    assert len(app.admin_dash.models) > 0
    assert app.admin_dash.models[0] == test_model_auth
    assert app.admin_dash.admin.auth_provider == custom_auth_provider


@pytest.mark.skipif(
    not find_spec("starlette_admin")
    or not find_spec("sqlmodel")
    or not find_spec("pydantic"),
    reason="starlette_admin not installed or sqlmodel not installed or pydantic not installed",
)
def test_initialize_admin_dashboard_with_view_overrides(
    test_model: type[Model], mocker: MockerFixture
):
    """Test setting the admin dashboard of an app with view class overridden.

    Args:
        test_model: The default model.
        mocker: pytest mocker object.
    """
    from starlette_admin.contrib.sqla.view import ModelView

    class TestModelView(ModelView):
        pass

    conf = rx.Config(app_name="testing", db_url="sqlite:///reflex.db")
    mocker.patch("reflex_base.config._get_config", return_value=conf)

    app = App(
        admin_dash=AdminDash(
            models=[test_model], view_overrides={test_model: TestModelView}
        )
    )
    assert app.admin_dash is not None
    assert app.admin_dash.models == [test_model]
    assert app.admin_dash.view_overrides[test_model] == TestModelView


@pytest.mark.asyncio
async def test_initialize_with_state(test_state: type[ATestState], token: str):
    """Test setting the state of an app.

    Args:
        test_state: The default state.
        token: a Token.
    """
    app = App(_state=test_state)
    assert app._state == test_state

    # Get a state for a given token.
    state = await app.state_manager.get_state(
        BaseStateToken(ident=token, cls=test_state)
    )
    assert isinstance(state, test_state)
    assert state.var == 0

    await app.state_manager.close()


@pytest.mark.asyncio
async def test_set_and_get_state(test_state: type[ATestState]):
    """Test setting and getting the state of an app with different tokens.

    Args:
        test_state: The default state.
    """
    app = App(_state=test_state)

    # Create two tokens.
    token1 = BaseStateToken(ident=str(uuid.uuid4()), cls=test_state)
    token2 = BaseStateToken(ident=str(uuid.uuid4()), cls=test_state)

    # Get the default state for each token.
    state1 = await app.state_manager.get_state(token1)
    state2 = await app.state_manager.get_state(token2)
    assert isinstance(state1, test_state)
    assert isinstance(state2, test_state)
    assert state1.var == 0
    assert state2.var == 0

    # Set the vars to different values.
    state1.var = 1
    state2.var = 2
    await app.state_manager.set_state(token1, state1)
    await app.state_manager.set_state(token2, state2)

    # Get the states again and check the values.
    state1 = await app.state_manager.get_state(token1)
    state2 = await app.state_manager.get_state(token2)
    assert isinstance(state1, test_state)
    assert isinstance(state2, test_state)
    assert state1.var == 1
    assert state2.var == 2

    await app.state_manager.close()


@pytest.mark.asyncio
async def test_dynamic_var_event(
    test_state: type[ATestState],
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, dict[str, dict[str, Any]]]],
    token: str,
    clean_registration_context: RegistrationContext,
):
    """Test that the default handler of a dynamic generated var
    works as expected.

    Args:
        test_state: State Fixture.
        mock_base_state_event_processor: BaseStateEventProcessor Fixture.
        emitted_deltas: List to store emitted deltas.
        token: a Token.
        clean_registration_context: The registration context fixture, which is cleared before each test.
    """
    clean_registration_context.register_base_state(test_state)
    state = test_state()  # pyright: ignore [reportCallIssue]
    state.add_var("int_val", int, 0)

    def set_int_val(self, value: int):
        self.int_val = value

    state._add_event_handler("set_int_val", set_int_val)
    async with mock_base_state_event_processor as processor:
        await processor.enqueue(
            token,
            Event(
                name=f"{test_state.get_name()}.set_int_val",
                payload={"value": 50},
            ),
        )
    assert emitted_deltas == [
        (token, {test_state.get_name(): {"int_val" + FIELD_MARKER: 50}})
    ]


@pytest.fixture
def list_mutation_state():
    """Create a state with list mutation features.

    Returns:
        A state with list mutation features.
    """

    class ListMutationTestState(BaseState):
        """A state for testing ReflexList mutation."""

        # plain list
        plain_friends = ["Tommy"]

        def make_friend(self):
            """Add a friend to the list."""
            self.plain_friends.append("another-fd")

        def change_first_friend(self):
            """Change the first friend in the list."""
            self.plain_friends[0] = "Jenny"

        def unfriend_all_friends(self):
            """Unfriend all friends in the list."""
            self.plain_friends.clear()

        def unfriend_first_friend(self):
            """Unfriend the first friend in the list."""
            del self.plain_friends[0]

        def remove_last_friend(self):
            """Remove the last friend in the list."""
            self.plain_friends.pop()

        def make_friends_with_colleagues(self):
            """Add list of friends to the list."""
            colleagues = ["Peter", "Jimmy"]
            self.plain_friends.extend(colleagues)

        def remove_tommy(self):
            """Remove Tommy from the list."""
            self.plain_friends.remove("Tommy")

        # list in dict
        friends_in_dict = {"Tommy": ["Jenny"]}

        def remove_jenny_from_tommy(self):
            """Remove Jenny from Tommy's friends list."""
            self.friends_in_dict["Tommy"].remove("Jenny")

        def add_jimmy_to_tommy_friends(self):
            """Add Jimmy to Tommy's friends list."""
            self.friends_in_dict["Tommy"].append("Jimmy")

        def tommy_has_no_fds(self):
            """Clear Tommy's friends list."""
            self.friends_in_dict["Tommy"].clear()

        # nested list
        friends_in_nested_list = [["Tommy"], ["Jenny"]]

        def remove_first_group(self):
            """Remove the first group of friends from the nested list."""
            self.friends_in_nested_list.pop(0)

        def remove_first_person_from_first_group(self):
            """Remove the first person from the first group of friends in the nested list."""
            self.friends_in_nested_list[0].pop(0)

        def add_jimmy_to_second_group(self):
            """Add Jimmy to the second group of friends in the nested list."""
            self.friends_in_nested_list[1].append("Jimmy")

    return ListMutationTestState()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_tuples",
    [
        pytest.param(
            [
                (
                    "make_friend",
                    {"plain_friends" + FIELD_MARKER: ["Tommy", "another-fd"]},
                ),
                (
                    "change_first_friend",
                    {"plain_friends" + FIELD_MARKER: ["Jenny", "another-fd"]},
                ),
            ],
            id="append then __setitem__",
        ),
        pytest.param(
            [
                (
                    "unfriend_first_friend",
                    {"plain_friends" + FIELD_MARKER: []},
                ),
                (
                    "make_friend",
                    {"plain_friends" + FIELD_MARKER: ["another-fd"]},
                ),
            ],
            id="delitem then append",
        ),
        pytest.param(
            [
                (
                    "make_friends_with_colleagues",
                    {"plain_friends" + FIELD_MARKER: ["Tommy", "Peter", "Jimmy"]},
                ),
                (
                    "remove_tommy",
                    {"plain_friends" + FIELD_MARKER: ["Peter", "Jimmy"]},
                ),
                (
                    "remove_last_friend",
                    {"plain_friends" + FIELD_MARKER: ["Peter"]},
                ),
                (
                    "unfriend_all_friends",
                    {"plain_friends" + FIELD_MARKER: []},
                ),
            ],
            id="extend, remove, pop, clear",
        ),
        pytest.param(
            [
                (
                    "add_jimmy_to_second_group",
                    {
                        "friends_in_nested_list" + FIELD_MARKER: [
                            ["Tommy"],
                            ["Jenny", "Jimmy"],
                        ]
                    },
                ),
                (
                    "remove_first_person_from_first_group",
                    {"friends_in_nested_list" + FIELD_MARKER: [[], ["Jenny", "Jimmy"]]},
                ),
                (
                    "remove_first_group",
                    {"friends_in_nested_list" + FIELD_MARKER: [["Jenny", "Jimmy"]]},
                ),
            ],
            id="nested list",
        ),
        pytest.param(
            [
                (
                    "add_jimmy_to_tommy_friends",
                    {"friends_in_dict" + FIELD_MARKER: {"Tommy": ["Jenny", "Jimmy"]}},
                ),
                (
                    "remove_jenny_from_tommy",
                    {"friends_in_dict" + FIELD_MARKER: {"Tommy": ["Jimmy"]}},
                ),
                (
                    "tommy_has_no_fds",
                    {"friends_in_dict" + FIELD_MARKER: {"Tommy": []}},
                ),
            ],
            id="list in dict",
        ),
    ],
)
async def test_list_mutation_detection__plain_list(
    event_tuples: list[tuple[str, list[str]]],
    list_mutation_state: State,
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, dict[str, dict[str, Any]]]],
):
    """Test list mutation detection
    when reassignment is not explicitly included in the logic.

    Args:
        event_tuples: From parametrization.
        list_mutation_state: A state with list mutation features.
        token: a Token.
        mock_base_state_event_processor: BaseStateEventProcessor Fixture.
        emitted_deltas: List to store emitted deltas.
    """
    for event_name, expected_delta in event_tuples:
        async with mock_base_state_event_processor as processor:
            await processor.enqueue(
                token,
                Event(
                    name=f"{list_mutation_state.get_name()}.{event_name}",
                    payload={},
                ),
            )
        # prefix keys in expected_delta with the state name
        expected_delta = {list_mutation_state.get_name(): expected_delta}
        assert emitted_deltas == [(token, expected_delta)]
        emitted_deltas.clear()  # Clear emitted deltas for the next iteration


@pytest.fixture
def dict_mutation_state():
    """Create a state with dict mutation features.

    Returns:
        A state with dict mutation features.
    """

    class DictMutationTestState(BaseState):
        """A state for testing ReflexDict mutation."""

        # plain dict
        details = {"name": "Tommy"}

        def add_age(self):
            """Add an age to the dict."""
            self.details.update({"age": 20})  # pyright: ignore [reportCallIssue, reportArgumentType]

        def change_name(self):
            """Change the name in the dict."""
            self.details["name"] = "Jenny"

        def remove_last_detail(self):
            """Remove the last item in the dict."""
            self.details.popitem()

        def clear_details(self):
            """Clear the dict."""
            self.details.clear()

        def remove_name(self):
            """Remove the name from the dict."""
            del self.details["name"]

        def pop_out_age(self):
            """Pop out the age from the dict."""
            self.details.pop("age")

        # dict in list
        address = [{"home": "home address"}, {"work": "work address"}]

        def remove_home_address(self):
            """Remove the home address from dict in the list."""
            self.address[0].pop("home")

        def add_street_to_home_address(self):
            """Set street key in the dict in the list."""
            self.address[0]["street"] = "street address"

        # nested dict
        friend_in_nested_dict = {"name": "Nikhil", "friend": {"name": "Alek"}}

        def change_friend_name(self):
            """Change the friend's name in the nested dict."""
            self.friend_in_nested_dict["friend"]["name"] = "Tommy"

        def remove_friend(self):
            """Remove the friend from the nested dict."""
            self.friend_in_nested_dict.pop("friend")

        def add_friend_age(self):
            """Add an age to the friend in the nested dict."""
            self.friend_in_nested_dict["friend"]["age"] = 30

    return DictMutationTestState()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_tuples",
    [
        pytest.param(
            [
                (
                    "add_age",
                    {"details" + FIELD_MARKER: {"name": "Tommy", "age": 20}},
                ),
                (
                    "change_name",
                    {"details" + FIELD_MARKER: {"name": "Jenny", "age": 20}},
                ),
                (
                    "remove_last_detail",
                    {"details" + FIELD_MARKER: {"name": "Jenny"}},
                ),
            ],
            id="update then __setitem__",
        ),
        pytest.param(
            [
                (
                    "clear_details",
                    {"details" + FIELD_MARKER: {}},
                ),
                (
                    "add_age",
                    {"details" + FIELD_MARKER: {"age": 20}},
                ),
            ],
            id="delitem then update",
        ),
        pytest.param(
            [
                (
                    "add_age",
                    {"details" + FIELD_MARKER: {"name": "Tommy", "age": 20}},
                ),
                (
                    "remove_name",
                    {"details" + FIELD_MARKER: {"age": 20}},
                ),
                (
                    "pop_out_age",
                    {"details" + FIELD_MARKER: {}},
                ),
            ],
            id="add, remove, pop",
        ),
        pytest.param(
            [
                (
                    "remove_home_address",
                    {"address" + FIELD_MARKER: [{}, {"work": "work address"}]},
                ),
                (
                    "add_street_to_home_address",
                    {
                        "address" + FIELD_MARKER: [
                            {"street": "street address"},
                            {"work": "work address"},
                        ]
                    },
                ),
            ],
            id="dict in list",
        ),
        pytest.param(
            [
                (
                    "change_friend_name",
                    {
                        "friend_in_nested_dict" + FIELD_MARKER: {
                            "name": "Nikhil",
                            "friend": {"name": "Tommy"},
                        }
                    },
                ),
                (
                    "add_friend_age",
                    {
                        "friend_in_nested_dict" + FIELD_MARKER: {
                            "name": "Nikhil",
                            "friend": {"name": "Tommy", "age": 30},
                        }
                    },
                ),
                (
                    "remove_friend",
                    {"friend_in_nested_dict" + FIELD_MARKER: {"name": "Nikhil"}},
                ),
            ],
            id="nested dict",
        ),
    ],
)
async def test_dict_mutation_detection__plain_list(
    event_tuples: list[tuple[str, list[str]]],
    dict_mutation_state: State,
    token: str,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, dict[str, dict[str, Any]]]],
):
    """Test dict mutation detection
    when reassignment is not explicitly included in the logic.

    Args:
        event_tuples: From parametrization.
        dict_mutation_state: A state with dict mutation features.
        token: a Token.
        mock_base_state_event_processor: BaseStateEventProcessor Fixture.
        emitted_deltas: List to store emitted deltas.
    """
    for event_name, expected_delta in event_tuples:
        async with mock_base_state_event_processor as processor:
            await processor.enqueue(
                token,
                Event(
                    name=f"{dict_mutation_state.get_name()}.{event_name}",
                    payload={},
                ),
            )
        # prefix keys in expected_delta with the state name
        expected_delta = {dict_mutation_state.get_name(): expected_delta}
        assert emitted_deltas == [(token, expected_delta)]
        emitted_deltas.clear()  # Clear emitted deltas for the next iteration


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "delta"),
    [
        (
            FileUploadState,
            {
                FileUploadState.get_full_name(): {
                    "img_list" + FIELD_MARKER: ["image1.jpg", "image2.jpg"]
                }
            },
        ),
        (
            ChildFileUploadState,
            {
                ChildFileUploadState.get_full_name(): {
                    "img_list" + FIELD_MARKER: ["image1.jpg", "image2.jpg"]
                }
            },
        ),
        (
            GrandChildFileUploadState,
            {
                GrandChildFileUploadState.get_full_name(): {
                    "img_list" + FIELD_MARKER: ["image1.jpg", "image2.jpg"]
                }
            },
        ),
    ],
)
async def test_upload_file(
    tmp_path: Path,
    state,
    delta,
    token: str,
    mocker: MockerFixture,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
    mock_root_event_context: EventContext,
    clean_registration_context: RegistrationContext,
):
    """Test that file upload works correctly.

    Args:
        tmp_path: Temporary path.
        state: The state class.
        delta: Expected delta after processing all files.
        token: a Token.
        mocker: pytest mocker object.
        attached_mock_base_state_event_processor: BaseStateEventProcessor Fixture attached to the app instance to capture emitted events.
        mock_root_event_context: The mocked root event context, for accessing state_manager.
        clean_registration_context: Fixture to ensure clean registration context for each test, preventing cross-test contamination of state subclasses.
    """
    clean_registration_context.register_base_state(state)
    app = Mock(
        event_processor=attached_mock_base_state_event_processor,
    )
    async with mock_root_event_context.state_manager.modify_state(
        BaseStateToken(ident=token, cls=state)
    ) as root_state:
        (await root_state.get_state(state))._tmp_path = tmp_path
    data = b"This is binary data"

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{state.get_full_name()}.multi_handle_upload",
    }

    file1 = UploadFile(
        filename="image1.jpg",
        file=io.BytesIO(data),
    )
    file2 = UploadFile(
        filename="image2.jpg",
        file=io.BytesIO(data),
    )

    async def form():  # noqa: RUF029
        return FormData([("files", file1), ("files", file2)])

    request_mock.form = form

    upload_fn = upload(app)
    streaming_response = await upload_fn(request_mock)
    assert isinstance(streaming_response, StreamingResponse)
    # Handler yields after each file, producing intermediate + final updates.
    updates = []
    async for state_update in streaming_response.body_iterator:
        updates.append(json.loads(str(state_update)))
    # 2 intermediate yields
    assert len(updates) == 2

    # The last intermediate update should contain the full cumulative delta.
    assert updates[1]["delta"] == delta


@pytest.mark.asyncio
async def test_upload_file_keeps_form_open_until_stream_completes(
    tmp_path: Path,
    token: str,
    mocker: MockerFixture,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
    mock_root_event_context: EventContext,
):
    """Test that upload files are not eagerly copied into memory.

    Uses two distinct BinaryIO instances, sets _tmp_path via modify_state,
    and verifies that both file handles remain open during streaming and are
    closed (along with correct file content) after the stream completes.

    Args:
        tmp_path: Temporary path.
        token: A token.
        mocker: pytest mocker object.
        attached_mock_base_state_event_processor: BaseStateEventProcessor Fixture attached to the app instance to capture emitted events.
        mock_root_event_context: The mocked root event context, for accessing state_manager.
    """
    app = Mock(event_processor=attached_mock_base_state_event_processor)

    # Set _tmp_path via modify_state instead of setting class attribute directly.
    async with mock_root_event_context.state_manager.modify_state(
        BaseStateToken(ident=token, cls=FileUploadState)
    ) as root_state:
        (await root_state.get_state(FileUploadState))._tmp_path = tmp_path

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{FileUploadState.get_full_name()}.multi_handle_upload",
    }

    data1 = b"contents of image one"
    data2 = b"contents of image two"
    bio1 = io.BytesIO(data1)
    bio2 = io.BytesIO(data2)
    file1 = UploadFile(filename="image1.jpg", file=bio1)
    file2 = UploadFile(filename="image2.jpg", file=bio2)

    form_data = FormData([("files", file1), ("files", file2)])
    original_close = form_data.close
    form_close = AsyncMock(side_effect=original_close)
    form_data.close = form_close

    async def form():  # noqa: RUF029
        return form_data

    request_mock.form = form

    upload_fn = upload(app)
    streaming_response = await upload_fn(request_mock)

    assert isinstance(streaming_response, StreamingResponse)
    # Before streaming starts, nothing should be read or closed.
    assert form_close.await_count == 0
    assert not bio1.closed
    assert not bio2.closed

    # Drive the response through the full ASGI lifecycle so the streaming
    # response invokes the on_finish callback.
    scope = {"type": "http"}
    done = asyncio.Event()

    async def receive():
        await done.wait()
        return {"type": "http.disconnect"}

    async def send(message):  # noqa: RUF029
        if message.get("type") == "http.response.body" and not message.get("body"):
            done.set()

    await streaming_response(scope, receive, send)

    # After the ASGI call completes, form_data.close() should have been called,
    # closing both underlying file handles.
    assert form_close.await_count == 1
    assert bio1.closed
    assert bio2.closed

    # Verify files were written to the tmp dir with the correct content.
    assert (tmp_path / "image1.jpg").read_bytes() == data1
    assert (tmp_path / "image2.jpg").read_bytes() == data2


@pytest.mark.asyncio
async def test_upload_empty_buffered_request_dispatches_alias_handler(
    token: str,
    mocker: MockerFixture,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
    mock_root_event_context: EventContext,
):
    """Test that empty uploads still dispatch buffered alias handlers."""
    app = Mock(event_processor=attached_mock_base_state_event_processor)

    async with mock_root_event_context.state_manager.modify_state(
        BaseStateToken(ident=token, cls=FileUploadState)
    ) as root_state:
        (await root_state.get_state(FileUploadState)).img_list = []

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{FileUploadState.get_full_name()}.upload_alias_handler",
    }

    async def form():  # noqa: RUF029
        return FormData()

    request_mock.form = form

    upload_fn = upload(app)
    streaming_response = await upload_fn(request_mock)
    assert isinstance(streaming_response, StreamingResponse)

    updates = []
    async for state_update in streaming_response.body_iterator:
        updates.append(json.loads(str(state_update)))

    assert len(updates) == 1
    assert updates[0]["delta"] == {
        FileUploadState.get_full_name(): {"img_list" + FIELD_MARKER: ["count:0"]}
    }
    if environment.REFLEX_OPLOCK_ENABLED.get():
        await mock_root_event_context.state_manager.close()

    state = await mock_root_event_context.state_manager.get_state(
        BaseStateToken(ident=token, cls=FileUploadState)
    )
    substate = await state.get_state(FileUploadState)
    assert isinstance(substate, FileUploadState)
    assert substate.img_list == ["count:0"]


@pytest.mark.asyncio
async def test_upload_file_closes_form_on_form_error(
    token: str,
    mocker: MockerFixture,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
):
    """Test that cancellation before form parsing leaves form data untouched."""
    app = Mock(event_processor=attached_mock_base_state_event_processor)

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{FileUploadState.get_full_name()}.multi_handle_upload",
    }

    file1 = UploadFile(filename="image1.jpg", file=io.BytesIO(b"data"))
    form_data = FormData([("files", file1)])
    original_close = form_data.close
    form_close = AsyncMock(side_effect=original_close)
    form_data.close = form_close

    async def cancelled_form():
        await asyncio.sleep(0)
        raise asyncio.CancelledError

    request_mock.form = cancelled_form

    upload_fn = upload(app)
    with pytest.raises(asyncio.CancelledError):
        await upload_fn(request_mock)

    assert form_close.await_count == 0
    assert not file1.file.closed


@pytest.mark.asyncio
async def test_upload_file_closes_form_on_event_creation_cancellation(
    token: str,
    mocker: MockerFixture,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
):
    """Test that cancellation during event creation closes form data."""
    app = Mock(event_processor=attached_mock_base_state_event_processor)

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{FileUploadState.get_full_name()}.multi_handle_upload",
    }

    bio = io.BytesIO(b"data")
    file1 = UploadFile(filename="image1.jpg", file=bio)
    form_data = FormData([("files", file1)])
    original_close = form_data.close
    form_close = AsyncMock(side_effect=original_close)
    form_data.close = form_close

    async def form():  # noqa: RUF029
        return form_data

    request_mock.form = form

    # Patch getlist on the form_data to raise CancelledError during event
    # creation (after form is parsed, before streaming begins).
    form_data.getlist = Mock(side_effect=asyncio.CancelledError)

    upload_fn = upload(app)
    with pytest.raises(asyncio.CancelledError):
        await upload_fn(request_mock)

    # Form was parsed, so it should be closed on failure.
    assert form_close.await_count == 1
    assert bio.closed


@pytest.mark.asyncio
async def test_upload_file_closes_form_if_response_cancelled_before_stream_starts(
    tmp_path: Path,
    token: str,
    mocker: MockerFixture,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
    mock_root_event_context: EventContext,
):
    """Test that response cancellation before iteration still closes form data."""
    app = Mock(event_processor=attached_mock_base_state_event_processor)

    async with mock_root_event_context.state_manager.modify_state(
        BaseStateToken(ident=token, cls=FileUploadState)
    ) as root_state:
        (await root_state.get_state(FileUploadState))._tmp_path = tmp_path

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{FileUploadState.get_full_name()}.multi_handle_upload",
    }

    bio = io.BytesIO(b"contents of image one")
    file1 = UploadFile(filename="image1.jpg", file=bio)
    form_data = FormData([("files", file1)])
    original_close = form_data.close
    form_close = AsyncMock(side_effect=original_close)
    form_data.close = form_close

    async def form():  # noqa: RUF029
        return form_data

    async def receive():
        await asyncio.sleep(0)
        return {"type": "http.disconnect"}

    async def send(_message):
        await asyncio.sleep(0)
        raise asyncio.CancelledError

    request_mock.form = form

    upload_fn = upload(app)
    streaming_response = await upload_fn(request_mock)

    assert isinstance(streaming_response, StreamingResponse)
    assert form_close.await_count == 0
    assert not bio.closed

    with pytest.raises(asyncio.CancelledError):
        await streaming_response(
            {"type": "http", "asgi": {"spec_version": "2.4"}},
            receive,
            send,
        )

    assert form_close.await_count == 1
    assert bio.closed


@pytest.mark.asyncio
async def test_upload_file_cancels_buffered_handler_on_disconnect(token: str):
    """Buffered uploads cancel the streaming handler on client disconnect.

    Args:
        token: A token.
    """
    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{FileUploadState.get_full_name()}.multi_handle_upload",
    }

    bio = io.BytesIO(b"contents of image one")
    file1 = UploadFile(filename="image1.jpg", file=bio)
    form_data = FormData([("files", file1)])
    original_close = form_data.close
    form_close = AsyncMock(side_effect=original_close)
    form_data.close = form_close

    async def form():  # noqa: RUF029
        return form_data

    request_mock.form = form

    stream_started = asyncio.Event()
    stream_closed = asyncio.Event()

    async def enqueue_stream_delta(_token, _event):
        try:
            stream_started.set()
            yield {"state": {"ok": True}}
            await asyncio.Event().wait()
        finally:
            stream_closed.set()

    app = Mock(
        event_processor=Mock(enqueue_stream_delta=enqueue_stream_delta),
    )

    upload_fn = upload(app)
    streaming_response = await upload_fn(request_mock)

    assert isinstance(streaming_response, StreamingResponse)

    async def receive():
        await stream_started.wait()
        return {"type": "http.disconnect"}

    async def send(_message):  # noqa: RUF029
        return None

    await asyncio.wait_for(
        streaming_response(
            {"type": "http", "asgi": {"spec_version": "2.4"}},
            receive,
            send,
        ),
        timeout=1,
    )

    await asyncio.wait_for(stream_closed.wait(), timeout=1)
    assert form_close.await_count == 1
    assert bio.closed


@pytest.mark.asyncio
async def test_upload_file_raises_client_disconnect_when_stream_send_fails(
    token: str,
):
    """Buffered uploads close the handler stream when send raises OSError.

    Args:
        token: A token.
    """
    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{FileUploadState.get_full_name()}.multi_handle_upload",
    }

    bio = io.BytesIO(b"contents of image one")
    file1 = UploadFile(filename="image1.jpg", file=bio)
    form_data = FormData([("files", file1)])
    original_close = form_data.close
    form_close = AsyncMock(side_effect=original_close)
    form_data.close = form_close

    async def form():  # noqa: RUF029
        return form_data

    request_mock.form = form

    stream_closed = asyncio.Event()

    async def enqueue_stream_delta(_token, _event):
        try:
            yield {"state": {"ok": True}}
            await asyncio.Event().wait()
        finally:
            stream_closed.set()

    app = Mock(
        event_processor=Mock(enqueue_stream_delta=enqueue_stream_delta),
    )

    upload_fn = upload(app)
    streaming_response = await upload_fn(request_mock)

    assert isinstance(streaming_response, StreamingResponse)

    async def receive() -> dict[str, Any]:
        await asyncio.Event().wait()
        msg = "receive should not return"
        raise AssertionError(msg)

    async def send(message):
        await asyncio.sleep(0)
        if message.get("type") == "http.response.body":
            err = "client disconnected"
            raise OSError(err)

    with pytest.raises(ClientDisconnect):
        await streaming_response(
            {"type": "http", "asgi": {"spec_version": "2.4"}},
            receive,
            send,
        )

    await asyncio.wait_for(stream_closed.wait(), timeout=1)
    assert form_close.await_count == 1
    assert bio.closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [FileUploadState, ChildFileUploadState, GrandChildFileUploadState],
)
async def test_upload_file_without_annotation(
    state: FileUploadState | ChildFileUploadState | GrandChildFileUploadState,
    tmp_path: Path,
    token: str,
):
    """Test that an error is thrown when there's no param annotated with rx.UploadFile or list[UploadFile].

    Args:
        state: The state class.
        tmp_path: Temporary path.
        token: a Token.
    """
    app = App(_state=State)

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{state.get_full_name()}.handle_upload2",
    }

    file1 = UploadFile(filename="image1.jpg", file=io.BytesIO(b"data"))

    async def form():  # noqa: RUF029
        return FormData([("files", file1)])

    request_mock.form = form

    fn = upload(app)
    with pytest.raises(ValueError) as err:
        await fn(request_mock)
    assert (
        err.value.args[0]
        == f"`{state.get_full_name()}.handle_upload2` handler should have a parameter annotated as list[rx.UploadFile]"
    )

    await app.state_manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [FileUploadState, ChildFileUploadState, GrandChildFileUploadState],
)
async def test_upload_file_background(
    state: FileUploadState | ChildFileUploadState | GrandChildFileUploadState,
    tmp_path: Path,
    token: str,
):
    """Test that an error is thrown handler is a background task.

    Args:
        state: The state class.
        tmp_path: Temporary path.
        token: a Token.
    """
    app = App(_state=State)

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{state.get_full_name()}.bg_upload",
    }

    file1 = UploadFile(filename="image1.jpg", file=io.BytesIO(b"data"))

    async def form():  # noqa: RUF029
        return FormData([("files", file1)])

    request_mock.form = form

    fn = upload(app)
    with pytest.raises(TypeError) as err:
        await fn(request_mock)
    assert (
        err.value.args[0]
        == f"@rx.event(background=True) is not supported for upload handler `{state.get_full_name()}.bg_upload`."
    )

    await app.state_manager.close()


def _build_chunk_upload_multipart_body(
    boundary: str,
    parts: list[tuple[str, str, str, bytes]],
) -> bytes:
    """Build a multipart upload body for chunk upload tests.

    Args:
        boundary: The multipart boundary string.
        parts: Tuples of field name, filename, content type, and payload.

    Returns:
        The encoded multipart body bytes.
    """
    body = bytearray()
    for field_name, filename, content_type, data in parts:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"\r\n'
            ).encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body)


def _make_chunk_upload_request(
    token: str,
    handler_name: str,
    body: bytes,
    *,
    content_type: str,
    stream_chunk_size: int = 17,
):
    """Create a mocked request for the chunk upload endpoint.

    Returns:
        A mocked Starlette request object.
    """
    request_mock = unittest.mock.Mock()
    request_mock.headers = Headers({
        "content-type": content_type,
        "reflex-client-token": token,
        "reflex-event-handler": handler_name,
    })
    request_mock.query_params = {}

    async def stream():
        for index in range(0, len(body), stream_chunk_size):
            yield body[index : index + stream_chunk_size]
        yield b""
        await asyncio.sleep(0)

    request_mock.stream = stream
    return request_mock


@pytest.mark.asyncio
async def test_upload_dispatches_chunk_handlers_on_upload_endpoint(
    tmp_path,
    token: str,
    mocker: MockerFixture,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
    mock_root_event_context: EventContext,
):
    """Test that the standard upload endpoint dispatches chunk handlers."""
    app = Mock(event_processor=attached_mock_base_state_event_processor)

    async with mock_root_event_context.state_manager.modify_state(
        BaseStateToken(ident=token, cls=ChunkUploadState)
    ) as root_state:
        substate = await root_state.get_state(ChunkUploadState)
        substate._tmp_path = tmp_path
        substate.chunk_records = []
        substate.completed_files = []

    upload_fn = upload(app)
    boundary = "chunk-upload-on-upload-endpoint-boundary"
    response = await upload_fn(
        _make_chunk_upload_request(
            token,
            f"{ChunkUploadState.get_full_name()}.chunk_handle_upload",
            _build_chunk_upload_multipart_body(
                boundary,
                [
                    ("files", "alpha.txt", "text/plain", b"abcde"),
                    ("files", "beta.txt", "text/plain", b"12345"),
                ],
            ),
            content_type=f"multipart/form-data; boundary={boundary}",
            stream_chunk_size=1,
        )
    )

    assert isinstance(response, StreamingResponse)
    assert response.status_code == 202

    updates = []
    async for state_update in response.body_iterator:
        updates.append(json.loads(str(state_update)))
    assert updates == [{}]

    await attached_mock_base_state_event_processor.join()
    if environment.REFLEX_OPLOCK_ENABLED.get():
        await mock_root_event_context.state_manager.close()

    state = await mock_root_event_context.state_manager.get_state(
        BaseStateToken(ident=token, cls=ChunkUploadState)
    )
    substate = await state.get_state(ChunkUploadState)
    assert isinstance(substate, ChunkUploadState)
    parsed_chunk_records = [
        (filename, int(offset), int(size), content_type)
        for filename, offset, size, content_type in (
            record.rsplit(":", 3) for record in substate.chunk_records
        )
    ]
    assert len(parsed_chunk_records) >= 4
    assert {filename for filename, *_ in parsed_chunk_records} == {
        "alpha.txt",
        "beta.txt",
    }
    assert all(
        content_type == "text/plain" for *_, content_type in parsed_chunk_records
    )
    assert (
        sum(
            size
            for filename, _offset, size, _content_type in parsed_chunk_records
            if filename == "alpha.txt"
        )
        == 5
    )
    assert (
        sum(
            size
            for filename, _offset, size, _content_type in parsed_chunk_records
            if filename == "beta.txt"
        )
        == 5
    )
    assert parsed_chunk_records[0][0] == "alpha.txt"
    assert parsed_chunk_records[-1][0] == "beta.txt"
    assert substate.completed_files == ["alpha.txt", "beta.txt"]
    assert (tmp_path / "alpha.txt").read_bytes() == b"abcde"
    assert (tmp_path / "beta.txt").read_bytes() == b"12345"


@pytest.mark.asyncio
async def test_upload_empty_chunk_request_dispatches_alias_handler(
    token: str,
    mocker: MockerFixture,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
    mock_root_event_context: EventContext,
):
    """Test that empty uploads still dispatch chunk alias handlers."""
    app = Mock(event_processor=attached_mock_base_state_event_processor)

    async with mock_root_event_context.state_manager.modify_state(
        BaseStateToken(ident=token, cls=ChunkUploadState)
    ) as root_state:
        substate = await root_state.get_state(ChunkUploadState)
        substate.chunk_records = []
        substate.completed_files = []

    upload_fn = upload(app)
    boundary = "chunk-upload-empty-alias-boundary"
    response = await upload_fn(
        _make_chunk_upload_request(
            token,
            f"{ChunkUploadState.get_full_name()}.chunk_handle_upload_alias",
            _build_chunk_upload_multipart_body(boundary, []),
            content_type=f"multipart/form-data; boundary={boundary}",
        )
    )

    assert isinstance(response, StreamingResponse)
    assert response.status_code == 202

    updates = []
    async for state_update in response.body_iterator:
        updates.append(json.loads(str(state_update)))
    assert updates == [{}]

    await attached_mock_base_state_event_processor.join()
    if environment.REFLEX_OPLOCK_ENABLED.get():
        await mock_root_event_context.state_manager.close()

    state = await mock_root_event_context.state_manager.get_state(
        BaseStateToken(ident=token, cls=ChunkUploadState)
    )
    substate = await state.get_state(ChunkUploadState)
    assert isinstance(substate, ChunkUploadState)
    assert substate.chunk_records == []
    assert substate.completed_files == ["chunks:0"]


@pytest.mark.asyncio
async def test_upload_chunk_invalid_offset_returns_400(
    token: str,
    mocker: MockerFixture,
    attached_mock_base_state_event_processor: BaseStateEventProcessor,
    mock_root_event_context: EventContext,
):
    """Test that malformed chunk metadata fails the standard upload request."""
    app = Mock(event_processor=attached_mock_base_state_event_processor)
    # The background task is expected to fail with a parse error for malformed input.
    attached_mock_base_state_event_processor.backend_exception_handler = None

    async with mock_root_event_context.state_manager.modify_state(
        BaseStateToken(ident=token, cls=ChunkUploadState)
    ) as root_state:
        substate = await root_state.get_state(ChunkUploadState)
        substate.chunk_records = []
        substate.completed_files = []

    upload_fn = upload(app)
    response = await upload_fn(
        _make_chunk_upload_request(
            token,
            f"{ChunkUploadState.get_full_name()}.chunk_handle_upload",
            b"abc",
            content_type="text/plain",
        )
    )

    assert response.status_code == 400
    assert json.loads(bytes(response.body).decode()) == {
        "detail": "Missing boundary in multipart."
    }

    await attached_mock_base_state_event_processor.join()
    if environment.REFLEX_OPLOCK_ENABLED.get():
        await mock_root_event_context.state_manager.close()

    state = await mock_root_event_context.state_manager.get_state(
        BaseStateToken(ident=token, cls=ChunkUploadState)
    )
    substate = await state.get_state(ChunkUploadState)
    assert isinstance(substate, ChunkUploadState)
    assert substate.chunk_records == []
    assert substate.completed_files == []


class DynamicState(State):
    """State class for testing dynamic route var.

    This is defined at module level because event handlers cannot be addressed
    correctly when the class is defined as a local.

    There are several counters:
      * loaded: counts how many times `on_load` was triggered by the hydrate middleware
      * counter: counts how many times `on_counter` was triggered by a non-navigational event
          -> these events should NOT trigger reload or recalculation of router_data dependent vars
      * side_effect_counter: counts how many times a computed var was
        recalculated when the dynamic route var was dirty
    """

    is_hydrated: bool = False
    loaded: int = 0
    counter: int = 0

    @rx.event
    def on_load(self):
        """Event handler for page on_load, should trigger for all navigation events."""
        self.loaded = self.loaded + 1

    @rx.event
    def on_counter(self):
        """Increment the counter var."""
        self.counter = self.counter + 1

    @computed_var
    def comp_dynamic(self) -> str:
        """A computed var that depends on the dynamic var.

        Returns:
            same as self.dynamic
        """
        return self.dynamic  # pyright: ignore[reportAttributeAccessIssue]


def test_dynamic_arg_shadow(
    index_page: ComponentCallable,
    token: str,
    app_module_mock: unittest.mock.Mock,
    mocker: MockerFixture,
):
    """Create app with dynamic route var and try to add a page with a dynamic arg that shadows a state var.

    Args:
        index_page: The index page.
        token: a Token.
        app_module_mock: Mocked app module.
        mocker: pytest mocker object.
    """
    arg_name = "counter"
    route = f"/test/[{arg_name}]"
    app = app_module_mock.app = App(_state=DynamicState)
    assert app._state is not None
    with pytest.raises(NameError):
        app.add_page(index_page, route=route, on_load=DynamicState.on_load)


def test_multiple_dynamic_args(
    index_page: ComponentCallable,
    token: str,
    app_module_mock: unittest.mock.Mock,
    mocker: MockerFixture,
):
    """Create app with multiple dynamic route vars with the same name.

    Args:
        index_page: The index page.
        token: a Token.
        app_module_mock: Mocked app module.
        mocker: pytest mocker object.
    """
    arg_name = "my_arg"
    route = f"/test/[{arg_name}]"
    route2 = f"/test2/[{arg_name}]"
    app = app_module_mock.app = App(_state=EmptyState)
    app.add_page(index_page, route=route)
    app.add_page(index_page, route=route2)


@pytest.fixture
def cleanup_dynamic_arg():
    """Fixture to reset DynamicState class vars after each test."""
    yield
    with contextlib.suppress(AttributeError):
        del State.dynamic  # pyright: ignore[reportAttributeAccessIssue]

    State.computed_vars.pop("dynamic", None)
    State.vars.pop("dynamic", None)
    State._var_dependencies = {}
    State._potentially_dirty_states = set()
    State._always_dirty_computed_vars = set()
    reload_state_module(__name__)


@pytest.mark.usefixtures("cleanup_dynamic_arg")
@pytest.mark.asyncio
async def test_dynamic_route_var_route_change_completed_on_load(
    index_page: ComponentCallable,
    token: str,
    app_module_mock: unittest.mock.Mock,
    mock_root_event_context: EventContext,
    mock_base_state_event_processor: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, dict[str, dict[str, Any]]]],
    emitted_events: list[tuple[str, tuple[Event, ...]]],
):
    """Create app with dynamic route var, and simulate navigation.

    on_load should fire, allowing any additional vars to be updated before the
    initial page hydrate.

    Args:
        index_page: The index page.
        token: a Token.
        app_module_mock: Mocked app module.
        mock_root_event_context: Mocked root event context.
        mock_base_state_event_processor: Mocked BaseStateEventProcessor.
        emitted_deltas: List to store emitted deltas.
        emitted_events: List to store emitted events.
    """
    OnLoadInternalState._app_ref = None
    arg_name = "dynamic"
    route = f"test/[{arg_name}]"
    app = app_module_mock.app = App()
    app._state_manager = mock_root_event_context.state_manager
    assert app._state is not None
    assert arg_name not in app._state.vars
    app.add_page(index_page, route=route, on_load=DynamicState.on_load)
    app._compile_page(route)
    assert arg_name in app._state.vars
    assert arg_name in app._state.computed_vars
    assert app._state.computed_vars[arg_name]._deps(objclass=DynamicState) == {
        DynamicState.get_full_name(): {constants.ROUTER},
    }
    assert constants.ROUTER in app._state()._var_dependencies

    substate_token = BaseStateToken(ident=token, cls=DynamicState)
    exp_vals = ["foo", "foobar", "baz"]

    def _event(name, val, **kwargs):
        return Event(
            name=name,
            router_data=kwargs.pop(
                "router_data",
                {
                    "pathname": "/" + route,
                    "query": {arg_name: val},
                    "asPath": f"/test/{val}",
                },
            ),
            payload=kwargs.pop("payload", {}),
            **kwargs,
        )

    def _dynamic_state_event(name, val, **kwargs):
        return _event(
            name=format.format_event_handler(getattr(DynamicState, name)),
            val=val,
            **kwargs,
        )

    prev_exp_val = ""
    for exp_index, exp_val in enumerate(exp_vals):
        on_load_internal = _event(
            name=f"{OnLoadInternalState.get_full_name()}.{constants.CompileVars.ON_LOAD_INTERNAL.rpartition('.')[2]}",
            val=exp_val,
        )
        exp_router = RouterData.from_router_data(on_load_internal.router_data)
        async with mock_base_state_event_processor as processor:
            await processor.enqueue(
                token,
                on_load_internal,
            )
            await processor.join()
        assert emitted_deltas == [
            (
                token,
                {
                    State.get_full_name(): {
                        arg_name + FIELD_MARKER: exp_val,
                        constants.CompileVars.IS_HYDRATED + FIELD_MARKER: False,
                        "router" + FIELD_MARKER: exp_router,
                    },
                    DynamicState.get_full_name(): {
                        f"comp_{arg_name}" + FIELD_MARKER: exp_val,
                    },
                },
            ),
            (
                token,
                {
                    DynamicState.get_full_name(): {
                        "loaded" + FIELD_MARKER: exp_index + 1,
                    },
                },
            ),
            (
                token,
                {
                    State.get_full_name(): {
                        "is_hydrated" + FIELD_MARKER: True,
                    },
                },
            ),
        ]
        assert emitted_events == []
        if isinstance(app.state_manager, StateManagerRedis):
            # When redis is used, the state is not updated until the processing is complete
            state = await app.state_manager.get_state(substate_token)
            assert state.dynamic == prev_exp_val  # pyright: ignore[reportAttributeAccessIssue]

        if environment.REFLEX_OPLOCK_ENABLED.get():
            await app.state_manager.close()

        # check that router data was written to the state_manager store
        state = await app.state_manager.get_state(substate_token)
        assert state.dynamic == exp_val  # pyright: ignore[reportAttributeAccessIssue]

        # a simple state update event should NOT trigger on_load or route var side effects
        emitted_deltas.clear()
        emitted_events.clear()
        async with mock_base_state_event_processor as processor:
            await processor.enqueue(
                token,
                _dynamic_state_event(name="on_counter", val=exp_val),
            )
        assert emitted_deltas == [
            (
                token,
                {
                    DynamicState.get_full_name(): {
                        "counter" + FIELD_MARKER: exp_index + 1,
                    }
                },
            )
        ]
        assert emitted_events == []
        emitted_deltas.clear()
        emitted_events.clear()
        prev_exp_val = exp_val

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await app.state_manager.close()
    state = await app.state_manager.get_state(substate_token)
    assert isinstance(state, State)
    dynamic_state = await state.get_state(DynamicState)
    assert isinstance(dynamic_state, DynamicState)
    assert dynamic_state.loaded == len(exp_vals)
    assert dynamic_state.counter == len(exp_vals)

    await app.state_manager.close()


@pytest.mark.asyncio
async def test_process_events(
    token: str,
    app_module_mock: unittest.mock.Mock,
    mock_base_state_event_processor: BaseStateEventProcessor,
    mock_root_event_context: EventContext,
    emitted_deltas: list[tuple[str, dict[str, dict[str, Any]]]],
):
    """Test that an event is processed properly and that it is postprocessed
    n+1 times. Also check that the processing flag of the last stateupdate is set to
    False.

    Args:
        token: a Token.
        app_module_mock: The mock for the app module, used to patch the app instance.
        mock_base_state_event_processor: BaseStateEventProcessor Fixture.
        mock_root_event_context: The mock for the root event context, used to patch the app
            state manager.
        emitted_deltas: List to store emitted deltas.
    """
    event = Event(
        name=f"{GenState.get_name()}.go",
        payload={"c": 5},
        router_data={},
    )

    async with mock_base_state_event_processor as processor:
        await processor.enqueue(
            token,
            event,
        )

    if environment.REFLEX_OPLOCK_ENABLED.get():
        await mock_root_event_context.state_manager.close()

    gen_state = await mock_root_event_context.state_manager.get_state(
        BaseStateToken(ident=token, cls=GenState),
    )
    assert isinstance(gen_state, GenState)
    assert gen_state.value == 5
    assert len(emitted_deltas) == 5

    await mock_root_event_context.state_manager.close()


@pytest.fixture
def compilable_app(tmp_path: Path) -> Generator[tuple[App, Path], None, None]:
    """Fixture for an app that can be compiled.

    Args:
        tmp_path: Temporary path.

    Yields:
        Tuple containing (app instance, Path to ".web" directory)

        The working directory is set to the app dir (parent of .web),
        allowing app.compile() to be called.
    """
    app_path = tmp_path / "app"
    web_dir = app_path / ".web"
    web_dir.mkdir(parents=True)
    (web_dir / constants.PackageJson.PATH).touch()
    (web_dir / constants.Dirs.POSTCSS_JS).touch()
    (web_dir / constants.Dirs.POSTCSS_JS).write_text(
        """
module.exports = {
  plugins: {
    "postcss-import": {},
    autoprefixer: {},
  },
};
""",
    )
    app = App(theme=None)
    app._get_frontend_packages = unittest.mock.Mock()
    with chdir(app_path):
        yield app, web_dir


@pytest.mark.parametrize(
    "react_strict_mode",
    [True, False],
)
def test_app_wrap_compile_theme(
    react_strict_mode: bool,
    compilable_app: tuple[App, Path],
    mocker: MockerFixture,
):
    """Test that the radix theme component wraps the app.

    Args:
        react_strict_mode: Whether to use React Strict Mode.
        compilable_app: compilable_app fixture.
        mocker: pytest mocker object.
    """
    conf = rx.Config(app_name="testing", react_strict_mode=react_strict_mode)
    mocker.patch("reflex_base.config._get_config", return_value=conf)
    app, web_dir = compilable_app
    mocker.patch("reflex.utils.prerequisites.get_web_dir", return_value=web_dir)
    app.theme = rx.theme(accent_color="plum")
    app._compile()
    app_js_contents = (
        web_dir / constants.Dirs.PAGES / constants.PageNames.APP_ROOT
    ).read_text()
    function_app_definition = app_js_contents[
        app_js_contents.index("function AppWrap") : app_js_contents.index(
            "export function Layout"
        )
    ].strip()

    expected = (
        "function AppWrap({children}) {\n"
        "const [addEvents, connectErrors] = useContext(EventLoopContext);\n\n\n\n"
        "return ("
        + ("jsx(StrictMode,{}," if react_strict_mode else "")
        + "jsx(ErrorBoundary,{"
        """fallbackRender:((event_args) => (jsx("div", ({css:({ ["height"] : "100%", ["width"] : "100%", ["position"] : "absolute", ["backgroundColor"] : "#fff", ["color"] : "#000", ["display"] : "flex", ["alignItems"] : "center", ["justifyContent"] : "center" })}), (jsx("div", ({css:({ ["display"] : "flex", ["flexDirection"] : "column", ["gap"] : "0.5rem", ["maxWidth"] : "min(80ch, 90vw)", ["borderRadius"] : "0.25rem", ["padding"] : "1rem" })}), (jsx("div", ({css:({ ["opacity"] : "0.5", ["display"] : "flex", ["gap"] : "4vmin", ["alignItems"] : "center" })}), (jsx("svg", ({className:"lucide lucide-frown-icon lucide-frown",fill:"none",stroke:"currentColor","stroke-linecap":"round","stroke-linejoin":"round","stroke-width":"2",viewBox:"0 0 24 24",width:"25vmin",xmlns:"http://www.w3.org/2000/svg"}), (jsx("circle", ({cx:"12",cy:"12",r:"10"}))), (jsx("path", ({d:"M16 16s-1.5-2-4-2-4 2-4 2"}))), (jsx("line", ({x1:"9",x2:"9.01",y1:"9",y2:"9"}))), (jsx("line", ({x1:"15",x2:"15.01",y1:"9",y2:"9"}))))), (jsx("h2", ({css:({ ["fontSize"] : "5vmin", ["fontWeight"] : "bold" })}), "An error occurred while rendering this page.")))), (jsx("p", ({css:({ ["opacity"] : "0.75", ["marginBlock"] : "1rem" })}), "This is an error with the application itself. Refreshing the page might help.")), (jsx("div", ({css:({ ["width"] : "100%", ["background"] : "color-mix(in srgb, currentColor 5%, transparent)", ["maxHeight"] : "15rem", ["overflow"] : "auto", ["borderRadius"] : "0.4rem" })}), (jsx("div", ({css:({ ["padding"] : "0.5rem" })}), (jsx("pre", ({css:({ ["wordBreak"] : "break-word", ["whiteSpace"] : "pre-wrap" })}), event_args.error.name + \': \' + event_args.error.message + \'\\n\' + event_args.error.stack)))))), (jsx("button", ({css:({ ["padding"] : "0.35rem 1.35rem", ["marginBlock"] : "0.5rem", ["marginInlineStart"] : "auto", ["background"] : "color-mix(in srgb, currentColor 15%, transparent)", ["borderRadius"] : "0.4rem", ["width"] : "fit-content", ["&:hover"] : ({ ["background"] : "color-mix(in srgb, currentColor 25%, transparent)" }), ["&:active"] : ({ ["background"] : "color-mix(in srgb, currentColor 35%, transparent)" }) }),onClick:((_e) => (addEvents([(ReflexEvent("_call_function", ({ ["function"] : (() => (navigator?.["clipboard"]?.["writeText"](event_args.error.name + \': \' + event_args.error.message + \'\\n\' + event_args.error.stack))), ["callback"] : null }), ({  })))], [_e], ({  }))))}), "Copy")), (jsx("hr", ({css:({ ["borderColor"] : "currentColor", ["opacity"] : "0.25" })}))), (jsx(ReactRouterLink, ({to:"https://reflex.dev"}), (jsx("div", ({css:({ ["display"] : "flex", ["alignItems"] : "baseline", ["justifyContent"] : "center", ["fontFamily"] : "monospace", ["--default-font-family"] : "monospace", ["gap"] : "0.5rem" })}), "Built with ", (jsx("svg", ({"aria-label":"Reflex",css:({ ["fill"] : "currentColor" }),height:"12",role:"img",width:"56",xmlns:"http://www.w3.org/2000/svg"}), (jsx("path", ({d:"M0 11.5999V0.399902H8.96V4.8799H6.72V2.6399H2.24V4.8799H6.72V7.1199H2.24V11.5999H0ZM6.72 11.5999V7.1199H8.96V11.5999H6.72Z"}))), (jsx("path", ({d:"M11.2 11.5999V0.399902H17.92V2.6399H13.44V4.8799H17.92V7.1199H13.44V9.3599H17.92V11.5999H11.2Z"}))), (jsx("path", ({d:"M20.16 11.5999V0.399902H26.88V2.6399H22.4V4.8799H26.88V7.1199H22.4V11.5999H20.16Z"}))), (jsx("path", ({d:"M29.12 11.5999V0.399902H31.36V9.3599H35.84V11.5999H29.12Z"}))), (jsx("path", ({d:"M38.08 11.5999V0.399902H44.8V2.6399H40.32V4.8799H44.8V7.1199H40.32V9.3599H44.8V11.5999H38.08Z"}))), (jsx("path", ({d:"M47.04 4.8799V0.399902H49.28V4.8799H47.04ZM53.76 4.8799V0.399902H56V4.8799H53.76ZM49.28 7.1199V4.8799H53.76V7.1199H49.28ZM47.04 11.5999V7.1199H49.28V11.5999H47.04ZM53.76 11.5999V7.1199H56V11.5999H53.76Z"}))), (jsx("title", ({}), "Reflex"))))))))))))),"""
        """onError:((_error, _info) => (addEvents([(ReflexEvent("reflex___state____state.reflex___state____frontend_event_exception_state.handle_frontend_exception", ({ ["info"] : ((((_error?.["name"]+": ")+_error?.["message"])+"\\n")+_error?.["stack"]), ["component_stack"] : _info?.["componentStack"] }), ({  })))], [_error, _info], ({  }))))"""
        + "},"
        + "jsx(RadixThemesColorModeProvider,{},"
        + "jsx(Fragment,{},"
        + "jsx(MemoizedToastProvider,{},),"
        + "jsx(RadixThemesTheme,{accentColor:\"plum\",css:{...theme.styles.global[':root'], ...theme.styles.global.body}},"
        + "jsx(Fragment,{},"
        + "jsx(DefaultOverlayComponents,{},),"
        + "jsx(Fragment,{},"
        + "children"
        "))))))" + (")" if react_strict_mode else "") + ")"
        "\n}"
    )
    assert expected.split(",") == function_app_definition.split(",")


@pytest.mark.parametrize(
    "react_strict_mode",
    [True, False],
)
def test_app_wrap_priority(
    react_strict_mode: bool,
    compilable_app: tuple[App, Path],
    mocker: MockerFixture,
):
    """Test that the app wrap components are wrapped in the correct order.

    Args:
        react_strict_mode: Whether to use React Strict Mode.
        compilable_app: compilable_app fixture.
        mocker: pytest mocker object.
    """
    conf = rx.Config(app_name="testing", react_strict_mode=react_strict_mode)
    mocker.patch("reflex_base.config._get_config", return_value=conf)

    app, web_dir = compilable_app

    class Fragment1(Component):
        tag = "Fragment1"

        def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:  # pyright: ignore [reportIncompatibleMethodOverride]
            return {(99, "Box"): rx.box()}

    class Fragment2(Component):
        tag = "Fragment2"

        def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:  # pyright: ignore [reportIncompatibleMethodOverride]
            return {(50, "Text"): rx.text()}

    class Fragment3(Component):
        tag = "Fragment3"

        def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:  # pyright: ignore [reportIncompatibleMethodOverride]
            return {(10, "Fragment2"): Fragment2.create()}

    def page():
        return Fragment1.create(Fragment3.create())

    app.add_page(page)
    app._compile()
    app_js_contents = (
        web_dir / constants.Dirs.PAGES / constants.PageNames.APP_ROOT
    ).read_text()
    function_app_definition = app_js_contents[
        app_js_contents.index("function AppWrap") : app_js_contents.index(
            "export function Layout"
        )
    ].strip()

    expected = (
        "function AppWrap({children}) {\n"
        "const [addEvents, connectErrors] = useContext(EventLoopContext);\n\n\n\n"
        "return ("
        + ("jsx(StrictMode,{}," if react_strict_mode else "")
        + "jsx(RadixThemesBox,{},"
        "jsx(ErrorBoundary,{"
        """fallbackRender:((event_args) => (jsx("div", ({css:({ ["height"] : "100%", ["width"] : "100%", ["position"] : "absolute", ["backgroundColor"] : "#fff", ["color"] : "#000", ["display"] : "flex", ["alignItems"] : "center", ["justifyContent"] : "center" })}), (jsx("div", ({css:({ ["display"] : "flex", ["flexDirection"] : "column", ["gap"] : "0.5rem", ["maxWidth"] : "min(80ch, 90vw)", ["borderRadius"] : "0.25rem", ["padding"] : "1rem" })}), (jsx("div", ({css:({ ["opacity"] : "0.5", ["display"] : "flex", ["gap"] : "4vmin", ["alignItems"] : "center" })}), (jsx("svg", ({className:"lucide lucide-frown-icon lucide-frown",fill:"none",stroke:"currentColor","stroke-linecap":"round","stroke-linejoin":"round","stroke-width":"2",viewBox:"0 0 24 24",width:"25vmin",xmlns:"http://www.w3.org/2000/svg"}), (jsx("circle", ({cx:"12",cy:"12",r:"10"}))), (jsx("path", ({d:"M16 16s-1.5-2-4-2-4 2-4 2"}))), (jsx("line", ({x1:"9",x2:"9.01",y1:"9",y2:"9"}))), (jsx("line", ({x1:"15",x2:"15.01",y1:"9",y2:"9"}))))), (jsx("h2", ({css:({ ["fontSize"] : "5vmin", ["fontWeight"] : "bold" })}), "An error occurred while rendering this page.")))), (jsx("p", ({css:({ ["opacity"] : "0.75", ["marginBlock"] : "1rem" })}), "This is an error with the application itself. Refreshing the page might help.")), (jsx("div", ({css:({ ["width"] : "100%", ["background"] : "color-mix(in srgb, currentColor 5%, transparent)", ["maxHeight"] : "15rem", ["overflow"] : "auto", ["borderRadius"] : "0.4rem" })}), (jsx("div", ({css:({ ["padding"] : "0.5rem" })}), (jsx("pre", ({css:({ ["wordBreak"] : "break-word", ["whiteSpace"] : "pre-wrap" })}), event_args.error.name + \': \' + event_args.error.message + \'\\n\' + event_args.error.stack)))))), (jsx("button", ({css:({ ["padding"] : "0.35rem 1.35rem", ["marginBlock"] : "0.5rem", ["marginInlineStart"] : "auto", ["background"] : "color-mix(in srgb, currentColor 15%, transparent)", ["borderRadius"] : "0.4rem", ["width"] : "fit-content", ["&:hover"] : ({ ["background"] : "color-mix(in srgb, currentColor 25%, transparent)" }), ["&:active"] : ({ ["background"] : "color-mix(in srgb, currentColor 35%, transparent)" }) }),onClick:((_e) => (addEvents([(ReflexEvent("_call_function", ({ ["function"] : (() => (navigator?.["clipboard"]?.["writeText"](event_args.error.name + \': \' + event_args.error.message + \'\\n\' + event_args.error.stack))), ["callback"] : null }), ({  })))], [_e], ({  }))))}), "Copy")), (jsx("hr", ({css:({ ["borderColor"] : "currentColor", ["opacity"] : "0.25" })}))), (jsx(ReactRouterLink, ({to:"https://reflex.dev"}), (jsx("div", ({css:({ ["display"] : "flex", ["alignItems"] : "baseline", ["justifyContent"] : "center", ["fontFamily"] : "monospace", ["--default-font-family"] : "monospace", ["gap"] : "0.5rem" })}), "Built with ", (jsx("svg", ({"aria-label":"Reflex",css:({ ["fill"] : "currentColor" }),height:"12",role:"img",width:"56",xmlns:"http://www.w3.org/2000/svg"}), (jsx("path", ({d:"M0 11.5999V0.399902H8.96V4.8799H6.72V2.6399H2.24V4.8799H6.72V7.1199H2.24V11.5999H0ZM6.72 11.5999V7.1199H8.96V11.5999H6.72Z"}))), (jsx("path", ({d:"M11.2 11.5999V0.399902H17.92V2.6399H13.44V4.8799H17.92V7.1199H13.44V9.3599H17.92V11.5999H11.2Z"}))), (jsx("path", ({d:"M20.16 11.5999V0.399902H26.88V2.6399H22.4V4.8799H26.88V7.1199H22.4V11.5999H20.16Z"}))), (jsx("path", ({d:"M29.12 11.5999V0.399902H31.36V9.3599H35.84V11.5999H29.12Z"}))), (jsx("path", ({d:"M38.08 11.5999V0.399902H44.8V2.6399H40.32V4.8799H44.8V7.1199H40.32V9.3599H44.8V11.5999H38.08Z"}))), (jsx("path", ({d:"M47.04 4.8799V0.399902H49.28V4.8799H47.04ZM53.76 4.8799V0.399902H56V4.8799H53.76ZM49.28 7.1199V4.8799H53.76V7.1199H49.28ZM47.04 11.5999V7.1199H49.28V11.5999H47.04ZM53.76 11.5999V7.1199H56V11.5999H53.76Z"}))), (jsx("title", ({}), "Reflex"))))))))))))),"""
        """onError:((_error, _info) => (addEvents([(ReflexEvent("reflex___state____state.reflex___state____frontend_event_exception_state.handle_frontend_exception", ({ ["info"] : ((((_error?.["name"]+": ")+_error?.["message"])+"\\n")+_error?.["stack"]), ["component_stack"] : _info?.["componentStack"] }), ({  })))], [_error, _info], ({  }))))"""
        + "},"
        + 'jsx(RadixThemesText,{as:"p"},'
        + "jsx(RadixThemesColorModeProvider,{},"
        + "jsx(Fragment,{},"
        + "jsx(MemoizedToastProvider,{},),"
        + "jsx(Fragment2,{},"
        + "jsx(Fragment,{},"
        + "jsx(DefaultOverlayComponents,{},),"
        + "jsx(Fragment,{},"
        + "children"
        ")))))))" + (")" if react_strict_mode else "") + "))\n}"
    )
    assert expected.split(",") == function_app_definition.split(",")


def test_app_state_determination():
    """Test that the stateless status of an app is determined correctly."""
    a1 = App()
    assert a1._state is not None

    a2 = App(enable_state=False)
    assert a2._state is None


def test_raise_on_state():
    """Test that the state is set."""
    # state kwargs is deprecated, we just make sure the app is created anyway.
    app = App(_state=State)
    assert app._state is not None
    assert issubclass(app._state, State)


def test_call_app():
    """Test that the app can be called."""
    app = App()
    app._compile = unittest.mock.Mock()
    api = app()
    assert isinstance(api, Starlette)


def test_app_with_optional_endpoints():
    from reflex_components_core.core.upload import Upload

    app = App()
    Upload.is_used = True
    app._add_optional_endpoints()
    # TODO: verify the availability of the endpoints in app.api


def test_app_state_manager():
    app = App(enable_state=False)
    with pytest.raises(ValueError):
        app.state_manager
    app._enable_state()
    assert app.state_manager is not None
    assert isinstance(
        app.state_manager, (StateManagerMemory, StateManagerDisk, StateManagerRedis)
    )


def test_generate_component():
    def index():
        return rx.box("Index")

    def index_mismatch():
        return rx.match(
            1,
            (1, rx.box("Index")),
            (2, "About"),
            "Bar",
        )

    comp = App._generate_component(index)
    assert isinstance(comp, Component)

    with pytest.raises(exceptions.MatchTypeError):
        App._generate_component(index_mismatch)


def test_add_page_component_returning_tuple():
    """Test that a component or render method returning a
    tuple is unpacked in a Fragment.
    """
    app = App()

    def index():
        return rx.text("first"), rx.text("second")

    def page2():
        return (rx.text("third"),)

    app.add_page(index)
    app.add_page(page2)

    app._compile_page("index")
    app._compile_page("page2")

    fragment_wrapper = app._pages["index"].children[0]
    assert isinstance(fragment_wrapper, Fragment)
    first_text = fragment_wrapper.children[0]
    assert isinstance(first_text, Text)
    assert isinstance(first_text.children[0], Bare)
    assert str(first_text.children[0].contents) == '"first"'
    second_text = fragment_wrapper.children[1]
    assert isinstance(second_text, Text)
    assert isinstance(second_text.children[0], Bare)
    assert str(second_text.children[0].contents) == '"second"'

    # Test page with trailing comma.
    page2_fragment_wrapper = app._pages["page2"].children[0]
    assert isinstance(page2_fragment_wrapper, Fragment)
    third_text = page2_fragment_wrapper.children[0]
    assert isinstance(third_text, Text)
    assert isinstance(third_text.children[0], Bare)
    assert str(third_text.children[0].contents) == '"third"'


def test_app_with_valid_var_dependencies(compilable_app: tuple[App, Path]):
    app, _ = compilable_app

    class ValidDepState(BaseState):
        base: int = 0
        _backend: int = 0

        @computed_var()
        def foo(self) -> str:
            return "foo"

        @computed_var(deps=["_backend", "base", foo])
        def bar(self) -> str:
            return "bar"

    class Child1(ValidDepState):
        @computed_var(deps=["base", ValidDepState.bar])
        def other(self) -> str:
            return "other"

    class Child2(ValidDepState):
        @computed_var(deps=["base", Child1.other])
        def other(self) -> str:
            return "other"

    app._state = ValidDepState
    app._compile()


def test_app_with_invalid_var_dependencies(compilable_app: tuple[App, Path]):
    app, _ = compilable_app

    class InvalidDepState(BaseState):
        @computed_var(deps=["foolksjdf"])
        def bar(self) -> str:
            return "bar"

    app._state = InvalidDepState
    with pytest.raises(exceptions.VarDependencyError):
        app._compile()


# Test custom exception handlers


def valid_custom_handler(exception: Exception, logger: str = "test"):
    print("Custom Backend Exception")
    print(exception)


def custom_exception_handler_with_wrong_arg_order(
    logger: str,
    exception: Exception,  # Should be first
):
    print("Custom Backend Exception")
    print(exception)


def custom_exception_handler_with_wrong_argspec(
    exception: str,  # Should be Exception
):
    print("Custom Backend Exception")
    print(exception)


class DummyExceptionHandler:
    """Dummy exception handler class."""

    def handle(self, exception: Exception):
        """Handle the exception.

        Args:
            exception: The exception.

        """
        print("Custom Backend Exception")
        print(exception)


custom_exception_handlers = {
    "lambda": lambda exception: print("Custom Exception Handler", exception),
    "wrong_argspec": custom_exception_handler_with_wrong_argspec,
    "wrong_arg_order": custom_exception_handler_with_wrong_arg_order,
    "valid": valid_custom_handler,
    "partial": functools.partial(valid_custom_handler, logger="test"),
    "method": DummyExceptionHandler().handle,
}


@pytest.mark.parametrize(
    ("handler_fn", "expected"),
    [
        pytest.param(
            custom_exception_handlers["partial"],
            pytest.raises(ValueError),
            id="partial",
        ),
        pytest.param(
            custom_exception_handlers["lambda"],
            pytest.raises(ValueError),
            id="lambda",
        ),
        pytest.param(
            custom_exception_handlers["wrong_argspec"],
            pytest.raises(ValueError),
            id="wrong_argspec",
        ),
        pytest.param(
            custom_exception_handlers["wrong_arg_order"],
            pytest.raises(ValueError),
            id="wrong_arg_order",
        ),
        pytest.param(
            custom_exception_handlers["valid"],
            does_not_raise(),
            id="valid_handler",
        ),
        pytest.param(
            custom_exception_handlers["method"],
            does_not_raise(),
            id="valid_class_method",
        ),
    ],
)
def test_frontend_exception_handler_validation(handler_fn, expected):
    """Test that the custom frontend exception handler is properly validated.

    Args:
        handler_fn: The handler function.
        expected: The expected result.

    """
    with expected:
        rx.App(frontend_exception_handler=handler_fn)._validate_exception_handlers()


def backend_exception_handler_with_wrong_return_type(exception: Exception) -> int:
    """Custom backend exception handler with wrong return type.

    Args:
        exception: The exception.

    Returns:
        int: The wrong return type.

    """
    print("Custom Backend Exception")
    print(exception)

    return 5


@pytest.mark.parametrize(
    ("handler_fn", "expected"),
    [
        pytest.param(
            backend_exception_handler_with_wrong_return_type,
            pytest.raises(ValueError),
            id="wrong_return_type",
        ),
        pytest.param(
            custom_exception_handlers["partial"],
            pytest.raises(ValueError),
            id="partial",
        ),
        pytest.param(
            custom_exception_handlers["lambda"],
            pytest.raises(ValueError),
            id="lambda",
        ),
        pytest.param(
            custom_exception_handlers["wrong_argspec"],
            pytest.raises(ValueError),
            id="wrong_argspec",
        ),
        pytest.param(
            custom_exception_handlers["wrong_arg_order"],
            pytest.raises(ValueError),
            id="wrong_arg_order",
        ),
        pytest.param(
            custom_exception_handlers["valid"],
            does_not_raise(),
            id="valid_handler",
        ),
        pytest.param(
            custom_exception_handlers["method"],
            does_not_raise(),
            id="valid_class_method",
        ),
    ],
)
def test_backend_exception_handler_validation(handler_fn, expected):
    """Test that the custom backend exception handler is properly validated.

    Args:
        handler_fn: The handler function.
        expected: The expected result.

    """
    with expected:
        rx.App(backend_exception_handler=handler_fn)._validate_exception_handlers()


@pytest.mark.parametrize(
    ("substate", "frontend"),
    [
        pytest.param(False, True, id="root_state_frontend"),
        pytest.param(False, False, id="root_state_backend"),
        pytest.param(True, True, id="substate_frontend"),
        pytest.param(True, False, id="substate_backend"),
    ],
)
@pytest.mark.asyncio
async def test_app_modify_state_clean(token: str, substate: bool, frontend: bool):
    """Test that modify_state does not leave dirty_vars or dirty_substates.

    Args:
        token: A client token.
        substate: Whether to modify a substate.
        frontend: Whether to modify a frontend or backend var.
    """

    class Base(BaseState):
        count: int = 0
        _backend: int = 0

    class Sub(Base):
        sub_count: int = 0
        _sub_backend: int = 0

    app = App(_state=Base)
    app._event_namespace = AsyncMock()

    async with app.modify_state(
        token=BaseStateToken(ident=token, cls=Sub)
    ) as root_state:
        sub = root_state.substates[Sub.get_name()]
        if substate:
            if frontend:
                sub.sub_count = 1
            else:
                sub._sub_backend = 1
        else:
            if frontend:
                root_state.count = 1
            else:
                root_state._backend = 1

    assert not root_state.dirty_vars
    assert not root_state.dirty_substates
    if substate:
        assert sub._was_touched
        assert not root_state._was_touched
    else:
        assert root_state._was_touched
        assert not sub._was_touched

    if frontend:
        assert app._event_namespace.emit_update.call_count == 1
        if substate:
            exp_delta = {Sub.get_full_name(): {"sub_count_rx_state_": 1}}
        else:
            exp_delta = {Base.get_full_name(): {"count_rx_state_": 1}}
        assert (
            app._event_namespace.emit_update.call_args.kwargs["update"].delta
            == exp_delta
        )
    else:
        assert app._event_namespace.emit_update.call_count == 0


@pytest.fixture
def app_with_processor() -> App:
    """Create an App with a mocked event processor that has a root context.

    Returns:
        An App instance with a mock event processor and root context.
    """
    app = App(_state=EmptyState)
    root_context = EventContext(
        token="",
        state_manager=StateManagerMemory(),
        enqueue_impl=AsyncMock(),
    )
    processor = Mock()
    processor._root_context = root_context
    app._event_processor = processor
    return app


@pytest.fixture
def isolated_context() -> contextvars.Context:
    """Create a fresh empty contextvars.Context.

    Returns:
        A new Context with no variables set.
    """
    return contextvars.Context()


@pytest.fixture(
    params=[False, True],
    ids=["unset_registration_context", "preset_registration_context"],
)
def pre_set_registration_context(
    isolated_context: contextvars.Context,
    request: pytest.FixtureRequest,
) -> RegistrationContext | None:
    """Optionally pre-set a RegistrationContext in the isolated context.

    Args:
        isolated_context: The empty context to optionally populate.
        request: The pytest fixture request with the param value.

    Returns:
        The pre-set RegistrationContext, or None if unset.
    """
    if request.param:
        ctx = RegistrationContext()
        isolated_context.run(RegistrationContext.set, ctx)
        return ctx
    return None


@pytest.fixture(
    params=[False, True], ids=["unset_event_context", "preset_event_context"]
)
def pre_set_event_context(
    isolated_context: contextvars.Context,
    request: pytest.FixtureRequest,
) -> EventContext | None:
    """Optionally pre-set an EventContext in the isolated context.

    Args:
        isolated_context: The empty context to optionally populate.
        request: The pytest fixture request with the param value.

    Returns:
        The pre-set EventContext, or None if unset.
    """
    if request.param:
        ctx = EventContext(
            token="pre-existing",
            state_manager=StateManagerMemory(),
            enqueue_impl=AsyncMock(),
        )
        isolated_context.run(EventContext.set, ctx)
        return ctx
    return None


def test_set_contexts(
    app_with_processor: App,
    pre_set_registration_context: RegistrationContext | None,
    pre_set_event_context: EventContext | None,
    isolated_context: contextvars.Context,
):
    """set_contexts sets absent contexts, preserves existing ones, and resets on exit."""

    def _test():
        with app_with_processor.set_contexts():
            # Pre-existing contexts are preserved; absent ones are filled in.
            if pre_set_registration_context is not None:
                assert RegistrationContext.get() is pre_set_registration_context
            else:
                assert (
                    RegistrationContext.get()
                    is app_with_processor._registration_context
                )

            if pre_set_event_context is not None:
                assert EventContext.get() is pre_set_event_context
            else:
                assert app_with_processor._event_processor is not None
                assert (
                    EventContext.get()
                    is app_with_processor._event_processor._root_context
                )

        # After exit: pushed contexts are reset, pre-existing ones remain.
        if pre_set_registration_context is not None:
            assert RegistrationContext.get() is pre_set_registration_context
        else:
            with pytest.raises(LookupError):
                RegistrationContext.get()

        if pre_set_event_context is not None:
            assert EventContext.get() is pre_set_event_context
        else:
            with pytest.raises(LookupError):
                EventContext.get()

    isolated_context.run(_test)


def test_set_contexts_no_event_processor(isolated_context: contextvars.Context):
    """When event processor is None, EventContext should not be touched."""

    def _test():
        app = App(_state=EmptyState)
        assert app._event_processor is None

        with app.set_contexts():
            assert RegistrationContext.get() is app._registration_context
            with pytest.raises(LookupError):
                EventContext.get()

    isolated_context.run(_test)
