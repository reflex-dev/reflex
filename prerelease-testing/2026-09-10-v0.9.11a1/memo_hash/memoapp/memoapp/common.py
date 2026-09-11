"""State shared by the collision modules so their renders stay byte-identical."""

import enum

import reflex as rx


class Shared(rx.State):
    """Shared reactive state; both collision modules bind the same var."""

    label: str = "shared"
    items: list[str] = ["i0", "i1", "i2"]

    @rx.event
    def relabel(self):
        """Change the shared label."""
        self.label = "relabelled"


class Level(enum.IntEnum):
    """IntEnum used as a memo prop (IntEnum member vs plain int)."""

    ONE = 1
    TWO = 2


class Hue(enum.Enum):
    """Str-valued enum used in rx.match / rx.cond inside a memo."""

    RED = "red"
    BLUE = "blue"
