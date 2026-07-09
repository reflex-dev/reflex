"""Tests for reflex_base.vars.base state metaclass field handling."""

from reflex_base.vars.base import EvenMoreBasicBaseState, field

_MARKER_ATTR = "_marker"


def test_custom_field_attr_survives_annotated_rebuild():
    """A custom attribute on an annotated Field survives a rebuild."""
    f = field("x")
    setattr(f, _MARKER_ATTR, "tag")

    class MyState(EvenMoreBasicBaseState):
        name: str = f  # pyright: ignore[reportAssignmentType]

    rebuilt = MyState.get_fields()["name"]
    assert getattr(rebuilt, _MARKER_ATTR, None) == "tag"
    assert rebuilt.annotated_type is str


def test_custom_field_attr_survives_unannotated_rebuild():
    """A custom attribute survives an inferred-type Field rebuild."""
    f = field(0)
    setattr(f, _MARKER_ATTR, "tag")

    class MyState(EvenMoreBasicBaseState):
        count = f

    rebuilt = MyState.get_fields()["count"]
    assert getattr(rebuilt, _MARKER_ATTR, None) == "tag"
    assert rebuilt.annotated_type is int


def test_custom_field_attr_survives_unannotated_factory_rebuild():
    """A custom attribute survives a default-factory Field rebuild."""
    f = field(default_factory=list)
    setattr(f, _MARKER_ATTR, "tag")

    class MyState(EvenMoreBasicBaseState):
        items = f

    rebuilt = MyState.get_fields()["items"]
    assert getattr(rebuilt, _MARKER_ATTR, None) == "tag"
