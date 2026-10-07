"""Plain data types used as state var annotations."""

import dataclasses
import datetime
import enum
from typing import TypedDict

import pydantic


@dataclasses.dataclass
class Point:
    """A dataclass var."""

    x: int = 0
    y: int = 0
    tags: list[str] = dataclasses.field(default_factory=list)


class PModel(pydantic.BaseModel):
    """A pydantic model var."""

    name: str = "p"
    tags: list[str] = []
    when: datetime.datetime | None = None


class Color(enum.Enum):
    """An enum var."""

    RED = "red"
    GREEN = "green"


class TD(TypedDict):
    """A TypedDict var."""

    a: int
    b: str
