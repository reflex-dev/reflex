"""Test fixtures."""
import contextlib
import os
import platform
from pathlib import Path
from typing import Dict, Generator, List, Set, Union

import pytest

import reflex as rx
from reflex import constants
from reflex.app import App
from reflex.event import EventSpec


@pytest.fixture
def app() -> App:
    """A base app.

    Returns:
        The app.
    """
    return App()


@pytest.fixture(scope="function")
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

    class TestState(rx.State):
        """The test state."""

        # plain list
        plain_friends = ["Tommy"]

        def make_friend(self):
            self.plain_friends.append("another-fd")

        def change_first_friend(self):
            self.plain_friends[0] = "Jenny"

        def unfriend_all_friends(self):
            self.plain_friends.clear()

        def unfriend_first_friend(self):
            del self.plain_friends[0]

        def remove_last_friend(self):
            self.plain_friends.pop()

        def make_friends_with_colleagues(self):
            colleagues = ["Peter", "Jimmy"]
            self.plain_friends.extend(colleagues)

        def remove_tommy(self):
            self.plain_friends.remove("Tommy")

        # list in dict
        friends_in_dict = {"Tommy": ["Jenny"]}

        def remove_jenny_from_tommy(self):
            self.friends_in_dict["Tommy"].remove("Jenny")

        def add_jimmy_to_tommy_friends(self):
            self.friends_in_dict["Tommy"].append("Jimmy")

        def tommy_has_no_fds(self):
            self.friends_in_dict["Tommy"].clear()

        # nested list
        friends_in_nested_list = [["Tommy"], ["Jenny"]]

        def remove_first_group(self):
            self.friends_in_nested_list.pop(0)

        def remove_first_person_from_first_group(self):
            self.friends_in_nested_list[0].pop(0)

        def add_jimmy_to_second_group(self):
            self.friends_in_nested_list[1].append("Jimmy")

    return TestState()


@pytest.fixture
def dict_mutation_state():
    """Create a state with dict mutation features.

    Returns:
        A state with dict mutation features.
    """

    class TestState(rx.State):
        """The test state."""

        # plain dict
        details = {"name": "Tommy"}

        def add_age(self):
            self.details.update({"age": 20})  # type: ignore

        def change_name(self):
            self.details["name"] = "Jenny"

        def remove_last_detail(self):
            self.details.popitem()

        def clear_details(self):
            self.details.clear()

        def remove_name(self):
            del self.details["name"]

        def pop_out_age(self):
            self.details.pop("age")

        # dict in list
        address = [{"home": "home address"}, {"work": "work address"}]

        def remove_home_address(self):
            self.address[0].pop("home")

        def add_street_to_home_address(self):
            self.address[0]["street"] = "street address"

        # nested dict
        friend_in_nested_dict = {"name": "Nikhil", "friend": {"name": "Alek"}}

        def change_friend_name(self):
            self.friend_in_nested_dict["friend"]["name"] = "Tommy"

        def remove_friend(self):
            self.friend_in_nested_dict.pop("friend")

        def add_friend_age(self):
            self.friend_in_nested_dict["friend"]["age"] = 30

    return TestState()


class UploadState(rx.State):
    """The base state for uploading a file."""

    async def handle_upload1(self, files: List[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass


class BaseState(rx.State):
    """The test base state."""

    pass


class SubUploadState(BaseState):
    """The test substate."""

    img: str

    async def handle_upload(self, files: List[rx.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass


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
def upload_state(tmp_path):
    """Create upload state.

    Args:
        tmp_path: pytest tmp_path

    Returns:
        The state

    """

    class FileUploadState(rx.State):
        """The base state for uploading a file."""

        img_list: List[str]

        async def handle_upload2(self, files):
            """Handle the upload of a file.

            Args:
                files: The uploaded files.
            """
            for file in files:
                upload_data = await file.read()
                outfile = f"{tmp_path}/{file.filename}"

                # Save the file.
                with open(outfile, "wb") as file_object:
                    file_object.write(upload_data)

                # Update the img var.
                self.img_list.append(file.filename)

        async def multi_handle_upload(self, files: List[rx.UploadFile]):
            """Handle the upload of a file.

            Args:
                files: The uploaded files.
            """
            for file in files:
                upload_data = await file.read()
                outfile = f"{tmp_path}/{file.filename}"

                # Save the file.
                with open(outfile, "wb") as file_object:
                    file_object.write(upload_data)

                # Update the img var.
                assert file.filename is not None
                self.img_list.append(file.filename)

    return FileUploadState


@pytest.fixture
def upload_sub_state(tmp_path):
    """Create upload substate.

    Args:
        tmp_path: pytest tmp_path

    Returns:
        The state

    """

    class FileState(rx.State):
        """The base state."""

        pass

    class FileUploadState(FileState):
        """The substate for uploading a file."""

        img_list: List[str]

        async def handle_upload2(self, files):
            """Handle the upload of a file.

            Args:
                files: The uploaded files.
            """
            for file in files:
                upload_data = await file.read()
                outfile = f"{tmp_path}/{file.filename}"

                # Save the file.
                with open(outfile, "wb") as file_object:
                    file_object.write(upload_data)

                # Update the img var.
                self.img_list.append(file.filename)

        async def multi_handle_upload(self, files: List[rx.UploadFile]):
            """Handle the upload of a file.

            Args:
                files: The uploaded files.
            """
            for file in files:
                upload_data = await file.read()
                outfile = f"{tmp_path}/{file.filename}"

                # Save the file.
                with open(outfile, "wb") as file_object:
                    file_object.write(upload_data)

                # Update the img var.
                assert file.filename is not None
                self.img_list.append(file.filename)

    return FileUploadState


@pytest.fixture
def upload_grand_sub_state(tmp_path):
    """Create upload grand-state.

    Args:
        tmp_path: pytest tmp_path

    Returns:
        The state

    """

    class BaseFileState(rx.State):
        """The base state."""

        pass

    class FileSubState(BaseFileState):
        """The substate."""

        pass

    class FileUploadState(FileSubState):
        """The grand-substate for uploading a file."""

        img_list: List[str]

        async def handle_upload2(self, files):
            """Handle the upload of a file.

            Args:
                files: The uploaded files.
            """
            for file in files:
                upload_data = await file.read()
                outfile = f"{tmp_path}/{file.filename}"

                # Save the file.
                with open(outfile, "wb") as file_object:
                    file_object.write(upload_data)

                # Update the img var.
                assert file.filename is not None
                self.img_list.append(file.filename)

        async def multi_handle_upload(self, files: List[rx.UploadFile]):
            """Handle the upload of a file.

            Args:
                files: The uploaded files.
            """
            for file in files:
                upload_data = await file.read()
                outfile = f"{tmp_path}/{file.filename}"

                # Save the file.
                with open(outfile, "wb") as file_object:
                    file_object.write(upload_data)

                # Update the img var.
                assert file.filename is not None
                self.img_list.append(file.filename)

    return FileUploadState


@pytest.fixture
def base_config_values() -> Dict:
    """Get base config values.

    Returns:
        Dictionary of base config values
    """
    return {"app_name": "app", "db_url": constants.DB_URL, "env": rx.Env.DEV}


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


class GenState(rx.State):
    """A state with event handlers that generate multiple updates."""

    value: int

    def go(self, c: int):
        """Increment the value c times and update each time.

        Args:
            c: The number of times to increment.

        Yields:
            After each increment.
        """
        for _ in range(c):
            self.value += 1
            yield


@pytest.fixture
def gen_state() -> GenState:
    """A state.

    Returns:
        A test state.
    """
    return GenState  # type: ignore


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
        "name=reflex;"
        " list_cookies=%5B%22some%22%2C%20%22random%22%2C%20%22cookies%22%5D;"
        " dict_cookies=%7B%22name%22%3A%20%22reflex%22%7D; val=true",
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

    class MutableTestState(rx.State):
        """A test state."""

        array: List[Union[str, List, Dict[str, str]]] = [
            "value",
            [1, 2, 3],
            {"key": "value"},
        ]
        hashmap: Dict[str, Union[List, str, Dict[str, str]]] = {
            "key": ["list", "of", "values"],
            "another_key": "another_value",
            "third_key": {"key": "value"},
        }
        test_set: Set[Union[str, int]] = {1, 2, 3, 4, "five"}

        def reassign_mutables(self):
            self.array = ["modified_value", [1, 2, 3], {"mod_key": "mod_value"}]
            self.hashmap = {
                "mod_key": ["list", "of", "values"],
                "mod_another_key": "another_value",
                "mod_third_key": {"key": "value"},
            }
            self.test_set = {1, 2, 3, 4, "five"}

    return MutableTestState()
