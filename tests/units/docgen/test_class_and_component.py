"""Tests for reflex-docgen."""

import dataclasses
import inspect
import sys
from collections.abc import Callable
from importlib.util import find_spec
from typing import Any, Literal

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
    format_type,
    generate_class_documentation,
    generate_documentation,
    get_component_event_handlers,
)
from reflex_docgen._class import _format_annotation, _format_signature
from typing_extensions import TypeAliasType


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

    # public_method: self is dropped from the rendered signature
    assert "public_method" in methods_by_name
    pub = methods_by_name["public_method"]
    assert pub.description == "Do something useful."
    assert "self" not in pub.signature
    assert pub.signature == "() -> None"

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

        name: str = dataclasses.field(default="x", doc="From field.doc")

    doc = generate_class_documentation(_DataclassWithFieldDoc)
    fields_by_name = {f.name: f for f in doc.fields}
    assert fields_by_name["name"].description == "From field.doc"


_SampleAlias = TypeAliasType("_SampleAlias", Callable[[int], int])


@pytest.mark.parametrize(
    ("type_", "expected"),
    [
        (str, "str"),
        (None, "None"),
        (type(None), "None"),
        (int | None, "Optional[int]"),
        (int | str, "int | str"),
        (int | str | None, "Optional[int | str]"),
        (list[str], "list[str]"),
        (dict[str, Any], "dict[str, Any]"),
        (dict[str, int | None], "dict[str, Optional[int]]"),
        (Literal["a", "b"], 'Literal["a", "b"]'),
        (Literal[1, True], "Literal[1, True]"),
        (Callable[[int, str], bool], "Callable[[int, str], bool]"),
        (Callable[..., None], "Callable[..., None]"),
        (Callable[[], int] | None, "Optional[Callable[[], int]]"),
        (_SampleAlias, "_SampleAlias"),
        (list[_SampleAlias], "list[_SampleAlias]"),
    ],
)
def test_format_type(type_, expected):
    """format_type renders concise, unqualified type strings."""
    assert format_type(type_) == expected


def test_format_type_strips_module_qualifiers():
    """Module-qualified classes render with their bare name only, with optionality explicit."""
    from reflex_base.components.component import Component

    assert format_type(Component | None) == "Optional[Component]"


def test_format_type_callable_with_paramspec():
    """A Callable parameterized by a ParamSpec renders without crashing."""
    from typing import ParamSpec

    P = ParamSpec("P")
    # Subscript dynamically: a bare ``Callable[P, int]`` has no static meaning
    # with an unbound ParamSpec, but format_type must still render it at runtime.
    callable_ctor: Any = Callable
    assert format_type(callable_ctor[P, int]) == "Callable[P, int]"


def test_api_transformer_type_display_is_readable():
    """The App.api_transformer field renders via its ASGIApp alias, not a fully expanded blob."""
    import reflex as rx

    doc = generate_class_documentation(rx.App)
    api_transformer = next(f for f in doc.fields if f.name == "api_transformer")

    display = api_transformer.type_display
    assert display.startswith("Optional[")
    assert "ASGIApp" in display
    assert "Starlette" in display
    for noise in ("collections.abc", "typing.", "MutableMapping", "Awaitable"):
        assert noise not in display, f"{noise!r} leaked into {display!r}"


def _sample_default_handler() -> None:
    """A module-level callable used as a default value in tests."""


def _sample_list_factory() -> list:
    """A module-level named factory used as a default_factory in tests.

    Returns:
        An empty list.
    """
    return []


@dataclasses.dataclass
class _DataclassWithCallableDefaults:
    """A dataclass whose defaults are callables and factories.

    Attributes:
        handler: A function default.
        items: A list factory default.
        data: A dict factory default.
        built: A named-function factory default.
        made: An opaque (lambda) factory default.
    """

    handler: Callable[[], None] = _sample_default_handler
    items: list = dataclasses.field(default_factory=list)
    data: dict = dataclasses.field(default_factory=dict)
    built: list = dataclasses.field(default_factory=_sample_list_factory)
    made: object = dataclasses.field(default_factory=lambda: object())


def test_callable_and_factory_defaults_are_clean():
    """Callable/factory defaults render as names or empty literals, never volatile reprs."""
    doc = generate_class_documentation(_DataclassWithCallableDefaults)
    defaults = {f.name: f.default for f in doc.fields}

    assert defaults["handler"] == "_sample_default_handler"
    assert defaults["items"] == "[]"
    assert defaults["data"] == "{}"
    # A named factory shows its name so the field reads as having a default.
    assert defaults["built"] == "_sample_list_factory"
    # Opaque factories (lambdas) are omitted rather than shown as <function ... at 0x...>.
    assert defaults["made"] is None


def test_app_field_defaults_have_no_memory_addresses():
    """No App field default leaks a function object repr with a memory address."""
    import reflex as rx

    doc = generate_class_documentation(rx.App)
    for f in doc.fields:
        if f.default is None:
            continue
        assert "0x" not in f.default, f"{f.name} default has an address: {f.default!r}"
        assert "<function" not in f.default
        assert "<bound method" not in f.default

    defaults = {f.name: f.default for f in doc.fields}
    assert (
        defaults["frontend_exception_handler"] == "default_frontend_exception_handler"
    )
    # A factory-backed default is shown (not dropped), so the field reads as optional.
    assert defaults["toaster"] is not None
    assert "<" not in defaults["toaster"]


@dataclasses.dataclass
class _DataclassWithDocumentedCallableField:
    """A dataclass whose field default is a documented function.

    Attributes:
        handler: A callable field whose default has a docstring.
    """

    handler: Callable[[], None] = _sample_default_handler

    def real_method(self) -> None:
        """An actual method that should appear in the methods list."""


def test_callable_field_default_not_listed_as_method():
    """A field whose default is a function is a field, not a method."""
    doc = generate_class_documentation(_DataclassWithDocumentedCallableField)
    field_names = {f.name for f in doc.fields}
    method_names = {m.name for m in doc.methods}

    assert "handler" in field_names
    assert "handler" not in method_names
    assert "real_method" in method_names


def test_app_methods_exclude_fields():
    """App field-defaults that are functions don't leak into the methods table."""
    import dataclasses as dc

    import reflex as rx

    doc = generate_class_documentation(rx.App)
    field_names = {f.name for f in dc.fields(rx.App)}
    method_names = {m.name for m in doc.methods}

    assert not (method_names & field_names), (
        f"fields leaked into methods: {sorted(method_names & field_names)}"
    )
    # The real methods are still present.
    assert {"add_page", "modify_state"} <= method_names


def test_method_signatures_are_readable():
    """Method signatures drop self, unquote annotations, and keep clean defaults."""
    import reflex as rx

    methods = {
        m.name: m.signature for m in generate_class_documentation(rx.App).methods
    }

    add_page = methods["add_page"]
    assert "self" not in add_page
    # Forward-ref annotation strings are unquoted and optionality is explicit...
    assert "route: Optional[str] = None" in add_page
    assert "'str | None'" not in add_page
    assert "component: Optional[Component | ComponentCallable] = None" in add_page
    # Bracketed types wrap correctly, and params without None are left untouched.
    assert "on_load: Optional[EventType[()]] = None" in add_page
    assert "meta: Sequence[Mapping[str, Any] | Component] = []" in add_page
    # ...while genuine string-literal defaults keep their quotes.
    assert "image: str = 'favicon.ico'" in add_page


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        ("str | None", "Optional[str]"),
        ("None | str", "Optional[str]"),
        ("int | None | str", "Optional[int | str]"),
        ("str", "str"),
        ("int | str", "int | str"),
        # None nested inside a subscript is not top-level optionality.
        ("Callable[[int], None]", "Callable[[int], None]"),
        ("dict[str, int | None]", "dict[str, int | None]"),
        ("EventType[()] | None", "Optional[EventType[()]]"),
        # An unresolvable forward-ref name is preserved verbatim.
        ("SomeAlias | None", "Optional[SomeAlias]"),
    ],
)
def test_format_annotation_from_string(annotation, expected):
    """Forward-ref unions normalize to Optional[...] wherever None sits, top-level only."""
    assert _format_annotation(annotation) == expected


def test_signature_renders_each_annotation_independently():
    """One unresolvable forward-ref annotation doesn't poison the rest of the signature."""

    def fn(resolvable, unresolvable, plain): ...

    # Forward-ref strings (as produced by ``from __future__ import annotations``);
    # ``Missing`` is a TYPE_CHECKING-only name that cannot be resolved.
    fn.__annotations__ = {
        "resolvable": "int | None",
        "unresolvable": "str | Missing | None",
        "plain": "list[str]",
        "return": "Missing | None",
    }

    assert _format_signature(fn) == (
        "(resolvable: Optional[int], "
        "unresolvable: Optional[str | Missing], "
        "plain: list[str]) -> Optional[Missing]"
    )


def test_signature_strips_module_qualifiers_from_forward_refs():
    """Forward-ref annotations get module qualifiers stripped, like resolved types do."""

    def fn(a, b): ...

    fn.__annotations__ = {
        "a": "contextlib.AbstractContextManager | None",
        "b": "Sequence[collections.abc.Mapping]",
        "return": "contextlib.AbstractContextManager",
    }

    assert _format_signature(fn) == (
        "(a: Optional[AbstractContextManager], b: Sequence[Mapping])"
        " -> AbstractContextManager"
    )


def test_signature_qualifier_stripping_is_quote_safe():
    """A dotted value inside a Literal string is not mistaken for a module path."""

    def fn(mode): ...

    fn.__annotations__ = {"mode": 'Literal["a.b.c"] | None'}

    assert _format_signature(fn) == '(mode: Optional[Literal["a.b.c"]])'
