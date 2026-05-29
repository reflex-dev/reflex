"""Tests for reflex-docgen."""

import dataclasses
import inspect
import sys
from importlib.util import find_spec

import pytest
from reflex_base.components.component import (
    DEFAULT_TRIGGERS_AND_DESC,
    Component,
    TriggerDefinition,
    field,
)
from reflex_base.constants import EventTriggers
from reflex_base.event import EventHandler, no_args_event_spec
from reflex_docgen import (
    generate_class_documentation,
    generate_documentation,
    get_component_event_handlers,
)


def test_default_triggers_have_descriptions():
    """Every entry in DEFAULT_TRIGGERS should carry a non-empty description."""
    for name, trigger in DEFAULT_TRIGGERS_AND_DESC.items():
        assert isinstance(trigger, TriggerDefinition), (
            f"{name} should be a TriggerDefinition"
        )
        assert trigger.description, f"{name} has an empty description"
        assert trigger.spec is not None, f"{name} has no spec"


def test_get_component_event_handlers_returns_default_descriptions():
    """get_component_event_handlers should return descriptions for default triggers."""
    handlers = get_component_event_handlers(Component)
    handlers_by_name = {h.name: h for h in handlers}

    # All default triggers should be present.
    for name in DEFAULT_TRIGGERS_AND_DESC:
        assert name in handlers_by_name, f"Missing default trigger: {name}"
        handler = handlers_by_name[name]
        assert handler.is_inherited is True
        assert handler.description == DEFAULT_TRIGGERS_AND_DESC[name].description


class _ComponentWithCustomTrigger(Component):
    on_custom: EventHandler[no_args_event_spec] = field(
        doc="Custom event fired on test."
    )

    @classmethod
    def create(cls, *children, **props):
        return super().create(*children, **props)


def test_custom_trigger_description_not_overridden():
    """Component-defined event handler docs should take priority over DEFAULT_TRIGGERS."""
    handlers = get_component_event_handlers(_ComponentWithCustomTrigger)
    handlers_by_name = {h.name: h for h in handlers}

    # Custom trigger should use its own doc.
    custom = handlers_by_name["on_custom"]
    assert custom.description == "Custom event fired on test."
    assert custom.is_inherited is False

    # Default triggers should still have their descriptions.
    click = handlers_by_name[EventTriggers.ON_CLICK]
    assert click.is_inherited is True
    assert click.description is not None
    assert "clicks" in click.description.lower()


class _DocumentedComponent(Component):
    """A component with a docstring for testing."""


class _UndocumentedComponent(Component):
    pass


def test_description_from_docstring():
    """generate_documentation should populate description from __doc__."""
    doc = generate_documentation(_DocumentedComponent)
    assert doc.description == _DocumentedComponent.__doc__


def test_description_none_when_no_docstring():
    """generate_documentation should set description to None when __doc__ is None."""
    doc = generate_documentation(_UndocumentedComponent)
    assert doc.description is None


# ---------------------------------------------------------------------------
# Tests for generate_class_documentation
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _SampleDataclass:
    """A sample dataclass for testing.

    Attributes:
        name: The name of the item.
        items: A list of items.
    """

    name: str = "default"
    count: int = 5
    items: list[str] = dataclasses.field(default_factory=list)
    _private: str = "hidden"

    def public_method(self) -> None:
        """Do something useful.

        Args:
            None.
        """

    def _private_method(self) -> None:
        """Should not appear."""

    @classmethod
    def class_method(cls, x: int) -> str:
        """A class method.

        Returns:
            A string.
        """
        return str(x)

    @staticmethod
    def static_method(y: int) -> int:
        """A static method.

        Args:
            y: The input.

        Returns:
            The output.
        """
        return y * 2


def test_dataclass_fields_doc_metadata():
    """Docstring Attributes descriptions are extracted for fields."""
    doc = generate_class_documentation(_SampleDataclass)

    fields_by_name = {f.name: f for f in doc.fields}

    # name field: described in docstring Attributes section
    assert "name" in fields_by_name
    name_field = fields_by_name["name"]
    assert name_field.description == "The name of the item."
    assert name_field.type is str
    assert "Annotated" not in name_field.type_display
    assert name_field.type_display == "str"
    assert name_field.default == "'default'"

    # count field: plain int
    assert "count" in fields_by_name
    count_field = fields_by_name["count"]
    assert count_field.description is None
    assert count_field.type is int
    assert count_field.default == "5"

    # items field: described in docstring Attributes section
    assert "items" in fields_by_name
    items_field = fields_by_name["items"]
    assert items_field.description == "A list of items."
    assert "Annotated" not in items_field.type_display


def test_dataclass_private_fields_skipped():
    """Fields starting with _ are excluded."""
    doc = generate_class_documentation(_SampleDataclass)
    field_names = {f.name for f in doc.fields}
    assert "_private" not in field_names


@dataclasses.dataclass
class _DataclassWithPrivateMarker:
    """Test PRIVATE marker in doc.

    Attributes:
        visible: A visible field.
        hidden: PRIVATE: internal use only.
    """

    visible: str = ""
    hidden: str = ""


def test_private_marker_in_doc():
    """Fields with PRIVATE in their doc are excluded."""
    doc = generate_class_documentation(_DataclassWithPrivateMarker)
    field_names = {f.name for f in doc.fields}
    assert "visible" in field_names
    assert "hidden" not in field_names


def test_dataclass_methods():
    """Methods: name, signature, and truncated description are correct."""
    doc = generate_class_documentation(_SampleDataclass)
    methods_by_name = {m.name: m for m in doc.methods}

    # public_method
    assert "public_method" in methods_by_name
    pub = methods_by_name["public_method"]
    assert pub.description == "Do something useful."
    assert "self" in pub.signature

    # class_method
    assert "class_method" in methods_by_name
    cm = methods_by_name["class_method"]
    assert cm.description == "A class method."
    assert "x" in cm.signature

    # static_method
    assert "static_method" in methods_by_name
    sm = methods_by_name["static_method"]
    assert sm.description == "A static method."
    assert "y" in sm.signature

    # _private_method should not appear
    assert "_private_method" not in methods_by_name


def test_dataclass_class_name_and_description():
    """Name matches module.qualname and description matches cleandoc."""
    doc = generate_class_documentation(_SampleDataclass)
    assert doc.name == f"{_SampleDataclass.__module__}.{_SampleDataclass.__qualname__}"
    assert _SampleDataclass.__doc__ is not None
    assert doc.description == inspect.cleandoc(_SampleDataclass.__doc__)


def test_string_annotations_resolve():
    """Classes using from __future__ import annotations still resolve correctly."""
    import reflex as rx

    doc = generate_class_documentation(rx.App)
    # Should have fields (App is a dataclass with many fields)
    assert len(doc.fields) > 0
    # No Annotated should appear in type_display
    for f in doc.fields:
        assert "Annotated" not in f.type_display, (
            f"Annotated in type_display of {f.name}: {f.type_display}"
        )


def test_rx_state_fields():
    """rx.State subclass fields are extracted via __fields__."""
    from reflex.state import BaseState

    doc = generate_class_documentation(BaseState)
    assert len(doc.fields) > 0
    field_names = {f.name for f in doc.fields}
    # Private fields should be excluded
    for name in field_names:
        assert not name.startswith("_")


@pytest.mark.skipif(
    not find_spec("pydantic"),
    reason="pydantic not installed",
)
def test_class_with_class_vars():
    """Class variables are extracted from __class_vars__."""
    from pydantic import BaseModel

    # BaseModel has __class_vars__ (from pydantic)
    doc = generate_class_documentation(BaseModel)
    # Just verify the attribute is populated (may be empty if BaseModel has no class vars)
    assert isinstance(doc.class_fields, tuple)


def test_plain_class_empty_fields():
    """A plain class (not dataclass, not rx.State) returns empty fields."""

    class PlainClass:
        """A plain class."""

        def do_stuff(self) -> None:
            """Do stuff."""

    doc = generate_class_documentation(PlainClass)
    assert doc.fields == ()
    assert doc.class_fields == ()
    assert len(doc.methods) == 1
    assert doc.methods[0].name == "do_stuff"


def test_no_docstring_description_is_none():
    """Classes without docstrings have None description."""

    class NoDoc:
        pass

    doc = generate_class_documentation(NoDoc)
    assert doc.description is None


@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Requires Python 3.14 for dataclass field doc support",
)
def test_field_doc_takes_priority():
    """field.doc takes priority over docstring Attributes section."""

    @dataclasses.dataclass
    class _DataclassWithFieldDoc:
        """Test field.doc attribute priority.

        Attributes:
            name: From docstring.
        """

        name: str = dataclasses.field(default="x", doc="From field.doc")  # ty:ignore[no-matching-overload]

    doc = generate_class_documentation(_DataclassWithFieldDoc)
    fields_by_name = {f.name: f for f in doc.fields}
    assert fields_by_name["name"].description == "From field.doc"
