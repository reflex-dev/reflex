"""Test fixtures."""
import contextlib
import os
import platform
import uuid
from pathlib import Path
from typing import Dict, Generator

import pytest

import nextpy as xt
from nextpy.app import App
from nextpy.core.event import EventSpec

from .states import (
    DictMutationTestState,
    ListMutationTestState,
    MutableTestState,
    SubUploadState,
    UploadState,
)


@pytest.fixture
def app() -> App:
    """A base app.

    Returns:
        The app.
    """
    return App()


@pytest.fixture(scope="session")
def windows_platform() -> Generator:
    """Check if system is windows.

    Yields:
        whether system is windows.
    """
    yield platform.system() == "Windows"


@pytest.fixture
def list_mutation_state():
    """Create a state with list mutation features.

    Returns:
        A state with list mutation features.
    """
    return ListMutationTestState()


@pytest.fixture
def dict_mutation_state():
    """Create a state with dict mutation features.

    Returns:
        A state with dict mutation features.
    """
    return DictMutationTestState()


@pytest.fixture
def upload_sub_state_event_spec():
    """Create an event Spec for a substate.

    Returns:
        Event Spec.
    """
    return EventSpec(handler=SubUploadState.handle_upload, upload=True)  # type: ignore


@pytest.fixture
def upload_event_spec():
    """Create an event Spec for a multi-upload base state.

    Returns:
        Event Spec.
    """
    return EventSpec(handler=UploadState.handle_upload1, upload=True)  # type: ignore


@pytest.fixture
def base_config_values() -> Dict:
    """Get base config values.

    Returns:
        Dictionary of base config values
    """
    return {"app_name": "app"}


@pytest.fixture
def base_db_config_values() -> Dict:
    """Get base DBConfig values.

    Returns:
        Dictionary of base db config values
    """
    return {"database": "db"}


@pytest.fixture
def sqlite_db_config_values(base_db_config_values) -> Dict:
    """Get sqlite DBConfig values.

    Args:
        base_db_config_values: Base DBConfig fixture.

    Returns:
        Dictionary of sqlite DBConfig values
    """
    base_db_config_values["engine"] = "sqlite"
    return base_db_config_values


@pytest.fixture
def router_data_headers() -> Dict[str, str]:
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
        "name=nextpy;"
        " list_cookies=%5B%22some%22%2C%20%22random%22%2C%20%22cookies%22%5D;"
        " dict_cookies=%7B%22name%22%3A%20%22nextpy%22%7D; val=true",
        "sec-websocket-key": "mock-websocket-key",
        "sec-websocket-extensions": "permessage-deflate; client_max_window_bits",
    }


@pytest.fixture
def router_data(router_data_headers) -> Dict[str, str]:
    """Router data.

    Args:
        router_data_headers: Headers fixture.

    Returns:
        Dict of router data.
    """
    return {  # type: ignore
        "pathname": "/",
        "query": {},
        "token": "b181904c-3953-4a79-dc18-ae9518c22f05",
        "sid": "9fpxSzPb9aFMb4wFAAAH",
        "headers": router_data_headers,
        "ip": "127.0.0.1",
    }


# borrowed from py3.11
class chdir(contextlib.AbstractContextManager):
    """Non thread-safe context manager to change the current working directory."""

    def __init__(self, path):
        """Prepare contextmanager.

        Args:
            path: the path to change to
        """
        self.path = path
        self._old_cwd = []

    def __enter__(self):
        """Save current directory and perform chdir."""
        self._old_cwd.append(Path(".").resolve())
        os.chdir(self.path)

    def __exit__(self, *excinfo):
        """Change back to previous directory on stack.

        Args:
            excinfo: sys.exc_info captured in the context block
        """
        os.chdir(self._old_cwd.pop())


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
def mutable_state():
    """Create a Test state containing mutable types.

    Returns:
        A state object.
    """
    return MutableTestState()


@pytest.fixture(scope="function")
def token() -> str:
    """Create a token.

    Returns:
        A fresh/unique token string.
    """
    return str(uuid.uuid4())


@pytest.fixture
def duplicate_substate():
    """Create a Test state that has duplicate child substates.

    Returns:
        The test state.
    """

    class TestState(xt.State):
        pass

    class ChildTestState(TestState):  # type: ignore # noqa
        pass

    class ChildTestState(TestState):  # type: ignore # noqa
        pass

    return TestState
