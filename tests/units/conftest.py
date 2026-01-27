"""Test fixtures."""

import platform
import uuid
from collections.abc import Generator
from unittest import mock

import pytest

from reflex.app import App
from reflex.event import EventSpec
from reflex.model import ModelRegistry
from reflex.testing import chdir
from reflex.utils import prerequisites

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
