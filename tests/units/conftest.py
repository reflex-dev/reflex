"""Test fixtures."""

import platform
import traceback
import uuid
from collections.abc import AsyncGenerator, Generator, Mapping
from copy import deepcopy
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from reflex_base.components.component import CUSTOM_COMPONENTS
from reflex_base.event import Event, EventSpec
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor, EventProcessor
from reflex_base.registry import RegistrationContext

from reflex.app import App
from reflex.experimental.memo import EXPERIMENTAL_MEMOS
from reflex.istate.manager import StateManager
from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis
from reflex.model import ModelRegistry
from reflex.testing import chdir
from reflex.utils import prerequisites
from tests.units.mock_redis import mock_redis

from .states.upload import SubUploadState, UploadState


@pytest.fixture
def app() -> App:
    """A base app.

    Returns:
        The app.
    """
    return App()


@pytest.fixture
def app_module_mock(monkeypatch) -> mock.Mock:
    """Mock the app module.

    This overwrites prerequisites.get_app to return the mock for the app module.

    To use this in your test, assign `app_module_mock.app = rx.App(...)`.

    Args:
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        The mock for the main app module.
    """
    app_module_mock = mock.Mock()
    get_app_mock = mock.Mock(return_value=app_module_mock)
    monkeypatch.setattr(prerequisites, "get_app", get_app_mock)
    return app_module_mock


@pytest.fixture
def mock_app(app_module_mock: mock.Mock, app: App) -> App:
    """A mocked dummy app per test.

    Args:
        app_module_mock: The mock for the main app module.
        app: A default App instance.

    Returns:
        The mock app instance.
    """
    app_module_mock.app = app
    return app


@pytest.fixture(scope="session")
def windows_platform() -> bool:
    """Check if system is windows.

    Returns:
        whether system is windows.
    """
    return platform.system() == "Windows"


@pytest.fixture
def upload_sub_state_event_spec():
    """Create an event Spec for a substate.

    Returns:
        Event Spec.
    """
    return EventSpec(handler=SubUploadState.handle_upload, upload=True)  # pyright: ignore [reportCallIssue]


@pytest.fixture
def upload_event_spec():
    """Create an event Spec for a multi-upload base state.

    Returns:
        Event Spec.
    """
    return EventSpec(handler=UploadState.handle_upload1, upload=True)  # pyright: ignore [reportCallIssue]


@pytest.fixture
def base_config_values() -> dict:
    """Get base config values.

    Returns:
        Dictionary of base config values
    """
    return {"app_name": "app"}


@pytest.fixture
def base_db_config_values() -> dict:
    """Get base DBConfig values.

    Returns:
        Dictionary of base db config values
    """
    return {"database": "db"}


@pytest.fixture
def sqlite_db_config_values(base_db_config_values) -> dict:
    """Get sqlite DBConfig values.

    Args:
        base_db_config_values: Base DBConfig fixture.

    Returns:
        Dictionary of sqlite DBConfig values
    """
    base_db_config_values["engine"] = "sqlite"
    return base_db_config_values


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
def token() -> str:
    """Create a token.

    Returns:
        A fresh/unique token string.
    """
    return str(uuid.uuid4())


@pytest.fixture
def model_registry() -> Generator[type[ModelRegistry], None, None]:
    """Create a model registry.

    Yields:
        A fresh model registry.
    """
    yield ModelRegistry
    ModelRegistry._metadata = None


@pytest_asyncio.fixture(
    loop_scope="function", scope="function", params=["in_process", "disk", "redis"]
)
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
    state_manager = StateManager.create()
    if request.param == "redis":
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
def mock_event_processor_obj() -> EventProcessor:
    """Create an event processor.

    Returns:
        A fresh event processor.
    """

    def handle_backend_exception(ex: Exception) -> None:
        raise ex

    return EventProcessor(
        backend_exception_handler=handle_backend_exception, graceful_shutdown_timeout=1
    )


@pytest.fixture
def mock_base_state_event_processor_obj(
    monkeypatch: pytest.MonkeyPatch,
) -> BaseStateEventProcessor:
    """Create a BaseState event processor.

    Args:
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        A fresh BaseState event processor.
    """
    monkeypatch.setattr(BaseStateEventProcessor, "_rehydrate", mock.AsyncMock())

    def handle_backend_exception(ex: Exception) -> None:
        formatted_exc = "\n".join(traceback.format_exception(ex))
        pytest.fail(f"Event processor raised an unexpected exception:\n{formatted_exc}")

    return BaseStateEventProcessor(
        backend_exception_handler=handle_backend_exception, graceful_shutdown_timeout=1
    )


@pytest.fixture
def emitted_deltas() -> list[tuple[str, Mapping[str, Mapping[str, Any]]]]:
    """Create a list to store emitted deltas.

    Returns:
        A list to store emitted deltas.
    """
    return []


@pytest.fixture
def emitted_events() -> list[tuple[str, tuple[Event, ...]]]:
    """Create a list to store emitted events.

    Returns:
        A list to store emitted events.
    """
    return []


@pytest_asyncio.fixture
async def mock_root_event_context(
    mock_base_state_event_processor_obj: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
    emitted_events: list[tuple[str, tuple[Event, ...]]],
) -> AsyncGenerator[EventContext]:
    """Create a mock event context.

    Args:
        mock_base_state_event_processor_obj: The mock event processor to use for the context's enqueue implementation.
        emitted_deltas: The list to store emitted deltas.
        emitted_events: The list to store emitted events.

    Yields:
        A mock event context.
    """

    async def emit_delta_impl(  # noqa: RUF029
        token: str, delta: Mapping[str, Mapping[str, Any]]
    ) -> None:
        """Mock emit delta implementation that records emitted deltas.

        Args:
            token: The client token to emit the delta to.
            delta: The delta to emit.
        """
        emitted_deltas.append((token, delta))

    async def emit_event_impl(token: str, *events: Event) -> None:  # noqa: RUF029
        """Mock emit event implementation that records emitted events.

        Args:
            token: The client token to emit the events to.
            events: The events to emit.
        """
        emitted_events.append((token, events))

    state_manager = StateManagerMemory()
    yield EventContext(
        token="",
        state_manager=state_manager,
        enqueue_impl=mock_base_state_event_processor_obj.enqueue_many,
        emit_delta_impl=emit_delta_impl,
        emit_event_impl=emit_event_impl,
    )
    await state_manager.close()


@pytest.fixture
def mock_event_processor(
    mock_root_event_context: EventContext, mock_event_processor_obj: EventProcessor
) -> EventProcessor:
    """Create an event processor with a mock root context.

    Set the mock context as the task's current context, and set the processor's
    root context to the mock context.

    Events can be queued against the processor via `await
    mock_event_processor.enqueue(token, *events)`.

    The `state_manager` fixture is used by the `mock_root_event_context` so any
    updates will be reflected in the context's state manager, and any deltas or
    frontend events can be checked via the context's `emitted_deltas` and
    `emitted_events` attributes.

    Args:
        mock_root_event_context: The mock event context to use as the root context for the processor.
        mock_event_processor_obj: The mock event processor to use for the processor's enqueue implementation.

    Returns:
        An un-started event processor with a mock root context.
    """
    mock_event_processor_obj._root_context = mock_root_event_context
    return mock_event_processor_obj


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
def forked_registration_context() -> Generator[RegistrationContext, None, None]:
    """Fork the registration context and attach it.

    Sets the forked context as the current registration context for the duration
    of the test, then resets it afterwards.

    Yields:
        The forked RegistrationContext.
    """
    with deepcopy(RegistrationContext.get()) as ctx:
        yield ctx


@pytest.fixture
def clean_registration_context() -> Generator[RegistrationContext, None, None]:
    """Create and attach a clean registration context.

    Sets the new context as the current registration context for the duration
    of the test, then resets it afterwards.

    Yields:
        The clean RegistrationContext.
    """
    with RegistrationContext() as ctx:
        yield ctx


@pytest.fixture
def preserve_memo_registries():
    """Save and restore global memo registries around a test.

    Yields:
        None
    """
    custom_components = dict(CUSTOM_COMPONENTS)
    experimental_memos = dict(EXPERIMENTAL_MEMOS)
    try:
        yield
    finally:
        CUSTOM_COMPONENTS.clear()
        CUSTOM_COMPONENTS.update(custom_components)
        EXPERIMENTAL_MEMOS.clear()
        EXPERIMENTAL_MEMOS.update(experimental_memos)
