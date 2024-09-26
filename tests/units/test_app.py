from __future__ import annotations

import functools
import io
import json
import os.path
import re
import unittest.mock
import uuid
from contextlib import nullcontext as does_not_raise
from pathlib import Path
from typing import Generator, List, Tuple, Type
from unittest.mock import AsyncMock

import pytest
import sqlmodel
from fastapi import FastAPI, UploadFile
from starlette_admin.auth import AuthProvider
from starlette_admin.contrib.sqla.admin import Admin
from starlette_admin.contrib.sqla.view import ModelView

import reflex as rx
from reflex import AdminDash, constants
from reflex.app import (
    App,
    ComponentCallable,
    OverlayFragment,
    default_overlay_component,
    process,
    upload,
)
from reflex.components import Component
from reflex.components.base.fragment import Fragment
from reflex.components.core.cond import Cond
from reflex.components.radix.themes.typography.text import Text
from reflex.event import Event
from reflex.middleware import HydrateMiddleware
from reflex.model import Model
from reflex.state import (
    BaseState,
    OnLoadInternalState,
    RouterData,
    State,
    StateManagerDisk,
    StateManagerMemory,
    StateManagerRedis,
    StateUpdate,
    _substate_key,
)
from reflex.style import Style
from reflex.utils import exceptions, format
from reflex.vars.base import computed_var

from .conftest import chdir
from .states import (
    ChildFileUploadState,
    FileStateBase1,
    FileUploadState,
    GenState,
    GrandChildFileUploadState,
)


class EmptyState(BaseState):
    """An empty state."""

    pass


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


@pytest.fixture()
def test_state() -> Type[BaseState]:
    """A default state.

    Returns:
        A default state.
    """
    return ATestState


@pytest.fixture()
def redundant_test_state() -> Type[BaseState]:
    """A default state.

    Returns:
        A default state.
    """

    class RedundantTestState(BaseState):
        var: int

    return RedundantTestState


@pytest.fixture(scope="session")
def test_model() -> Type[Model]:
    """A default model.

    Returns:
        A default model.
    """

    class TestModel(Model, table=True):  # type: ignore
        pass

    return TestModel


@pytest.fixture(scope="session")
def test_model_auth() -> Type[Model]:
    """A default model.

    Returns:
        A default model.
    """

    class TestModelAuth(Model, table=True):  # type: ignore
        """A test model with auth."""

        pass

    return TestModelAuth


@pytest.fixture()
def test_get_engine():
    """A default database engine.

    Returns:
        A default database engine.
    """
    enable_admin = True
    url = "sqlite:///test.db"
    return sqlmodel.create_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False} if enable_admin else {},
    )


@pytest.fixture()
def test_custom_auth_admin() -> Type[AuthProvider]:
    """A default auth provider.

    Returns:
        A default default auth provider.
    """

    class TestAuthProvider(AuthProvider):
        """A test auth provider."""

        login_path: str = "/login"
        logout_path: str = "/logout"

        def login(self):
            """Login."""
            pass

        def is_authenticated(self):
            """Is authenticated."""
            pass

        def get_admin_user(self):
            """Get admin user."""
            pass

        def logout(self):
            """Logout."""
            pass

    return TestAuthProvider


def test_default_app(app: App):
    """Test creating an app with no args.

    Args:
        app: The app to test.
    """
    assert app.middleware == [HydrateMiddleware()]
    assert app.style == Style()
    assert app.admin_dash is None


def test_multiple_states_error(monkeypatch, test_state, redundant_test_state):
    """Test that an error is thrown when multiple classes subclass rx.BaseState.

    Args:
        monkeypatch: Pytest monkeypatch object.
        test_state: A test state subclassing rx.BaseState.
        redundant_test_state: Another test state subclassing rx.BaseState.
    """
    monkeypatch.delenv(constants.PYTEST_CURRENT_TEST)
    with pytest.raises(ValueError):
        App()


def test_add_page_default_route(app: App, index_page, about_page):
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
        about_page: The about page.
    """
    assert app.pages == {}
    app.add_page(index_page)
    assert app.pages.keys() == {"index"}
    app.add_page(about_page)
    assert app.pages.keys() == {"index", "about"}


def test_add_page_set_route(app: App, index_page, windows_platform: bool):
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
        windows_platform: Whether the system is windows.
    """
    route = "test" if windows_platform else "/test"
    assert app.pages == {}
    app.add_page(index_page, route=route)
    assert app.pages.keys() == {"test"}


def test_add_page_set_route_dynamic(index_page, windows_platform: bool):
    """Test adding a page with dynamic route variable to an app.

    Args:
        index_page: The index page.
        windows_platform: Whether the system is windows.
    """
    app = App(state=EmptyState)
    assert app.state is not None
    route = "/test/[dynamic]"
    assert app.pages == {}
    app.add_page(index_page, route=route)
    assert app.pages.keys() == {"test/[dynamic]"}
    assert "dynamic" in app.state.computed_vars
    assert app.state.computed_vars["dynamic"]._deps(objclass=EmptyState) == {
        constants.ROUTER
    }
    assert constants.ROUTER in app.state()._computed_var_dependencies


def test_add_page_set_route_nested(app: App, index_page, windows_platform: bool):
    """Test adding a page to an app.

    Args:
        app: The app to test.
        index_page: The index page.
        windows_platform: Whether the system is windows.
    """
    route = "test\\nested" if windows_platform else "/test/nested"
    assert app.pages == {}
    app.add_page(index_page, route=route)
    assert app.pages.keys() == {route.strip(os.path.sep)}


def test_add_page_invalid_api_route(app: App, index_page):
    """Test adding a page with an invalid route to an app.

    Args:
        app: The app to test.
        index_page: The index page.
    """
    with pytest.raises(ValueError):
        app.add_page(index_page, route="api")
    with pytest.raises(ValueError):
        app.add_page(index_page, route="/api")
    with pytest.raises(ValueError):
        app.add_page(index_page, route="/api/")
    with pytest.raises(ValueError):
        app.add_page(index_page, route="api/foo")
    with pytest.raises(ValueError):
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
    "first_page,second_page, route",
    [
        (lambda: rx.fragment(), lambda: rx.fragment(rx.text("second")), "/"),
        (rx.fragment(rx.text("first")), rx.fragment(rx.text("second")), "/page1"),
        (
            lambda: rx.fragment(rx.text("first")),
            rx.fragment(rx.text("second")),
            "page3",
        ),
        (page1, page2, "page1"),
        (index, index, None),
        (page1, page1, None),
    ],
)
def test_add_duplicate_page_route_error(app, first_page, second_page, route):
    app.add_page(first_page, route=route)
    with pytest.raises(ValueError):
        app.add_page(second_page, route="/" + route.strip("/") if route else None)


def test_initialize_with_admin_dashboard(test_model):
    """Test setting the admin dashboard of an app.

    Args:
        test_model: The default model.
    """
    app = App(admin_dash=AdminDash(models=[test_model]))
    assert app.admin_dash is not None
    assert len(app.admin_dash.models) > 0
    assert app.admin_dash.models[0] == test_model


def test_initialize_with_custom_admin_dashboard(
    test_get_engine,
    test_custom_auth_admin,
    test_model_auth,
):
    """Test setting the custom admin dashboard of an app.

    Args:
        test_get_engine: The default database engine.
        test_model_auth: The default model for an auth admin dashboard.
        test_custom_auth_admin: The custom auth provider.
    """
    custom_auth_provider = test_custom_auth_admin()
    custom_admin = Admin(engine=test_get_engine, auth_provider=custom_auth_provider)
    app = App(admin_dash=AdminDash(models=[test_model_auth], admin=custom_admin))
    assert app.admin_dash is not None
    assert app.admin_dash.admin is not None
    assert len(app.admin_dash.models) > 0
    assert app.admin_dash.models[0] == test_model_auth
    assert app.admin_dash.admin.auth_provider == custom_auth_provider


def test_initialize_admin_dashboard_with_view_overrides(test_model):
    """Test setting the admin dashboard of an app with view class overridden.

    Args:
        test_model: The default model.
    """

    class TestModelView(ModelView):
        pass

    app = App(
        admin_dash=AdminDash(
            models=[test_model], view_overrides={test_model: TestModelView}
        )
    )
    assert app.admin_dash is not None
    assert app.admin_dash.models == [test_model]
    assert app.admin_dash.view_overrides[test_model] == TestModelView


@pytest.mark.asyncio
async def test_initialize_with_state(test_state: Type[ATestState], token: str):
    """Test setting the state of an app.

    Args:
        test_state: The default state.
        token: a Token.
    """
    app = App(state=test_state)
    assert app.state == test_state

    # Get a state for a given token.
    state = await app.state_manager.get_state(_substate_key(token, test_state))
    assert isinstance(state, test_state)
    assert state.var == 0  # type: ignore

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.close()


@pytest.mark.asyncio
async def test_set_and_get_state(test_state):
    """Test setting and getting the state of an app with different tokens.

    Args:
        test_state: The default state.
    """
    app = App(state=test_state)

    # Create two tokens.
    token1 = str(uuid.uuid4()) + f"_{test_state.get_full_name()}"
    token2 = str(uuid.uuid4()) + f"_{test_state.get_full_name()}"

    # Get the default state for each token.
    state1 = await app.state_manager.get_state(token1)
    state2 = await app.state_manager.get_state(token2)
    assert state1.var == 0  # type: ignore
    assert state2.var == 0  # type: ignore

    # Set the vars to different values.
    state1.var = 1
    state2.var = 2
    await app.state_manager.set_state(token1, state1)
    await app.state_manager.set_state(token2, state2)

    # Get the states again and check the values.
    state1 = await app.state_manager.get_state(token1)
    state2 = await app.state_manager.get_state(token2)
    assert state1.var == 1  # type: ignore
    assert state2.var == 2  # type: ignore

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.close()


@pytest.mark.asyncio
async def test_dynamic_var_event(test_state: Type[ATestState], token: str):
    """Test that the default handler of a dynamic generated var
    works as expected.

    Args:
        test_state: State Fixture.
        token: a Token.
    """
    state = test_state()  # type: ignore
    state.add_var("int_val", int, 0)
    result = await state._process(
        Event(
            token=token,
            name=f"{test_state.get_name()}.set_int_val",
            router_data={"pathname": "/", "query": {}},
            payload={"value": 50},
        )
    ).__anext__()
    assert result.delta == {test_state.get_name(): {"int_val": 50}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_tuples",
    [
        pytest.param(
            [
                (
                    "make_friend",
                    {"plain_friends": ["Tommy", "another-fd"]},
                ),
                (
                    "change_first_friend",
                    {"plain_friends": ["Jenny", "another-fd"]},
                ),
            ],
            id="append then __setitem__",
        ),
        pytest.param(
            [
                (
                    "unfriend_first_friend",
                    {"plain_friends": []},
                ),
                (
                    "make_friend",
                    {"plain_friends": ["another-fd"]},
                ),
            ],
            id="delitem then append",
        ),
        pytest.param(
            [
                (
                    "make_friends_with_colleagues",
                    {"plain_friends": ["Tommy", "Peter", "Jimmy"]},
                ),
                (
                    "remove_tommy",
                    {"plain_friends": ["Peter", "Jimmy"]},
                ),
                (
                    "remove_last_friend",
                    {"plain_friends": ["Peter"]},
                ),
                (
                    "unfriend_all_friends",
                    {"plain_friends": []},
                ),
            ],
            id="extend, remove, pop, clear",
        ),
        pytest.param(
            [
                (
                    "add_jimmy_to_second_group",
                    {"friends_in_nested_list": [["Tommy"], ["Jenny", "Jimmy"]]},
                ),
                (
                    "remove_first_person_from_first_group",
                    {"friends_in_nested_list": [[], ["Jenny", "Jimmy"]]},
                ),
                (
                    "remove_first_group",
                    {"friends_in_nested_list": [["Jenny", "Jimmy"]]},
                ),
            ],
            id="nested list",
        ),
        pytest.param(
            [
                (
                    "add_jimmy_to_tommy_friends",
                    {"friends_in_dict": {"Tommy": ["Jenny", "Jimmy"]}},
                ),
                (
                    "remove_jenny_from_tommy",
                    {"friends_in_dict": {"Tommy": ["Jimmy"]}},
                ),
                (
                    "tommy_has_no_fds",
                    {"friends_in_dict": {"Tommy": []}},
                ),
            ],
            id="list in dict",
        ),
    ],
)
async def test_list_mutation_detection__plain_list(
    event_tuples: List[Tuple[str, List[str]]],
    list_mutation_state: State,
    token: str,
):
    """Test list mutation detection
    when reassignment is not explicitly included in the logic.

    Args:
        event_tuples: From parametrization.
        list_mutation_state: A state with list mutation features.
        token: a Token.
    """
    for event_name, expected_delta in event_tuples:
        result = await list_mutation_state._process(
            Event(
                token=token,
                name=f"{list_mutation_state.get_name()}.{event_name}",
                router_data={"pathname": "/", "query": {}},
                payload={},
            )
        ).__anext__()

        # prefix keys in expected_delta with the state name
        expected_delta = {list_mutation_state.get_name(): expected_delta}
        assert result.delta == expected_delta


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_tuples",
    [
        pytest.param(
            [
                (
                    "add_age",
                    {"details": {"name": "Tommy", "age": 20}},
                ),
                (
                    "change_name",
                    {"details": {"name": "Jenny", "age": 20}},
                ),
                (
                    "remove_last_detail",
                    {"details": {"name": "Jenny"}},
                ),
            ],
            id="update then __setitem__",
        ),
        pytest.param(
            [
                (
                    "clear_details",
                    {"details": {}},
                ),
                (
                    "add_age",
                    {"details": {"age": 20}},
                ),
            ],
            id="delitem then update",
        ),
        pytest.param(
            [
                (
                    "add_age",
                    {"details": {"name": "Tommy", "age": 20}},
                ),
                (
                    "remove_name",
                    {"details": {"age": 20}},
                ),
                (
                    "pop_out_age",
                    {"details": {}},
                ),
            ],
            id="add, remove, pop",
        ),
        pytest.param(
            [
                (
                    "remove_home_address",
                    {"address": [{}, {"work": "work address"}]},
                ),
                (
                    "add_street_to_home_address",
                    {
                        "address": [
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
                        "friend_in_nested_dict": {
                            "name": "Nikhil",
                            "friend": {"name": "Tommy"},
                        }
                    },
                ),
                (
                    "add_friend_age",
                    {
                        "friend_in_nested_dict": {
                            "name": "Nikhil",
                            "friend": {"name": "Tommy", "age": 30},
                        }
                    },
                ),
                (
                    "remove_friend",
                    {"friend_in_nested_dict": {"name": "Nikhil"}},
                ),
            ],
            id="nested dict",
        ),
    ],
)
async def test_dict_mutation_detection__plain_list(
    event_tuples: List[Tuple[str, List[str]]],
    dict_mutation_state: State,
    token: str,
):
    """Test dict mutation detection
    when reassignment is not explicitly included in the logic.

    Args:
        event_tuples: From parametrization.
        dict_mutation_state: A state with dict mutation features.
        token: a Token.
    """
    for event_name, expected_delta in event_tuples:
        result = await dict_mutation_state._process(
            Event(
                token=token,
                name=f"{dict_mutation_state.get_name()}.{event_name}",
                router_data={"pathname": "/", "query": {}},
                payload={},
            )
        ).__anext__()

        # prefix keys in expected_delta with the state name
        expected_delta = {dict_mutation_state.get_name(): expected_delta}

        assert result.delta == expected_delta


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "delta"),
    [
        (
            FileUploadState,
            {
                FileUploadState.get_full_name(): {
                    "img_list": ["image1.jpg", "image2.jpg"]
                }
            },
        ),
        (
            ChildFileUploadState,
            {
                ChildFileUploadState.get_full_name(): {
                    "img_list": ["image1.jpg", "image2.jpg"]
                }
            },
        ),
        (
            GrandChildFileUploadState,
            {
                GrandChildFileUploadState.get_full_name(): {
                    "img_list": ["image1.jpg", "image2.jpg"]
                }
            },
        ),
    ],
)
async def test_upload_file(tmp_path, state, delta, token: str, mocker):
    """Test that file upload works correctly.

    Args:
        tmp_path: Temporary path.
        state: The state class.
        delta: Expected delta
        token: a Token.
        mocker: pytest mocker object.
    """
    mocker.patch(
        "reflex.state.State.class_subclasses",
        {state if state is FileUploadState else FileStateBase1},
    )
    state._tmp_path = tmp_path
    # The App state must be the "root" of the state tree
    app = App(state=State)
    app.event_namespace.emit = AsyncMock()  # type: ignore
    current_state = await app.state_manager.get_state(_substate_key(token, state))
    data = b"This is binary data"

    # Create a binary IO object and write data to it
    bio = io.BytesIO()
    bio.write(data)

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{state.get_full_name()}.multi_handle_upload",
    }

    file1 = UploadFile(
        filename=f"image1.jpg",
        file=bio,
    )
    file2 = UploadFile(
        filename=f"image2.jpg",
        file=bio,
    )
    upload_fn = upload(app)
    streaming_response = await upload_fn(request_mock, [file1, file2])
    async for state_update in streaming_response.body_iterator:
        assert (
            state_update
            == StateUpdate(delta=delta, events=[], final=True).json() + "\n"
        )

    current_state = await app.state_manager.get_state(_substate_key(token, state))
    state_dict = current_state.dict()[state.get_full_name()]
    assert state_dict["img_list"] == [
        "image1.jpg",
        "image2.jpg",
    ]

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [FileUploadState, ChildFileUploadState, GrandChildFileUploadState],
)
async def test_upload_file_without_annotation(state, tmp_path, token):
    """Test that an error is thrown when there's no param annotated with rx.UploadFile or List[UploadFile].

    Args:
        state: The state class.
        tmp_path: Temporary path.
        token: a Token.
    """
    state._tmp_path = tmp_path
    app = App(state=State)

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{state.get_full_name()}.handle_upload2",
    }
    file_mock = unittest.mock.Mock(filename="image1.jpg")
    fn = upload(app)
    with pytest.raises(ValueError) as err:
        await fn(request_mock, [file_mock])
    assert (
        err.value.args[0]
        == f"`{state.get_full_name()}.handle_upload2` handler should have a parameter annotated as List[rx.UploadFile]"
    )

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state",
    [FileUploadState, ChildFileUploadState, GrandChildFileUploadState],
)
async def test_upload_file_background(state, tmp_path, token):
    """Test that an error is thrown handler is a background task.

    Args:
        state: The state class.
        tmp_path: Temporary path.
        token: a Token.
    """
    state._tmp_path = tmp_path
    app = App(state=State)

    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{state.get_full_name()}.bg_upload",
    }
    file_mock = unittest.mock.Mock(filename="image1.jpg")
    fn = upload(app)
    with pytest.raises(TypeError) as err:
        await fn(request_mock, [file_mock])
    assert (
        err.value.args[0]
        == f"@rx.background is not supported for upload handler `{state.get_full_name()}.bg_upload`."
    )

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.close()


class DynamicState(BaseState):
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

    # side_effect_counter: int = 0

    def on_load(self):
        """Event handler for page on_load, should trigger for all navigation events."""
        self.loaded = self.loaded + 1

    def on_counter(self):
        """Increment the counter var."""
        self.counter = self.counter + 1

    @computed_var(cache=True)
    def comp_dynamic(self) -> str:
        """A computed var that depends on the dynamic var.

        Returns:
            same as self.dynamic
        """
        # self.side_effect_counter = self.side_effect_counter + 1
        return self.dynamic

    on_load_internal = OnLoadInternalState.on_load_internal.fn


def test_dynamic_arg_shadow(
    index_page: ComponentCallable,
    windows_platform: bool,
    token: str,
    app_module_mock: unittest.mock.Mock,
    mocker,
):
    """Create app with dynamic route var and try to add a page with a dynamic arg that shadows a state var.

    Args:
        index_page: The index page.
        windows_platform: Whether the system is windows.
        token: a Token.
        app_module_mock: Mocked app module.
        mocker: pytest mocker object.
    """
    arg_name = "counter"
    route = f"/test/[{arg_name}]"
    app = app_module_mock.app = App(state=DynamicState)
    assert app.state is not None
    with pytest.raises(NameError):
        app.add_page(index_page, route=route, on_load=DynamicState.on_load)  # type: ignore


def test_multiple_dynamic_args(
    index_page: ComponentCallable,
    windows_platform: bool,
    token: str,
    app_module_mock: unittest.mock.Mock,
    mocker,
):
    """Create app with multiple dynamic route vars with the same name.

    Args:
        index_page: The index page.
        windows_platform: Whether the system is windows.
        token: a Token.
        app_module_mock: Mocked app module.
        mocker: pytest mocker object.
    """
    arg_name = "my_arg"
    route = f"/test/[{arg_name}]"
    route2 = f"/test2/[{arg_name}]"
    app = app_module_mock.app = App(state=EmptyState)
    app.add_page(index_page, route=route)
    app.add_page(index_page, route=route2)


@pytest.mark.asyncio
async def test_dynamic_route_var_route_change_completed_on_load(
    index_page: ComponentCallable,
    windows_platform: bool,
    token: str,
    app_module_mock: unittest.mock.Mock,
    mocker,
):
    """Create app with dynamic route var, and simulate navigation.

    on_load should fire, allowing any additional vars to be updated before the
    initial page hydrate.

    Args:
        index_page: The index page.
        windows_platform: Whether the system is windows.
        token: a Token.
        app_module_mock: Mocked app module.
        mocker: pytest mocker object.
    """
    arg_name = "dynamic"
    route = f"/test/[{arg_name}]"
    app = app_module_mock.app = App(state=DynamicState)
    assert app.state is not None
    assert arg_name not in app.state.vars
    app.add_page(index_page, route=route, on_load=DynamicState.on_load)  # type: ignore
    assert arg_name in app.state.vars
    assert arg_name in app.state.computed_vars
    assert app.state.computed_vars[arg_name]._deps(objclass=DynamicState) == {
        constants.ROUTER
    }
    assert constants.ROUTER in app.state()._computed_var_dependencies

    substate_token = _substate_key(token, DynamicState)
    sid = "mock_sid"
    client_ip = "127.0.0.1"
    state = await app.state_manager.get_state(substate_token)
    assert state.dynamic == ""
    exp_vals = ["foo", "foobar", "baz"]

    def _event(name, val, **kwargs):
        return Event(
            token=kwargs.pop("token", token),
            name=name,
            router_data=kwargs.pop(
                "router_data", {"pathname": route, "query": {arg_name: val}}
            ),
            payload=kwargs.pop("payload", {}),
            **kwargs,
        )

    def _dynamic_state_event(name, val, **kwargs):
        return _event(
            name=format.format_event_handler(getattr(DynamicState, name)),  # type: ignore
            val=val,
            **kwargs,
        )

    prev_exp_val = ""
    for exp_index, exp_val in enumerate(exp_vals):
        on_load_internal = _event(
            name=f"{state.get_full_name()}.{constants.CompileVars.ON_LOAD_INTERNAL.rpartition('.')[2]}",
            val=exp_val,
        )
        exp_router_data = {
            "headers": {},
            "ip": client_ip,
            "sid": sid,
            "token": token,
            **on_load_internal.router_data,
        }
        exp_router = RouterData(exp_router_data)
        process_coro = process(
            app,
            event=on_load_internal,
            sid=sid,
            headers={},
            client_ip=client_ip,
        )
        update = await process_coro.__anext__()
        # route change (on_load_internal) triggers: [call on_load events, call set_is_hydrated(True)]
        assert update == StateUpdate(
            delta={
                state.get_name(): {
                    arg_name: exp_val,
                    f"comp_{arg_name}": exp_val,
                    constants.CompileVars.IS_HYDRATED: False,
                    # "side_effect_counter": exp_index,
                    "router": exp_router,
                }
            },
            events=[
                _dynamic_state_event(
                    name="on_load",
                    val=exp_val,
                ),
                _event(
                    name=f"{State.get_name()}.set_is_hydrated",
                    payload={"value": True},
                    val=exp_val,
                    router_data={},
                ),
            ],
        )
        if isinstance(app.state_manager, StateManagerRedis):
            # When redis is used, the state is not updated until the processing is complete
            state = await app.state_manager.get_state(substate_token)
            assert state.dynamic == prev_exp_val

        # complete the processing
        with pytest.raises(StopAsyncIteration):
            await process_coro.__anext__()

        # check that router data was written to the state_manager store
        state = await app.state_manager.get_state(substate_token)
        assert state.dynamic == exp_val

        process_coro = process(
            app,
            event=_dynamic_state_event(name="on_load", val=exp_val),
            sid=sid,
            headers={},
            client_ip=client_ip,
        )
        on_load_update = await process_coro.__anext__()
        assert on_load_update == StateUpdate(
            delta={
                state.get_name(): {
                    "loaded": exp_index + 1,
                },
            },
            events=[],
        )
        # complete the processing
        with pytest.raises(StopAsyncIteration):
            await process_coro.__anext__()
        process_coro = process(
            app,
            event=_dynamic_state_event(
                name="set_is_hydrated", payload={"value": True}, val=exp_val
            ),
            sid=sid,
            headers={},
            client_ip=client_ip,
        )
        on_set_is_hydrated_update = await process_coro.__anext__()
        assert on_set_is_hydrated_update == StateUpdate(
            delta={
                state.get_name(): {
                    "is_hydrated": True,
                },
            },
            events=[],
        )
        # complete the processing
        with pytest.raises(StopAsyncIteration):
            await process_coro.__anext__()

        # a simple state update event should NOT trigger on_load or route var side effects
        process_coro = process(
            app,
            event=_dynamic_state_event(name="on_counter", val=exp_val),
            sid=sid,
            headers={},
            client_ip=client_ip,
        )
        update = await process_coro.__anext__()
        assert update == StateUpdate(
            delta={
                state.get_name(): {
                    "counter": exp_index + 1,
                }
            },
            events=[],
        )
        # complete the processing
        with pytest.raises(StopAsyncIteration):
            await process_coro.__anext__()

        prev_exp_val = exp_val
    state = await app.state_manager.get_state(substate_token)
    assert state.loaded == len(exp_vals)
    assert state.counter == len(exp_vals)
    # print(f"Expected {exp_vals} rendering side effects, got {state.side_effect_counter}")
    # assert state.side_effect_counter == len(exp_vals)

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.close()


@pytest.mark.asyncio
async def test_process_events(mocker, token: str):
    """Test that an event is processed properly and that it is postprocessed
    n+1 times. Also check that the processing flag of the last stateupdate is set to
    False.

    Args:
        mocker: mocker object.
        token: a Token.
    """
    router_data = {
        "pathname": "/",
        "query": {},
        "token": token,
        "sid": "mock_sid",
        "headers": {},
        "ip": "127.0.0.1",
    }
    app = App(state=GenState)
    mocker.patch.object(app, "_postprocess", AsyncMock())
    event = Event(
        token=token,
        name=f"{GenState.get_name()}.go",
        payload={"c": 5},
        router_data=router_data,
    )

    async for _update in process(app, event, "mock_sid", {}, "127.0.0.1"):
        pass

    assert (await app.state_manager.get_state(event.substate_token)).value == 5
    assert app._postprocess.call_count == 6

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.close()


@pytest.mark.parametrize(
    ("state", "overlay_component", "exp_page_child"),
    [
        (None, default_overlay_component, None),
        (None, None, None),
        (None, Text.create("foo"), Text),
        (State, default_overlay_component, Fragment),
        (State, None, None),
        (State, Text.create("foo"), Text),
        (State, lambda: Text.create("foo"), Text),
    ],
)
def test_overlay_component(
    state: State | None,
    overlay_component: Component | ComponentCallable | None,
    exp_page_child: Type[Component] | None,
):
    """Test that the overlay component is set correctly.

    Args:
        state: The state class to pass to App.
        overlay_component: The overlay_component to pass to App.
        exp_page_child: The type of the expected child in the page fragment.
    """
    app = App(state=state, overlay_component=overlay_component)
    app._setup_overlay_component()
    if exp_page_child is None:
        assert app.overlay_component is None
    elif isinstance(exp_page_child, OverlayFragment):
        assert app.overlay_component is not None
        generated_component = app._generate_component(app.overlay_component)  # type: ignore
        assert isinstance(generated_component, OverlayFragment)
        assert isinstance(
            generated_component.children[0],
            Cond,  # ConnectionModal is a Cond under the hood
        )
    else:
        assert app.overlay_component is not None
        assert isinstance(
            app._generate_component(app.overlay_component),  # type: ignore
            exp_page_child,
        )

    app.add_page(rx.box("Index"), route="/test")
    # overlay components are wrapped during compile only
    app._setup_overlay_component()
    page = app.pages["test"]

    if exp_page_child is not None:
        assert len(page.children) == 3
        children_types = (type(child) for child in page.children)
        assert exp_page_child in children_types
    else:
        assert len(page.children) == 2


@pytest.fixture
def compilable_app(tmp_path) -> Generator[tuple[App, Path], None, None]:
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
    app = App(theme=None)
    app._get_frontend_packages = unittest.mock.Mock()
    with chdir(app_path):
        yield app, web_dir


def test_app_wrap_compile_theme(compilable_app: tuple[App, Path]):
    """Test that the radix theme component wraps the app.

    Args:
        compilable_app: compilable_app fixture.
    """
    app, web_dir = compilable_app
    app.theme = rx.theme(accent_color="plum")
    app._compile()
    app_js_contents = (web_dir / "pages" / "_app.js").read_text()
    app_js_lines = [
        line.strip() for line in app_js_contents.splitlines() if line.strip()
    ]
    assert (
        "function AppWrap({children}) {"
        "return ("
        "<RadixThemesColorModeProvider>"
        "<RadixThemesTheme accentColor={\"plum\"} css={{...theme.styles.global[':root'], ...theme.styles.global.body}}>"
        "<Fragment>"
        "{children}"
        "</Fragment>"
        "</RadixThemesTheme>"
        "</RadixThemesColorModeProvider>"
        ")"
        "}"
    ) in "".join(app_js_lines)


def test_app_wrap_priority(compilable_app: tuple[App, Path]):
    """Test that the app wrap components are wrapped in the correct order.

    Args:
        compilable_app: compilable_app fixture.
    """
    app, web_dir = compilable_app

    class Fragment1(Component):
        tag = "Fragment1"

        def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
            return {(99, "Box"): rx.box()}

    class Fragment2(Component):
        tag = "Fragment2"

        def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
            return {(50, "Text"): rx.text()}

    class Fragment3(Component):
        tag = "Fragment3"

        def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
            return {(10, "Fragment2"): Fragment2.create()}

    def page():
        return Fragment1.create(Fragment3.create())

    app.add_page(page)
    app._compile()
    app_js_contents = (web_dir / "pages" / "_app.js").read_text()
    app_js_lines = [
        line.strip() for line in app_js_contents.splitlines() if line.strip()
    ]
    assert (
        "function AppWrap({children}) {"
        "return ("
        "<RadixThemesBox>"
        '<RadixThemesText as={"p"}>'
        "<RadixThemesColorModeProvider>"
        "<Fragment2>"
        "<Fragment>"
        "{children}"
        "</Fragment>"
        "</Fragment2>"
        "</RadixThemesColorModeProvider>"
        "</RadixThemesText>"
        "</RadixThemesBox>"
        ")"
        "}"
    ) in "".join(app_js_lines)


def test_app_state_determination():
    """Test that the stateless status of an app is determined correctly."""
    a1 = App()
    assert a1.state is None

    # No state, no router, no event handlers.
    a1.add_page(rx.box("Index"), route="/")
    assert a1.state is None

    # Add a page with `on_load` enables state.
    a1.add_page(rx.box("About"), route="/about", on_load=rx.console_log(""))
    assert a1.state is not None

    a2 = App()
    assert a2.state is None

    # Referencing a state Var enables state.
    a2.add_page(rx.box(rx.text(GenState.value)), route="/")
    assert a2.state is not None

    a3 = App()
    assert a3.state is None

    # Referencing router enables state.
    a3.add_page(rx.box(rx.text(State.router.page.full_path)), route="/")
    assert a3.state is not None

    a4 = App()
    assert a4.state is None

    a4.add_page(rx.box(rx.button("Click", on_click=rx.console_log(""))), route="/")
    assert a4.state is None

    a4.add_page(
        rx.box(rx.button("Click", on_click=DynamicState.on_counter)), route="/page2"
    )
    assert a4.state is not None


# for coverage
def test_raise_on_connect_error():
    """Test that the connect_error function is called."""
    with pytest.raises(ValueError):
        App(connect_error_component="Foo")


def test_raise_on_state():
    """Test that the state is set."""
    # state kwargs is deprecated, we just make sure the app is created anyway.
    _app = App(state=State)
    assert _app.state is not None
    assert issubclass(_app.state, State)


def test_call_app():
    """Test that the app can be called."""
    app = App()
    api = app()
    assert isinstance(api, FastAPI)


def test_app_with_optional_endpoints():
    from reflex.components.core.upload import Upload

    app = App()
    Upload.is_used = True
    app._add_optional_endpoints()
    # TODO: verify the availability of the endpoints in app.api


def test_app_state_manager():
    app = App()
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

    comp = App._generate_component(index)  # type: ignore
    assert isinstance(comp, Component)

    with pytest.raises(exceptions.MatchTypeError):
        App._generate_component(index_mismatch)  # type: ignore


def test_add_page_component_returning_tuple():
    """Test that a component or render method returning a
    tuple is unpacked in a Fragment.
    """
    app = App()

    def index():
        return rx.text("first"), rx.text("second")

    def page2():
        return (rx.text("third"),)

    app.add_page(index)  # type: ignore
    app.add_page(page2)  # type: ignore

    assert isinstance((fragment_wrapper := app.pages["index"].children[0]), Fragment)
    assert isinstance((first_text := fragment_wrapper.children[0]), Text)
    assert str(first_text.children[0].contents) == '"first"'  # type: ignore
    assert isinstance((second_text := fragment_wrapper.children[1]), Text)
    assert str(second_text.children[0].contents) == '"second"'  # type: ignore

    # Test page with trailing comma.
    assert isinstance(
        (page2_fragment_wrapper := app.pages["page2"].children[0]), Fragment
    )
    assert isinstance((third_text := page2_fragment_wrapper.children[0]), Text)
    assert str(third_text.children[0].contents) == '"third"'  # type: ignore


@pytest.mark.parametrize("export", (True, False))
def test_app_with_transpile_packages(compilable_app: tuple[App, Path], export: bool):
    class C1(rx.Component):
        library = "foo@1.2.3"
        tag = "Foo"
        transpile_packages: List[str] = ["foo"]

    class C2(rx.Component):
        library = "bar@4.5.6"
        tag = "Bar"
        transpile_packages: List[str] = ["bar@4.5.6"]

    class C3(rx.NoSSRComponent):
        library = "baz@7.8.10"
        tag = "Baz"
        transpile_packages: List[str] = ["baz@7.8.9"]

    class C4(rx.NoSSRComponent):
        library = "quuc@2.3.4"
        tag = "Quuc"
        transpile_packages: List[str] = ["quuc"]

    class C5(rx.Component):
        library = "quuc"
        tag = "Quuc"

    app, web_dir = compilable_app
    page = Fragment.create(
        C1.create(), C2.create(), C3.create(), C4.create(), C5.create()
    )
    app.add_page(page, route="/")
    app._compile(export=export)

    next_config = (web_dir / "next.config.js").read_text()
    transpile_packages_match = re.search(r"transpilePackages: (\[.*?\])", next_config)
    transpile_packages_json = transpile_packages_match.group(1)  # type: ignore
    transpile_packages = sorted(json.loads(transpile_packages_json))

    assert transpile_packages == [
        "bar",
        "foo",
        "quuc",
    ]

    if export:
        assert 'output: "export"' in next_config
        assert f'distDir: "{constants.Dirs.STATIC}"' in next_config
    else:
        assert 'output: "export"' not in next_config
        assert f'distDir: "{constants.Dirs.STATIC}"' not in next_config


def test_app_with_valid_var_dependencies(compilable_app: tuple[App, Path]):
    app, _ = compilable_app

    class ValidDepState(BaseState):
        base: int = 0
        _backend: int = 0

        @computed_var(cache=True)
        def foo(self) -> str:
            return "foo"

        @computed_var(deps=["_backend", "base", foo], cache=True)
        def bar(self) -> str:
            return "bar"

    app.state = ValidDepState
    app._compile()


def test_app_with_invalid_var_dependencies(compilable_app: tuple[App, Path]):
    app, _ = compilable_app

    class InvalidDepState(BaseState):
        @computed_var(deps=["foolksjdf"], cache=True)
        def bar(self) -> str:
            return "bar"

    app.state = InvalidDepState
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
    "handler_fn, expected",
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
    "handler_fn, expected",
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
