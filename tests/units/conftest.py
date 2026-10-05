"""Fixtures for the framework and cross-package unit suite."""

import collections
import dataclasses
import enum
import platform
import sys
from collections.abc import AsyncGenerator, Generator
from types import ModuleType

import pytest
import pytest_asyncio
from reflex_base.components.memo import MEMOS
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor

from reflex.app import App
from reflex.istate.manager import StateManager
from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis
from reflex.model import ModelRegistry
from reflex.testing import chdir
from reflex.testing.fixtures import _isolate_app_in_context as _isolate_app_in_context
from reflex.testing.fixtures import app_module_mock as app_module_mock
from reflex.testing.fixtures import (
    clean_registration_context as clean_registration_context,
)
from reflex.testing.fixtures import emitted_deltas as emitted_deltas
from reflex.testing.fixtures import emitted_events as emitted_events
from reflex.testing.fixtures import (
    forked_registration_context as forked_registration_context,
)
from reflex.testing.fixtures import (
    mock_base_state_event_processor_obj as mock_base_state_event_processor_obj,
)
from reflex.testing.fixtures import mock_root_event_context as mock_root_event_context
from reflex.testing.fixtures import otel_exporter as otel_exporter
from reflex.testing.fixtures import otel_metrics as otel_metrics
from reflex.testing.fixtures import otel_sdk as otel_sdk
from reflex.testing.fixtures import token as token
from tests.units.mock_redis import mock_redis


@pytest.fixture
def app() -> App:
    """A base app.

    Returns:
        The app.
    """
    return App()


@pytest.fixture(scope="session")
def windows_platform() -> bool:
    """Check if system is windows.

    Returns:
        whether system is windows.
    """
    return platform.system() == "Windows"


@pytest.fixture
def base_config_values() -> dict:
    """Get base config values.

    Returns:
        Dictionary of base config values
    """
    return {"app_name": "app"}


@pytest.fixture
def router_data_headers() -> dict[str, str]:
    """Router data headers.

    Returns:
        client headers
    """
    return {
        "host": "localhost:8000",
        "connection": "Upgrade",
        "pragma": "no-cache",
        "cache-control": "no-cache",
        "user-agent": "Mock Agent",
        "upgrade": "websocket",
        "origin": "http://localhost:3000",
        "sec-websocket-version": "13",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-US,en;q=0.9",
        "cookie": "csrftoken=mocktoken; "
        "name=reflex;"
        " list_cookies=%5B%22some%22%2C%20%22random%22%2C%20%22cookies%22%5D;"
        " dict_cookies=%7B%22name%22%3A%20%22reflex%22%7D; val=true",
        "sec-websocket-key": "mock-websocket-key",
        "sec-websocket-extensions": "permessage-deflate; client_max_window_bits",
    }


@pytest.fixture
def router_data(router_data_headers: dict[str, str]) -> dict[str, str | dict]:
    """Router data.

    Args:
        router_data_headers: Headers fixture.

    Returns:
        Dict of router data.
    """
    return {
        "pathname": "/",
        "query": {},
        "token": "b181904c-3953-4a79-dc18-ae9518c22f05",
        "sid": "9fpxSzPb9aFMb4wFAAAH",
        "headers": router_data_headers,
        "ip": "127.0.0.1",
    }


@pytest.fixture
def tmp_working_dir(tmp_path):
    """Create a temporary directory and chdir to it.

    After the test executes, chdir back to the original working directory.

    Args:
        tmp_path: pytest tmp_path fixture creates per-test temp dir

    Yields:
        subdirectory of tmp_path which is now the current working directory.
    """
    working_dir = tmp_path / "working_dir"
    working_dir.mkdir()
    with chdir(working_dir):
        yield working_dir


@pytest.fixture
def app_classes_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Create a throwaway module of app classes that a stored state can pickle.

    Tests break the module (remove it, delete a class, change a class) to
    simulate a deploy that changes classes held in a stored state.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The module, registered in sys.modules, with Entry, Color and Point.
    """
    module = ModuleType("_reflex_test_app_classes")
    monkeypatch.setitem(sys.modules, module.__name__, module)

    @dataclasses.dataclass
    class Entry:
        name: str

    Entry.__module__ = module.__name__
    Entry.__qualname__ = "Entry"
    module.Entry = Entry  # pyright: ignore[reportAttributeAccessIssue]
    module.Color = enum.Enum(  # pyright: ignore[reportAttributeAccessIssue]
        "Color", {"RED": "red", "BLUE": "blue"}, module=module.__name__
    )
    module.Point = collections.namedtuple("Point", "x y", module=module.__name__)  # pyright: ignore[reportAttributeAccessIssue]
    return module


@pytest.fixture
def model_registry() -> Generator[type[ModelRegistry], None, None]:
    """Create a model registry.

    Yields:
        A fresh model registry.
    """
    yield ModelRegistry
    ModelRegistry._metadata = None


@pytest_asyncio.fixture(loop_scope="function", params=["in_process", "disk", "redis"])
async def state_manager(
    request: pytest.FixtureRequest, mock_root_event_context: EventContext
) -> AsyncGenerator[StateManager, None]:
    """Instance of state manager parametrized for redis and in-process.

    Args:
        request: pytest request object.
        mock_root_event_context: The mock root event context to use for the state manager.

    Yields:
        A state manager instance
    """
    if request.param == "redis":
        # Only construct the configured manager for the redis param. When
        # REFLEX_REDIS_URL is set, `StateManager.create()` returns a live
        # StateManagerRedis that starts a `_lock_task`, so building one for the
        # other params would orphan that task: it is replaced below and never
        # closed, and then blocks event-loop teardown.
        state_manager = StateManager.create()
        if not isinstance(state_manager, StateManagerRedis):
            state_manager = StateManagerRedis(redis=mock_redis())
    elif request.param == "disk":
        # explicitly NOT using redis
        state_manager = StateManagerDisk()
        assert not state_manager._states_locks
    else:
        state_manager = StateManagerMemory()
        assert not state_manager._states_locks

    orig_state_manager = mock_root_event_context.state_manager
    object.__setattr__(mock_root_event_context, "state_manager", state_manager)

    yield state_manager

    await state_manager.close()
    object.__setattr__(mock_root_event_context, "state_manager", orig_state_manager)


@pytest.fixture
def mock_base_state_event_processor(
    mock_root_event_context: EventContext,
    mock_base_state_event_processor_obj: BaseStateEventProcessor,
) -> BaseStateEventProcessor:
    """Create a BaseState event processor with a mock root context.

    Set the mock context as the task's current context, and set the processor's
    root context to the mock context.

    Events can be queued against the processor via `await
    mock_base_state_event_processor.enqueue(token, *events)`.

    The `state_manager` fixture is used by the `mock_root_event_context` so any
    updates will be reflected in the context's state manager, and any deltas or
    frontend events can be checked via the context's `emitted_deltas` and
    `emitted_events` attributes.

    Args:
        mock_root_event_context: The mock event context to use as the root context for the processor.
        mock_base_state_event_processor_obj: The mock BaseState event processor to use for the processor's enqueue implementation.

    Returns:
        An un-started event processor with a mock root context.
    """
    mock_base_state_event_processor_obj._root_context = mock_root_event_context
    return mock_base_state_event_processor_obj


@pytest.fixture
def attached_mock_event_context(
    mock_root_event_context: EventContext, token: str
) -> Generator[EventContext, None, None]:
    """Fork the mock event context for the given token and attach it.

    Sets the forked context as the current event_context for the duration
    of the test, then resets it afterwards.

    Args:
        mock_root_event_context: The mock root event context.
        token: The client token.

    Yields:
        The forked EventContext.
    """
    with mock_root_event_context.fork(token=token) as ctx:
        yield ctx


@pytest_asyncio.fixture
async def attached_mock_base_state_event_processor(
    mock_base_state_event_processor: BaseStateEventProcessor,
) -> AsyncGenerator[BaseStateEventProcessor]:
    """Fork the mock event context for the given token, attach it, and set the processor's root context to it.

    Args:
        mock_base_state_event_processor: The mock BaseState event processor to use for the processor's enqueue implementation.

    Yields:
        The mock BaseState event processor with the attached context as its root context.
    """
    async with mock_base_state_event_processor as processor:
        yield processor


@pytest.fixture
def preserve_memo_registries():
    """Save and restore the global memo registry around a test.

    Yields:
        None
    """
    memos = dict(MEMOS)
    try:
        yield
    finally:
        MEMOS.clear()
        MEMOS.update(memos)
