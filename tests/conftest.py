"""Test fixtures."""
import platform
from typing import Generator

import pytest

from pynecone.state import State


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

    class TestState(State):
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

    class TestState(State):
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
