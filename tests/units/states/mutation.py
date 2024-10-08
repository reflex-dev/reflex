"""Test states for mutable vars."""

from typing import Dict, List, Set, Union

from sqlalchemy import ARRAY, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import reflex as rx
from reflex.state import BaseState
from reflex.utils.serializers import serializer


class DictMutationTestState(BaseState):
    """A state for testing ReflexDict mutation."""

    # plain dict
    details = {"name": "Tommy"}

    def add_age(self):
        """Add an age to the dict."""
        self.details.update({"age": 20})  # type: ignore

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


class OtherBase(rx.Base):
    """A Base model with a str field."""

    bar: str = ""


class CustomVar(rx.Base):
    """A Base model with multiple fields."""

    foo: str = ""
    array: List[str] = []
    hashmap: Dict[str, str] = {}
    test_set: Set[str] = set()
    custom: OtherBase = OtherBase()


class MutableSQLABase(DeclarativeBase):
    """SQLAlchemy base model for mutable vars."""

    pass


class MutableSQLAModel(MutableSQLABase):
    """SQLAlchemy model for mutable vars."""

    __tablename__: str = "mutable_test_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strlist: Mapped[List[str]] = mapped_column(ARRAY(String))
    hashmap: Mapped[Dict[str, str]] = mapped_column(JSON)
    test_set: Mapped[Set[str]] = mapped_column(ARRAY(String))


@serializer
def serialize_mutable_sqla_model(
    model: MutableSQLAModel,
) -> Dict[str, Union[List[str], Dict[str, str]]]:
    """Serialize the MutableSQLAModel.

    Args:
        model: The MutableSQLAModel instance to serialize.

    Returns:
        The serialized model.
    """
    return {"strlist": model.strlist, "hashmap": model.hashmap}


class MutableTestState(BaseState):
    """A test state."""

    array: List[Union[str, int, List, Dict[str, str]]] = [
        "value",
        [1, 2, 3],
        {"key": "value"},
    ]
    hashmap: Dict[str, Union[List, str, Dict[str, Union[str, Dict]]]] = {
        "key": ["list", "of", "values"],
        "another_key": "another_value",
        "third_key": {"key": "value"},
    }
    test_set: Set[Union[str, int]] = {1, 2, 3, 4, "five"}
    custom: CustomVar = CustomVar()
    _be_custom: CustomVar = CustomVar()
    sqla_model: MutableSQLAModel = MutableSQLAModel(
        strlist=["a", "b", "c"],
        hashmap={"key": "value"},
        test_set={"one", "two", "three"},
    )

    def reassign_mutables(self):
        """Assign mutable fields to different values."""
        self.array = ["modified_value", [1, 2, 3], {"mod_key": "mod_value"}]
        self.hashmap = {
            "mod_key": ["list", "of", "values"],
            "mod_another_key": "another_value",
            "mod_third_key": {"key": "value"},
        }
        self.test_set = {1, 2, 3, 4, "five"}
        self.sqla_model = MutableSQLAModel(
            strlist=["d", "e", "f"],
            hashmap={"key": "value"},
            test_set={"one", "two", "three"},
        )
