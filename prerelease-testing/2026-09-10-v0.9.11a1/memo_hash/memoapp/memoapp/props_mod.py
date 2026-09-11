"""Memoized components taking dataclass / enum props (#6947 collision rows 6 and 7)."""

import dataclasses

import reflex as rx

from .common import Hue, Level, Shared


@dataclasses.dataclass(frozen=True)
class Alpha:
    """A frozen dataclass whose layout matches Beta's exactly."""

    a: str


@dataclasses.dataclass(frozen=True)
class Beta:
    """A frozen dataclass whose layout matches Alpha's exactly."""

    a: str


def make_local_dataclass(marker: str):
    """Build a dataclass inside a function body (fresh class per call).

    Args:
        marker: Distinguishes the generated class' qualname.

    Returns:
        The generated dataclass type.
    """

    @dataclasses.dataclass(frozen=True)
    class Local:
        a: str

    Local.__qualname__ = f"Local{marker}"
    return Local


@rx.memo
def show_obj(obj: dict, tid: str) -> rx.Component:
    """Render a serialized dataclass prop.

    Args:
        obj: The serialized dataclass.
        tid: The DOM id.

    Returns:
        The component.
    """
    return rx.el.span(obj["a"], id=tid, class_name="memo-obj")


@rx.memo
def show_level(level: int, tid: str) -> rx.Component:
    """Render a numeric prop that may be an IntEnum member or a plain int.

    Args:
        level: The level.
        tid: The DOM id.

    Returns:
        The component.
    """
    return rx.el.span(level.to_string(), id=tid, class_name="memo-level")


@rx.memo
def show_hue(hue: str, tid: str) -> rx.Component:
    """Render rx.match / rx.cond over an enum-valued prop inside a memo body.

    Args:
        hue: The hue string.
        tid: The DOM id.

    Returns:
        The component.
    """
    return rx.el.span(
        rx.match(
            hue,
            (Hue.RED.value, "matched-red"),
            (Hue.BLUE.value, "matched-blue"),
            "matched-none",
        ),
        "|",
        rx.cond(hue == Hue.RED.value, "cond-red", "cond-not-red"),
        "|",
        Shared.label,
        id=tid,
        class_name="memo-hue",
    )


def props_panel() -> rx.Component:
    """Render every dataclass / enum prop case.

    Returns:
        The panel.
    """
    LocalOne = make_local_dataclass("One")
    LocalTwo = make_local_dataclass("Two")
    return rx.el.div(
        show_obj(obj=Alpha(a="x"), tid="obj-alpha"),
        show_obj(obj=Beta(a="x"), tid="obj-beta"),
        show_obj(obj=LocalOne(a="x"), tid="obj-local-one"),
        show_obj(obj=LocalTwo(a="x"), tid="obj-local-two"),
        show_level(level=Level.ONE, tid="level-enum"),
        show_level(level=1, tid="level-int"),
        show_level(level=Level.TWO, tid="level-enum-two"),
        show_hue(hue=Hue.RED.value, tid="hue-red"),
        show_hue(hue=Hue.BLUE.value, tid="hue-blue"),
        id="props-panel",
    )
