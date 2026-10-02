"""Test states for mutable vars."""

import pytest

from reflex.state import BaseState

pytest.importorskip("pydantic")

import pydantic


class OtherBase(pydantic.BaseModel):
    """A BaseModel with a str field."""

    bar: str = pydantic.Field(default="")


class CustomVar(pydantic.BaseModel):
    """A BaseModel with multiple fields."""

    foo: str = pydantic.Field(default="")
    array: list[str] = pydantic.Field(default_factory=list)
    hashmap: dict[str, str] = pydantic.Field(default_factory=dict)
    test_set: set[str] = pydantic.Field(default_factory=set)
    custom: OtherBase = pydantic.Field(default_factory=OtherBase)


class MutableTestState(BaseState):
    """A test state without SQLAlchemy dependencies."""

    array: list[str | int | list | dict[str, str]] = [
        "value",
        [1, 2, 3],
        {"key": "value"},
    ]
    hashmap: dict[str, list | str | dict[str, str | dict]] = {
        "key": ["list", "of", "values"],
        "another_key": "another_value",
        "third_key": {"key": "value"},
    }
    test_set: set[str | int] = {1, 2, 3, 4, "five"}
    custom: CustomVar = CustomVar()
    _be_custom: CustomVar = CustomVar()

    def reassign_mutables(self):
        """Assign mutable fields to different values."""
        self.array = ["modified_value", [1, 2, 3], {"mod_key": "mod_value"}]
        self.hashmap = {
            "mod_key": ["list", "of", "values"],
            "mod_another_key": "another_value",
            "mod_third_key": {"key": "value"},
        }
        self.test_set = {1, 2, 3, 4, "five"}

    def _get_array(self) -> list[str | int | list | dict[str, str]]:
        return self.array
