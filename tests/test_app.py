from __future__ import annotations

import io
import os.path
import unittest.mock
import uuid
from pathlib import Path
from typing import Generator, List, Tuple, Type
from unittest.mock import AsyncMock

import pytest
import sqlmodel
from fastapi import UploadFile
from starlette_admin.auth import AuthProvider
from starlette_admin.contrib.sqla.admin import Admin
from starlette_admin.contrib.sqla.view import ModelView

import reflex.components.radix.themes as rdxt
from reflex import AdminDash, constants
from reflex.app import (
    App,
    ComponentCallable,
    default_overlay_component,
    process,
    upload,
)
from reflex.components import Box, Component, Cond, Fragment, Text
from reflex.event import Event, get_hydrate_event
from reflex.middleware import HydrateMiddleware
from reflex.model import Model
from reflex.state import BaseState, RouterData, State, StateManagerRedis, StateUpdate
from reflex.style import Style
from reflex.utils import format
from reflex.vars import ComputedVar

from .conftest import chdir
from .states import (
    ChildFileUploadState,
    FileStateBase1,
    FileStateBase2,
    FileUploadState,
    GenState,
    GrandChildFileUploadState,
)


class EmptyState(BaseState):
    """An empty state."""

    pass


@pytest.fixture
def index_page():
    """An index page.

    Returns:
        The index page.
    """

    def index():
        return Box.create("Index")

    return index


@pytest.fixture
def about_page():
    """An about page.

    Returns:
        The about page.
    """

    def about():
        return Box.create("About")

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
    assert set(app.pages.keys()) == {"index"}
    app.add_page(about_page)
    assert set(app.pages.keys()) == {"index", "about"}


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
    assert set(app.pages.keys()) == {"test"}


def test_add_page_set_route_dynamic(index_page, windows_platform: bool):
    """Test adding a page with dynamic route variable to an app.

    Args:
        index_page: The index page.
        windows_platform: Whether the system is windows.
    """
    app = App(state=EmptyState)
    route = "/test/[dynamic]"
    if windows_platform:
        route.lstrip("/").replace("/", "\\")
    assert app.pages == {}
    app.add_page(index_page, route=route)
    assert set(app.pages.keys()) == {"test/[dynamic]"}
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
    assert set(app.pages.keys()) == {route.strip(os.path.sep)}


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
    custom_admin = Admin(engine=test_get_engine, auth_provider=test_custom_auth_admin)
    app = App(admin_dash=AdminDash(models=[test_model_auth], admin=custom_admin))
    assert app.admin_dash is not None
    assert app.admin_dash.admin is not None
    assert len(app.admin_dash.models) > 0
    assert app.admin_dash.models[0] == test_model_auth
    assert app.admin_dash.admin.auth_provider == test_custom_auth_admin


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
    state = await app.state_manager.get_state(token)
    assert isinstance(state, test_state)
    assert state.var == 0  # type: ignore

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.redis.close()


@pytest.mark.asyncio
async def test_set_and_get_state(test_state):
    """Test setting and getting the state of an app with different tokens.

    Args:
        test_state: The default state.
    """
    app = App(state=test_state)

    # Create two tokens.
    token1 = str(uuid.uuid4())
    token2 = str(uuid.uuid4())

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
        await app.state_manager.redis.close()


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
                    "list_mutation_test_state.make_friend",
                    {
                        "list_mutation_test_state": {
                            "plain_friends": ["Tommy", "another-fd"]
                        }
                    },
                ),
                (
                    "list_mutation_test_state.change_first_friend",
                    {
                        "list_mutation_test_state": {
                            "plain_friends": ["Jenny", "another-fd"]
                        }
                    },
                ),
            ],
            id="append then __setitem__",
        ),
        pytest.param(
            [
                (
                    "list_mutation_test_state.unfriend_first_friend",
                    {"list_mutation_test_state": {"plain_friends": []}},
                ),
                (
                    "list_mutation_test_state.make_friend",
                    {"list_mutation_test_state": {"plain_friends": ["another-fd"]}},
                ),
            ],
            id="delitem then append",
        ),
        pytest.param(
            [
                (
                    "list_mutation_test_state.make_friends_with_colleagues",
                    {
                        "list_mutation_test_state": {
                            "plain_friends": ["Tommy", "Peter", "Jimmy"]
                        }
                    },
                ),
                (
                    "list_mutation_test_state.remove_tommy",
                    {"list_mutation_test_state": {"plain_friends": ["Peter", "Jimmy"]}},
                ),
                (
                    "list_mutation_test_state.remove_last_friend",
                    {"list_mutation_test_state": {"plain_friends": ["Peter"]}},
                ),
                (
                    "list_mutation_test_state.unfriend_all_friends",
                    {"list_mutation_test_state": {"plain_friends": []}},
                ),
            ],
            id="extend, remove, pop, clear",
        ),
        pytest.param(
            [
                (
                    "list_mutation_test_state.add_jimmy_to_second_group",
                    {
                        "list_mutation_test_state": {
                            "friends_in_nested_list": [["Tommy"], ["Jenny", "Jimmy"]]
                        }
                    },
                ),
                (
                    "list_mutation_test_state.remove_first_person_from_first_group",
                    {
                        "list_mutation_test_state": {
                            "friends_in_nested_list": [[], ["Jenny", "Jimmy"]]
                        }
                    },
                ),
                (
                    "list_mutation_test_state.remove_first_group",
                    {
                        "list_mutation_test_state": {
                            "friends_in_nested_list": [["Jenny", "Jimmy"]]
                        }
                    },
                ),
            ],
            id="nested list",
        ),
        pytest.param(
            [
                (
                    "list_mutation_test_state.add_jimmy_to_tommy_friends",
                    {
                        "list_mutation_test_state": {
                            "friends_in_dict": {"Tommy": ["Jenny", "Jimmy"]}
                        }
                    },
                ),
                (
                    "list_mutation_test_state.remove_jenny_from_tommy",
                    {
                        "list_mutation_test_state": {
                            "friends_in_dict": {"Tommy": ["Jimmy"]}
                        }
                    },
                ),
                (
                    "list_mutation_test_state.tommy_has_no_fds",
                    {"list_mutation_test_state": {"friends_in_dict": {"Tommy": []}}},
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
                name=event_name,
                router_data={"pathname": "/", "query": {}},
                payload={},
            )
        ).__anext__()

        assert result.delta == expected_delta


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_tuples",
    [
        pytest.param(
            [
                (
                    "dict_mutation_test_state.add_age",
                    {
                        "dict_mutation_test_state": {
                            "details": {"name": "Tommy", "age": 20}
                        }
                    },
                ),
                (
                    "dict_mutation_test_state.change_name",
                    {
                        "dict_mutation_test_state": {
                            "details": {"name": "Jenny", "age": 20}
                        }
                    },
                ),
                (
                    "dict_mutation_test_state.remove_last_detail",
                    {"dict_mutation_test_state": {"details": {"name": "Jenny"}}},
                ),
            ],
            id="update then __setitem__",
        ),
        pytest.param(
            [
                (
                    "dict_mutation_test_state.clear_details",
                    {"dict_mutation_test_state": {"details": {}}},
                ),
                (
                    "dict_mutation_test_state.add_age",
                    {"dict_mutation_test_state": {"details": {"age": 20}}},
                ),
            ],
            id="delitem then update",
        ),
        pytest.param(
            [
                (
                    "dict_mutation_test_state.add_age",
                    {
                        "dict_mutation_test_state": {
                            "details": {"name": "Tommy", "age": 20}
                        }
                    },
                ),
                (
                    "dict_mutation_test_state.remove_name",
                    {"dict_mutation_test_state": {"details": {"age": 20}}},
                ),
                (
                    "dict_mutation_test_state.pop_out_age",
                    {"dict_mutation_test_state": {"details": {}}},
                ),
            ],
            id="add, remove, pop",
        ),
        pytest.param(
            [
                (
                    "dict_mutation_test_state.remove_home_address",
                    {
                        "dict_mutation_test_state": {
                            "address": [{}, {"work": "work address"}]
                        }
                    },
                ),
                (
                    "dict_mutation_test_state.add_street_to_home_address",
                    {
                        "dict_mutation_test_state": {
                            "address": [
                                {"street": "street address"},
                                {"work": "work address"},
                            ]
                        }
                    },
                ),
            ],
            id="dict in list",
        ),
        pytest.param(
            [
                (
                    "dict_mutation_test_state.change_friend_name",
                    {
                        "dict_mutation_test_state": {
                            "friend_in_nested_dict": {
                                "name": "Nikhil",
                                "friend": {"name": "Tommy"},
                            }
                        }
                    },
                ),
                (
                    "dict_mutation_test_state.add_friend_age",
                    {
                        "dict_mutation_test_state": {
                            "friend_in_nested_dict": {
                                "name": "Nikhil",
                                "friend": {"name": "Tommy", "age": 30},
                            }
                        }
                    },
                ),
                (
                    "dict_mutation_test_state.remove_friend",
                    {
                        "dict_mutation_test_state": {
                            "friend_in_nested_dict": {"name": "Nikhil"}
                        }
                    },
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
                name=event_name,
                router_data={"pathname": "/", "query": {}},
                payload={},
            )
        ).__anext__()

        assert result.delta == expected_delta


# @pytest.mark.asyncio
# @pytest.mark.parametrize(
#     ("state", "delta"),
#     [
#         (
#             FileUploadState,
#             {"file_upload_state": {"img_list": ["image1.jpg", "image2.jpg"]}},
#         ),
#         (
#             ChildFileUploadState,
#             {
#                 "file_state_base1.child_file_upload_state": {
#                     "img_list": ["image1.jpg", "image2.jpg"]
#                 }
#             },
#         ),
#         (
#             GrandChildFileUploadState,
#             {
#                 "file_state_base1.file_state_base2.grand_child_file_upload_state": {
#                     "img_list": ["image1.jpg", "image2.jpg"]
#                 }
#             },
#         ),
#     ],
# )
# async def test_upload_file(tmp_path, state, delta, token: str):
#     """Test that file upload works correctly.
#
#     Args:
#         tmp_path: Temporary path.
#         state: The state class.
#         delta: Expected delta
#         token: a Token.
#     """
#     state._tmp_path = tmp_path
#     # The App state must be the "root" of the state tree
#     app = App(state=state if state is FileUploadState else FileStateBase1)
#     app.event_namespace.emit = AsyncMock()  # type: ignore
#     current_state = await app.state_manager.get_state(token)
#     data = b"This is binary data"
#
#     # Create a binary IO object and write data to it
#     bio = io.BytesIO()
#     bio.write(data)
#
#     state_name = state.get_full_name().partition(".")[2] or state.get_name()
#     request_mock = unittest.mock.Mock()
#     request_mock.headers = {
#         "reflex-client-token": token,
#         "reflex-event-handler": f"{state_name}.multi_handle_upload",
#     }
#
#     file1 = UploadFile(
#         filename=f"image1.jpg",
#         file=bio,
#     )
#     file2 = UploadFile(
#         filename=f"image2.jpg",
#         file=bio,
#     )
#     upload_fn = upload(app)
#     streaming_response = await upload_fn(request_mock, [file1, file2])
#     async for state_update in streaming_response.body_iterator:
#         assert (
#             state_update
#             == StateUpdate(delta=delta, events=[], final=True).json() + "\n"
#         )
#
#     current_state = await app.state_manager.get_state(token)
#     state_dict = current_state.dict()
#     for substate in state.get_full_name().split(".")[1:]:
#         state_dict = state_dict[substate]
#     assert state_dict["img_list"] == [
#         "image1.jpg",
#         "image2.jpg",
#     ]
#
#     if isinstance(app.state_manager, StateManagerRedis):
#         await app.state_manager.redis.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "delta"),
    [
        (
            FileUploadState,
            {"state.file_upload_state": {"img_list": ["image1.jpg", "image2.jpg"]}},
        ),
        (
            ChildFileUploadState,
            {
                "state.file_state_base1.child_file_upload_state": {
                    "img_list": ["image1.jpg", "image2.jpg"]
                }
            },
        ),
        (
            GrandChildFileUploadState,
            {
                "state.file_state_base1.file_state_base2.grand_child_file_upload_state": {
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
    class_subclasses = {
        State: {state if state is FileUploadState else FileStateBase1},
        FileUploadState: set(),
        FileStateBase1: {ChildFileUploadState, FileStateBase2},
        FileStateBase2: {GrandChildFileUploadState},
        GrandChildFileUploadState: set(),
        ChildFileUploadState: set(),
    }

    mocker.patch("reflex.state.State.class_subclasses", class_subclasses)
    state._tmp_path = tmp_path
    # The App state must be the "root" of the state tree
    app = App(state=State)
    app.event_namespace.emit = AsyncMock()  # type: ignore
    current_state = await app.state_manager.get_state(token)
    data = b"This is binary data"

    # Create a binary IO object and write data to it
    bio = io.BytesIO()
    bio.write(data)

    state_name = state.get_full_name().partition(".")[2] or state.get_name()
    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"state.{state_name}.multi_handle_upload",
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

    current_state = await app.state_manager.get_state(token)
    state_dict = current_state.dict()[state.get_full_name()]
    assert state_dict["img_list"] == [
        "image1.jpg",
        "image2.jpg",
    ]

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.redis.close()


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
    # The App state must be the "root" of the state tree
    app = App(state=state if state is FileUploadState else FileStateBase1)

    state_name = state.get_full_name().partition(".")[2] or state.get_name()
    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{state_name}.handle_upload2",
    }
    file_mock = unittest.mock.Mock(filename="image1.jpg")
    fn = upload(app)
    with pytest.raises(ValueError) as err:
        await fn(request_mock, [file_mock])
    assert (
        err.value.args[0]
        == f"`{state_name}.handle_upload2` handler should have a parameter annotated as List[rx.UploadFile]"
    )

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.redis.close()


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
    # The App state must be the "root" of the state tree
    app = App(state=state if state is FileUploadState else FileStateBase1)

    state_name = state.get_full_name().partition(".")[2] or state.get_name()
    request_mock = unittest.mock.Mock()
    request_mock.headers = {
        "reflex-client-token": token,
        "reflex-event-handler": f"{state_name}.bg_upload",
    }
    file_mock = unittest.mock.Mock(filename="image1.jpg")
    fn = upload(app)
    with pytest.raises(TypeError) as err:
        await fn(request_mock, [file_mock])
    assert (
        err.value.args[0]
        == f"@rx.background is not supported for upload handler `{state_name}.bg_upload`."
    )

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.redis.close()


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

    loaded: int = 0
    counter: int = 0

    # side_effect_counter: int = 0

    def on_load(self):
        """Event handler for page on_load, should trigger for all navigation events."""
        self.loaded = self.loaded + 1

    def on_counter(self):
        """Increment the counter var."""
        self.counter = self.counter + 1

    @ComputedVar
    def comp_dynamic(self) -> str:
        """A computed var that depends on the dynamic var.

        Returns:
            same as self.dynamic
        """
        # self.side_effect_counter = self.side_effect_counter + 1
        return self.dynamic


@pytest.mark.asyncio
async def test_dynamic_route_var_route_change_completed_on_load(
    index_page, windows_platform: bool, token: str, mocker
):
    """Create app with dynamic route var, and simulate navigation.

    on_load should fire, allowing any additional vars to be updated before the
    initial page hydrate.

    Args:
        index_page: The index page.
        windows_platform: Whether the system is windows.
        token: a Token.
        mocker: pytest mocker object.
    """
    class_subclasses = {State: {DynamicState}}
    mocker.patch("reflex.state.State.class_subclasses", class_subclasses)
    DynamicState.add_var(
        constants.CompileVars.IS_HYDRATED, type_=bool, default_value=False
    )
    arg_name = "dynamic"
    route = f"/test/[{arg_name}]"
    if windows_platform:
        route.lstrip("/").replace("/", "\\")
    app = App(state=DynamicState)
    assert arg_name not in app.state.vars
    app.add_page(index_page, route=route, on_load=DynamicState.on_load)  # type: ignore
    assert arg_name in app.state.vars
    assert arg_name in app.state.computed_vars
    assert app.state.computed_vars[arg_name]._deps(objclass=DynamicState) == {
        constants.ROUTER
    }
    assert constants.ROUTER in app.state()._computed_var_dependencies

    sid = "mock_sid"
    client_ip = "127.0.0.1"
    state = await app.state_manager.get_state(token)
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
        hydrate_event = _event(name=get_hydrate_event(state), val=exp_val)
        exp_router_data = {
            "headers": {},
            "ip": client_ip,
            "sid": sid,
            "token": token,
            **hydrate_event.router_data,
        }
        exp_router = RouterData(exp_router_data)
        process_coro = process(
            app,
            event=hydrate_event,
            sid=sid,
            headers={},
            client_ip=client_ip,
        )
        update = await process_coro.__anext__()  # type: ignore
        # route change triggers: [full state dict, call on_load events, call set_is_hydrated(True)]
        assert update == StateUpdate(
            delta={
                state.get_name(): {
                    arg_name: exp_val,
                    f"comp_{arg_name}": exp_val,
                    constants.CompileVars.IS_HYDRATED: False,
                    "loaded": exp_index,
                    "counter": exp_index,
                    "router": exp_router,
                    # "side_effect_counter": exp_index,
                }
            },
            events=[
                _dynamic_state_event(
                    name="on_load",
                    val=exp_val,
                    router_data=exp_router_data,
                ),
                _dynamic_state_event(
                    name="set_is_hydrated",
                    payload={"value": True},
                    val=exp_val,
                    router_data=exp_router_data,
                ),
            ],
        )
        if isinstance(app.state_manager, StateManagerRedis):
            # When redis is used, the state is not updated until the processing is complete
            state = await app.state_manager.get_state(token)
            assert state.dynamic == prev_exp_val

        # complete the processing
        with pytest.raises(StopAsyncIteration):
            await process_coro.__anext__()  # type: ignore

        # check that router data was written to the state_manager store
        state = await app.state_manager.get_state(token)
        assert state.dynamic == exp_val

        process_coro = process(
            app,
            event=_dynamic_state_event(name="on_load", val=exp_val),
            sid=sid,
            headers={},
            client_ip=client_ip,
        )
        on_load_update = await process_coro.__anext__()  # type: ignore
        assert on_load_update == StateUpdate(
            delta={
                state.get_name(): {
                    # These computed vars _shouldn't_ be here, because they didn't change
                    arg_name: exp_val,
                    f"comp_{arg_name}": exp_val,
                    "loaded": exp_index + 1,
                },
            },
            events=[],
        )
        # complete the processing
        with pytest.raises(StopAsyncIteration):
            await process_coro.__anext__()  # type: ignore
        process_coro = process(
            app,
            event=_dynamic_state_event(
                name="set_is_hydrated", payload={"value": True}, val=exp_val
            ),
            sid=sid,
            headers={},
            client_ip=client_ip,
        )
        on_set_is_hydrated_update = await process_coro.__anext__()  # type: ignore
        assert on_set_is_hydrated_update == StateUpdate(
            delta={
                state.get_name(): {
                    # These computed vars _shouldn't_ be here, because they didn't change
                    arg_name: exp_val,
                    f"comp_{arg_name}": exp_val,
                    "is_hydrated": True,
                },
            },
            events=[],
        )
        # complete the processing
        with pytest.raises(StopAsyncIteration):
            await process_coro.__anext__()  # type: ignore

        # a simple state update event should NOT trigger on_load or route var side effects
        process_coro = process(
            app,
            event=_dynamic_state_event(name="on_counter", val=exp_val),
            sid=sid,
            headers={},
            client_ip=client_ip,
        )
        update = await process_coro.__anext__()  # type: ignore
        assert update == StateUpdate(
            delta={
                state.get_name(): {
                    # These computed vars _shouldn't_ be here, because they didn't change
                    f"comp_{arg_name}": exp_val,
                    arg_name: exp_val,
                    "counter": exp_index + 1,
                }
            },
            events=[],
        )
        # complete the processing
        with pytest.raises(StopAsyncIteration):
            await process_coro.__anext__()  # type: ignore

        prev_exp_val = exp_val
    state = await app.state_manager.get_state(token)
    assert state.loaded == len(exp_vals)
    assert state.counter == len(exp_vals)
    # print(f"Expected {exp_vals} rendering side effects, got {state.side_effect_counter}")
    # assert state.side_effect_counter == len(exp_vals)

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.redis.close()


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
    mocker.patch.object(app, "postprocess", AsyncMock())
    event = Event(
        token=token, name="gen_state.go", payload={"c": 5}, router_data=router_data
    )

    async for _update in process(app, event, "mock_sid", {}, "127.0.0.1"):  # type: ignore
        pass

    assert (await app.state_manager.get_state(token)).value == 5
    assert app.postprocess.call_count == 6

    if isinstance(app.state_manager, StateManagerRedis):
        await app.state_manager.redis.close()


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
    if exp_page_child is None:
        assert app.overlay_component is None
    elif isinstance(exp_page_child, Fragment):
        assert app.overlay_component is not None
        generated_component = app._generate_component(app.overlay_component)  # type: ignore
        assert isinstance(generated_component, Fragment)
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

    app.add_page(Box.create("Index"), route="/test")
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
    (web_dir / "package.json").touch()
    app = App()
    app.get_frontend_packages = unittest.mock.Mock()
    with chdir(app_path):
        yield app, web_dir


def test_app_wrap_compile_theme(compilable_app):
    """Test that the radix theme component wraps the app.

    Args:
        compilable_app: compilable_app fixture.
    """
    app, web_dir = compilable_app
    app.theme = rdxt.theme(accent_color="plum")
    app.compile()
    app_js_contents = (web_dir / "pages" / "_app.js").read_text()
    app_js_lines = [
        line.strip() for line in app_js_contents.splitlines() if line.strip()
    ]
    assert (
        "function AppWrap({children}) {"
        "return ("
        "<RadixThemesTheme accentColor={`plum`}>"
        "<Fragment>"
        "{children}"
        "</Fragment>"
        "</RadixThemesTheme>"
        ")"
        "}"
    ) in "".join(app_js_lines)


def test_app_wrap_priority(compilable_app):
    """Test that the app wrap components are wrapped in the correct order.

    Args:
        compilable_app: compilable_app fixture.
    """
    app, web_dir = compilable_app

    class Fragment1(Component):
        tag = "Fragment1"

        def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
            return {(99, "Box"): Box.create()}

    class Fragment2(Component):
        tag = "Fragment2"

        def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
            return {(50, "Text"): Text.create()}

    class Fragment3(Component):
        tag = "Fragment3"

        def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
            return {(10, "Fragment2"): Fragment2.create()}

    def page():
        return Fragment1.create(Fragment3.create())

    app.add_page(page)
    app.compile()
    app_js_contents = (web_dir / "pages" / "_app.js").read_text()
    app_js_lines = [
        line.strip() for line in app_js_contents.splitlines() if line.strip()
    ]
    assert (
        "function AppWrap({children}) {"
        "return ("
        "<Box>"
        "<ChakraProvider theme={extendTheme(theme)}>"
        "<Global styles={GlobalStyles}/>"
        "<ChakraColorModeProvider>"
        "<Text>"
        "<Fragment2>"
        "<Fragment>"
        "{children}"
        "</Fragment>"
        "</Fragment2>"
        "</Text>"
        "</ChakraColorModeProvider>"
        "</ChakraProvider>"
        "</Box>"
        ")"
        "}"
    ) in "".join(app_js_lines)
