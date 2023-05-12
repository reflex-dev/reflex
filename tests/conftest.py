"""Test fixtures."""
import platform
from typing import Dict, Generator, List

import pytest

import pynecone as pc
from pynecone import constants
from pynecone.event import EventSpec


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

    class TestState(pc.State):
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

    class TestState(pc.State):
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


class UploadState(pc.State):
    """The base state for uploading a file."""

    async def handle_upload1(self, files: List[pc.UploadFile]):
        """Handle the upload of a file.

        Args:
            files: The uploaded files.
        """
        pass


class BaseState(pc.State):
    """The test base state."""

    pass


class SubUploadState(BaseState):
    """The test substate."""

    img: str

    async def handle_upload(self, files: List[pc.UploadFile]):
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

    class FileUploadState(pc.State):
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

        async def multi_handle_upload(self, files: List[pc.UploadFile]):
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

    class FileState(pc.State):
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

        async def multi_handle_upload(self, files: List[pc.UploadFile]):
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

    class BaseFileState(pc.State):
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

        async def multi_handle_upload(self, files: List[pc.UploadFile]):
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
    return {"app_name": "app", "db_url": constants.DB_URL, "env": pc.Env.DEV}


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
