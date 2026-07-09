"""Tests for rx.memo support."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest
from reflex_base.components.component import Component
from reflex_base.components.memo import (
    _SPECS,
    EMPTY_VAR_COMPONENT,
    MEMOS,
    MemoComponent,
    MemoComponentDefinition,
    MemoFunctionDefinition,
    MemoParam,
    MemoParamKind,
    _analyze_params,
    _LazyBody,
    _MemoCallBinding,
    _strip_optional,
)
from reflex_base.event import EventChain, EventHandler, no_args_event_spec
from reflex_base.style import Style
from reflex_base.utils import console, memo_paths
from reflex_base.utils import format as format_utils
from reflex_base.utils.exceptions import ReflexError
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData
from reflex_base.vars.base import Var
from reflex_base.vars.function import FunctionVar

import reflex as rx
from reflex.compiler import compiler
from reflex.compiler import utils as compiler_utils


@pytest.fixture(autouse=True)
def _restore_memo_registries(preserve_memo_registries):
    """Autouse wrapper around the shared preserve_memo_registries fixture."""


def test_var_returning_memo():
    """Var-returning memos should behave like imported function vars."""

    @rx.memo
    def format_price(amount: rx.Var[int], currency: rx.Var[str]) -> rx.Var[str]:
        return currency.to(str) + ": $" + amount.to(str)

    price = Var(_js_expr="price", _var_type=int)
    currency = Var(_js_expr="currency", _var_type=str)

    sym = memo_paths.mirrored_symbol("format_price", __name__)
    assert (
        str(format_price(amount=price, currency=currency))
        == f"({sym}(price, currency))"
    )
    assert (
        str(format_price.call(amount=price, currency=currency))
        == f"({sym}(price, currency))"
    )
    assert isinstance(format_price._as_var(), FunctionVar)

    definition = MEMOS["format_price", __name__]
    assert isinstance(definition, MemoFunctionDefinition)
    assert (
        str(definition.function) == '((amount, currency) => ((currency+": $")+amount))'
    )

    with pytest.raises(TypeError, match="only accepts keyword props"):
        format_price(price, currency)


def test_component_returning_memo_with_children_and_rest():
    """Component-returning memos should accept positional children and forwarded props."""

    @rx.memo
    def my_card(
        children: rx.Var[rx.Component],
        rest: rx.RestProp,
        *,
        title: rx.Var[str],
    ) -> rx.Component:
        return rx.box(
            rx.heading(title),
            children,
            rest,
        )

    component = my_card(
        rx.text("child 1"),
        rx.text("child 2"),
        title="Hello",
        foo="extra",
        class_name="extra",
    )
    component_again = my_card(title="World")

    sym = memo_paths.mirrored_symbol("MyCard", __name__)
    assert isinstance(component, MemoComponent)
    assert len(component.children) == 2
    assert component.get_props() == ("title", "foo")
    assert type(component) is type(component_again)
    assert type(component).tag == sym
    assert type(component).get_fields()["tag"].default == sym

    rendered = component.render()
    assert rendered["name"] == sym
    assert 'title:"Hello"' in rendered["props"]
    assert 'foo:"extra"' in rendered["props"]
    assert 'className:"extra"' in rendered["props"]

    definition = MEMOS["MyCard", __name__]
    assert isinstance(definition, MemoComponentDefinition)
    assert any(str(prop) == "rest" for prop in definition.component.special_props)

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert f"export const {sym} = memo(" in code
    assert "({children, title:title" in code
    assert "...rest" in code
    assert "jsx(RadixThemesBox,{...rest}" in code


def test_component_returning_memo_accepts_component_var_result():
    """Component-returning memos should accept component-typed var results."""

    @rx.memo
    def conditional_slot(
        show: rx.Var[bool],
        first: rx.Var[rx.Component],
        second: rx.Var[rx.Component],
    ) -> rx.Var[rx.Component]:
        return rx.cond(show, first, second)

    definition = MEMOS["ConditionalSlot", __name__]
    assert isinstance(definition, MemoComponentDefinition)
    assert definition.component.render() == {
        "contents": "(showRxMemo ? firstRxMemo : secondRxMemo)"
    }

    sym = memo_paths.mirrored_symbol("ConditionalSlot", __name__)
    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert f"export const {sym} = memo(" in code
    assert "({show:showRxMemo" in code
    assert "(showRxMemo ? firstRxMemo : secondRxMemo)" in code


def test_var_returning_memo_with_rest_props():
    """Var-returning memos should capture extra keyword args into RestProp."""

    @rx.memo
    def merge_styles(
        base: rx.Var[dict[str, str]],
        overrides: rx.RestProp,
    ) -> rx.Var[Any]:
        return base.to(dict).merge(overrides)

    base = Var(_js_expr="base", _var_type=dict[str, str])
    merged = merge_styles(base=base, color="red", class_name="primary")

    assert "merge_styles" in str(merged)
    assert '["base"] : base' in str(merged)
    assert '["color"] : "red"' in str(merged)
    assert '["className"] : "primary"' in str(merged)

    sym = memo_paths.mirrored_symbol("merge_styles", __name__)
    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert (
        f"export const {sym} = (({{base, ...overrides}}) => ({{...base, ...overrides}}));"
        in code
    )

    with pytest.raises(TypeError, match="Do not pass `overrides=` directly"):
        merge_styles(base=base, overrides={"color": "red"})


def test_component_returning_memo_with_only_rest():
    """Component-returning memos with only RestProp should emit valid JSX (#6443)."""

    @rx.memo
    def hover_trigger(rest: rx.RestProp) -> rx.Component:
        return rx.text("hover me", rest)

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert "memo(({...rest})" in code
    assert "({," not in code


def test_component_memo_rest_prop_merge_is_forwarded_as_rest_prop():
    """A merged ``RestProp`` stays a ``RestProp``.

    Passing ``rest.merge({...})`` to another component must lift it onto that
    component's ``special_props`` (a JSX spread), exactly like the bare ``rest``
    — not render it as a literal child.
    """

    @rx.memo
    def primary_button(rest: rx.RestProp, *, label: rx.Var[str]) -> rx.Component:
        return rx.button(label, rest.merge({"className": "btn"}))

    definition = MEMOS["PrimaryButton", __name__]
    assert isinstance(definition, MemoComponentDefinition)

    # The merged value is accepted as a RestProp: lifted onto special_props
    # rather than wrapped as a child.
    merged_specials = [
        prop
        for prop in definition.component.special_props
        if isinstance(prop, rx.RestProp)
    ]
    assert len(merged_specials) == 1
    assert "...rest" in str(merged_specials[0])

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    # Spread into the button props, not emitted as a jsx child.
    assert '{...({...rest, ...({ ["className"] : "btn" })})}' in code


def test_var_returning_memo_with_only_rest():
    """Var-returning memos with only RestProp should emit valid JS (#6443)."""

    @rx.memo
    def merge_only(overrides: rx.RestProp) -> rx.Var[Any]:
        return overrides

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert "(({...overrides}) => overrides)" in code
    assert "({," not in code


def test_var_returning_memo_with_children_and_rest():
    """Var-returning memos should accept positional children plus keyword props."""

    @rx.memo
    def label_slot(
        children: rx.Var[rx.Component],
        rest: rx.RestProp,
        *,
        label: rx.Var[str],
    ) -> rx.Var[str]:
        return label

    rendered = label_slot(
        rx.text("child"),
        label="Hello",
        class_name="slot",
    )

    assert "label_slot" in str(rendered)
    assert '["children"]' in str(rendered)
    assert '["className"] : "slot"' in str(rendered)

    sym = memo_paths.mirrored_symbol("label_slot", __name__)
    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert f"export const {sym} = (({{children, label, ...rest}}) => label);" in code


def test_memo_munges_legacy_bare_type_param():
    """Legacy bare-type params should coerce to ``rx.Var[...]`` with a warning."""
    with patch.object(console, "deprecate") as mock_deprecate:

        @rx.memo
        def bad_annotation(value: int) -> rx.Var[str]:
            return rx.Var.create("x")

    mock_deprecate.assert_called_once()
    kwargs = mock_deprecate.call_args.kwargs
    assert "bad_annotation" in kwargs["feature_name"]
    assert "`value`" in kwargs["reason"]

    definition = MEMOS["bad_annotation", __name__]
    assert isinstance(definition, MemoFunctionDefinition)
    (value_param,) = definition.params
    assert value_param.kind is MemoParamKind.VALUE
    # The bare ``int`` annotation is coerced into ``Var[int]``.
    assert value_param.annotation == rx.Var[int]


def test_memo_munges_legacy_bare_type_params_for_component():
    """Component memos coerce legacy bare-type params and keep their defaults."""
    with patch.object(console, "deprecate") as mock_deprecate:

        @rx.memo
        def legacy_card(title: str, count: int = 3) -> rx.Component:
            return rx.box(rx.heading(title), rx.text(count))

    mock_deprecate.assert_called_once()
    reason = mock_deprecate.call_args.kwargs["reason"]
    assert "`title`" in reason
    assert "`count`" in reason

    definition = MEMOS["LegacyCard", __name__]
    assert isinstance(definition, MemoComponentDefinition)
    assert {p.name: p.kind for p in definition.params} == {
        "title": MemoParamKind.VALUE,
        "count": MemoParamKind.VALUE,
    }
    count_param = next(p for p in definition.params if p.name == "count")
    assert count_param.default == 3

    # The munged props bind at instantiation; ``count`` falls back to its default.
    component = legacy_card(title="Hi")
    assert isinstance(component, MemoComponent)


def test_memo_does_not_warn_for_event_handler_param():
    """``rx.EventHandler`` params are recognized and must not be munged/warned."""
    with patch.object(console, "deprecate") as mock_deprecate:

        @rx.memo
        def eh_only(event: rx.EventHandler) -> rx.Component:
            return rx.button("click", on_click=event())

    mock_deprecate.assert_not_called()


def test_memo_component_forwards_key_without_rest():
    """``key`` passes through a ``RestProp``-less memo and reaches the element.

    ``key`` is the one base ``Component`` prop that takes effect without an
    ``rx.RestProp``: React consumes it at the reconciliation layer, so the
    legacy custom-component use case (notably setting ``key`` under
    ``rx.foreach``) keeps working. It is set as a real base field while a
    deprecation warning points at ``rx.RestProp``. Props that only matter once
    spread onto the rendered root (``id``, ``class_name``, ...) are *not*
    forwardable here — see ``test_memo_nonkey_base_props_require_rest_prop``.
    """

    @rx.memo
    def keyed_card(title: rx.Var[str]) -> rx.Component:
        return rx.text(title)

    with patch.object(console, "deprecate") as mock_deprecate:
        component = keyed_card(title="hi", key="row-1")

    mock_deprecate.assert_called_once()
    feature_name = mock_deprecate.call_args.kwargs["feature_name"]
    assert "keyed_card" in feature_name
    assert "`key`" in feature_name

    assert isinstance(component, MemoComponent)
    # ``key`` lands as a real base field, not as a declared memo prop ...
    assert component.key == "row-1"
    assert component.get_props() == ("title",)
    # ... and reaches the rendered element, where React reads it for list
    # reconciliation.
    assert 'key:"row-1"' in component.render()["props"]


def test_memo_component_key_deprecation_warns_once_across_instances():
    """Repeated ``key=`` instantiations warn once, without re-walking the stack.

    Under ``rx.foreach`` a keyed memo is instantiated once per row. The warning
    is deduped, but ``console.deprecate`` walks and path-resolves the call stack
    *before* its dedupe check, so an ungated call site would pay that walk on
    every row. The wrapper gates the call so only the first row reaches
    ``console.deprecate`` at all.
    """

    @rx.memo
    def row_card(title: rx.Var[str]) -> rx.Component:
        return rx.text(title)

    with patch.object(console, "deprecate") as mock_deprecate:
        for i in range(5):
            row_card(title="hi", key=f"row-{i}")

    mock_deprecate.assert_called_once()


def test_memo_nonkey_base_props_require_rest_prop():
    """Non-``key`` base props raise without a ``RestProp`` rather than silently dropping.

    Without a ``RestProp`` the compiled memo function destructures only its
    declared params and emits no ``...rest`` spread, so ``id``/``class_name``/
    ``style``/``custom_attrs``/``ref`` set on the wrapper never reach the
    rendered root — they would be silently discarded. Reject them and point at
    ``rx.RestProp``, which genuinely forwards them (see
    ``test_memo_base_props_forward_to_root_via_rest_prop``).
    """

    @rx.memo
    def plain_card(title: rx.Var[str]) -> rx.Component:
        return rx.text(title)

    for prop, value in (
        ("id", "card-id"),
        ("class_name", "c"),
        ("style", {"color": "red"}),
        ("custom_attrs", {"data-x": "y"}),
        ("ref", "myref"),
    ):
        with pytest.raises(TypeError, match=f"does not accept prop `{prop}`"):
            plain_card(title="hi", **{prop: value})


def test_memo_nonkey_base_prop_dropped_from_render_without_rest():
    """Guard the *reason* non-``key`` base props are rejected: they don't render.

    Bypass the call-site gate by setting ``class_name`` directly on a built memo
    wrapper, then compile. The base prop shows up on the page-level element but
    the memo's own function body neither destructures nor spreads it onto the
    root — proving a ``RestProp``-less memo cannot forward it, which is why the
    call site rejects it.
    """

    @rx.memo
    def dropper(title: rx.Var[str]) -> rx.Component:
        return rx.box(rx.text(title))

    component = dropper(title="hi")
    component.class_name = Var.create("leaks")  # set past the call-site gate

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    segments = memo_paths.module_to_mirrored_segments(__name__)
    assert segments is not None
    exp_path = compiler_utils.get_memo_module_path(segments)
    code = next(c for path, c in files if path == exp_path)
    # No rest capture, and the root Box gets an empty props object.
    assert "...rest" not in code
    assert "className" not in code


def test_memo_base_props_forward_to_root_via_rest_prop():
    """With an ``rx.RestProp``, base props reach the rendered root via JS ``...rest``.

    This is the supported forwarding path the rejection message points users at.
    """

    @rx.memo
    def rest_card(rest: rx.RestProp, *, title: rx.Var[str]) -> rx.Component:
        return rx.box(rx.text(title), rest)

    component = rest_card(title="hi", class_name="c", id="card-id")
    assert isinstance(component, MemoComponent)

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    segments = memo_paths.module_to_mirrored_segments(__name__)
    assert segments is not None
    exp_path = compiler_utils.get_memo_module_path(segments)
    code = next(c for path, c in files if path == exp_path)
    # Undeclared props are captured in ``...rest`` and spread onto the root, so
    # ``className``/``id`` actually reach the rendered element.
    assert "...rest" in code
    assert "{...rest}" in code


def test_memo_component_still_rejects_unknown_props_without_rest():
    """Props that are not base ``Component`` fields still raise without a ``RestProp``."""

    @rx.memo
    def plain_card(title: rx.Var[str]) -> rx.Component:
        return rx.text(title)

    with pytest.raises(TypeError, match="does not accept prop `bogus`"):
        plain_card(title="hi", bogus="x")


def test_memo_component_rejects_unknown_even_alongside_base_props():
    """A genuinely-unknown prop raises even when a base prop is also present."""

    @rx.memo
    def mixed_card(title: rx.Var[str]) -> rx.Component:
        return rx.text(title)

    with pytest.raises(TypeError, match="does not accept prop `bogus`"):
        mixed_card(title="hi", key="row-1", bogus="x")


def test_memo_component_rejects_structural_base_fields_without_rest():
    """Identity/internal base fields (``tag``, ``library``, ...) are not forwardable.

    Overriding them would corrupt the memo's render, so they keep raising like
    any other unknown prop rather than passing through.
    """

    @rx.memo
    def struct_card(title: rx.Var[str]) -> rx.Component:
        return rx.text(title)

    for prop in ("tag", "library", "event_triggers", "special_props"):
        with pytest.raises(TypeError, match=f"does not accept prop `{prop}`"):
            struct_card(title="hi", **{prop: "x"})


def test_analyze_params_strict_mode_rejects_bare_type():
    """Strict callers (``defaulted_params=None``) must still reject bare types."""

    def bare(value: int) -> rx.Component:
        return rx.text("x")

    with pytest.raises(TypeError, match="must be annotated"):
        _analyze_params(bare, for_component=True)


def test_is_memo_annotation_recognizes_supported_kinds():
    """``_is_memo_annotation`` gates which annotations are coerced to ``Var``."""
    from reflex_base.components.memo import _is_memo_annotation

    assert _is_memo_annotation(rx.Var[int]) is True
    assert _is_memo_annotation(rx.RestProp) is True
    assert _is_memo_annotation(rx.EventHandler) is True
    assert (
        _is_memo_annotation(rx.EventHandler[rx.event.passthrough_event_spec(str)])
        is True
    )
    # Legacy bare types are not recognized -> they get munged + warned.
    assert _is_memo_annotation(int) is False
    assert _is_memo_annotation(str) is False
    assert _is_memo_annotation(list[str]) is False


def test_memo_warns_on_missing_param_annotation():
    """Unannotated parameters should fall back to ``rx.Var[Any]`` with a warning."""
    with patch.object(console, "deprecate") as mock_deprecate:

        @rx.memo
        def soft_missing(value) -> rx.Component:
            return rx.text(value.to(str))

    mock_deprecate.assert_called_once()
    kwargs = mock_deprecate.call_args.kwargs
    assert "soft_missing" in kwargs["feature_name"]
    assert "`value`" in kwargs["reason"]


def test_memo_warns_on_missing_return_annotation():
    """A missing return annotation should default to ``rx.Component`` with a warning."""
    with patch.object(console, "deprecate") as mock_deprecate:

        @rx.memo
        def soft_return():
            return rx.box()

    mock_deprecate.assert_called_once()
    kwargs = mock_deprecate.call_args.kwargs
    assert "soft_return" in kwargs["feature_name"]
    assert "return annotation" in kwargs["reason"]


def test_memo_warning_suggests_component_return():
    """A missing return annotation warns with a constant `-> rx.Component` hint.

    The suggestion no longer inspects the body's return value, so the warning
    fires eagerly at decoration time even though the body itself runs lazily.
    """
    evaluated = []
    with patch.object(console, "deprecate") as mock_deprecate:

        @rx.memo
        def fragment_memo():
            evaluated.append(1)
            return rx.fragment(rx.text("x"))

    mock_deprecate.assert_called_once()
    reason = mock_deprecate.call_args.kwargs["reason"]
    assert "-> rx.Component" in reason
    # Emitting the warning did not require evaluating the body.
    assert evaluated == []


def test_memo_component_body_not_evaluated_until_used():
    """A component memo's body must not run until the wrapper is instantiated."""
    evaluated = []

    @rx.memo
    def lazy_box(value: rx.Var[str]) -> rx.Component:
        evaluated.append(1)
        return rx.box(value)

    # Decoration registers the memo without running the body.
    assert ("LazyBox", __name__) in MEMOS
    assert evaluated == []

    # First instantiation triggers a single evaluation...
    component = lazy_box(value="hi")
    assert isinstance(component, MemoComponent)
    assert evaluated == [1]

    # ...and subsequent uses reuse the cached body.
    lazy_box(value="bye")
    assert evaluated == [1]


def test_memo_function_body_not_evaluated_until_compiled():
    """A var memo's body must not run at decoration or when merely called."""
    evaluated = []

    @rx.memo
    def lazy_join(value: rx.Var[str]) -> rx.Var[str]:
        evaluated.append(1)
        return value

    assert ("lazy_join", __name__) in MEMOS
    assert evaluated == []

    # Calling a function memo references the imported var, not the body.
    lazy_join(value=Var(_js_expr="x", _var_type=str))
    assert evaluated == []

    # The compiler (reading ``.function``) triggers a single evaluation.
    definition = MEMOS["lazy_join", __name__]
    assert isinstance(definition, MemoFunctionDefinition)
    _ = definition.function
    assert evaluated == [1]
    _ = definition.function
    assert evaluated == [1]


def test_lazy_body_placeholder_stands_in_for_reentrant_read():
    """A re-entrant read returns the placeholder, then caches the real body."""
    cell: _LazyBody[str]
    seen = []

    def thunk() -> str:
        seen.append(cell.get())  # re-enters while the thunk is running
        return "real"

    cell = _LazyBody(thunk, placeholder="placeholder")
    assert cell.get() == "real"
    assert seen == ["placeholder"]
    # Cached afterwards; the thunk does not run again (``seen`` stays unchanged).
    assert cell.get() == "real"
    assert seen == ["placeholder"]


def test_lazy_body_reentrant_read_without_placeholder_raises():
    """A placeholder-less body that re-enters its own evaluation fails loudly."""
    cell: _LazyBody[str]

    def thunk() -> str:
        return cell.get()

    cell = _LazyBody(thunk)
    with pytest.raises(RuntimeError, match="Re-entrant"):
        cell.get()


@pytest.mark.parametrize(
    ("attr_name", "expected_type", "expected_render"),
    [
        ("EMPTY_VAR_STR", str, '""'),
        ("EMPTY_VAR_INT", int, "0"),
        ("EMPTY_VAR_COMPONENT", Component, "(jsx(Fragment, ({})))"),
    ],
)
def test_empty_var_sentinels_are_public_typed_vars(
    attr_name: str, expected_type: type, expected_render: str
):
    """`rx.EMPTY_VAR_*` defaults are public, correctly-typed empty Vars.

    These back the documented `rx.Var[...]` memo prop defaults;
    `EMPTY_VAR_COMPONENT` lives in `memo` (not `component`) to avoid a circular
    import, but must still be reachable as `rx.EMPTY_VAR_COMPONENT`.
    """
    sentinel = getattr(rx, attr_name)
    assert isinstance(sentinel, Var)
    assert sentinel._var_type is expected_type
    assert str(sentinel) == expected_render


def test_empty_var_component_default_for_memo_children_slot():
    """`EMPTY_VAR_COMPONENT` works as the default for a memo `children` slot."""

    @rx.memo
    def slot(
        children: rx.Var[rx.Component] = EMPTY_VAR_COMPONENT,
    ) -> rx.Component:
        return rx.box(children)

    # Omitting children falls back to the empty-component default.
    assert isinstance(slot(), MemoComponent)
    assert isinstance(slot(rx.text("hi")), MemoComponent)


def test_memo_warns_once_when_return_and_param_both_missing():
    """A function missing both should emit a single combined warning."""
    with patch.object(console, "deprecate") as mock_deprecate:

        @rx.memo
        def soft_both(value):
            return rx.text(value.to(str))

    mock_deprecate.assert_called_once()
    reason = mock_deprecate.call_args.kwargs["reason"]
    assert "return annotation" in reason
    assert "`value`" in reason


def test_memo_defaults_children_to_var_component():
    """An unannotated ``children`` parameter must default to ``Var[Component]``.

    ``Var[Any]`` would fail the children-name validation in ``_analyze_params``;
    this guards the name-based special case.
    """
    with patch.object(console, "deprecate") as mock_deprecate:

        @rx.memo
        def soft_children(children) -> rx.Component:
            return rx.box(children)

    mock_deprecate.assert_called_once()

    definition = MEMOS["SoftChildren", __name__]
    assert isinstance(definition, MemoComponentDefinition)
    (children_param,) = definition.params
    assert children_param.name == "children"
    assert children_param.kind is MemoParamKind.CHILDREN


def test_memo_does_not_warn_when_fully_annotated():
    """Fully-annotated memos must not trigger the deprecation fallback."""
    with patch.object(console, "deprecate") as mock_deprecate:

        @rx.memo
        def fully_typed(value: rx.Var[str]) -> rx.Component:
            return rx.text(value)

    mock_deprecate.assert_not_called()


def test_analyze_params_strict_mode_still_raises():
    """Internal callers (``defaulted_params=None``) must keep the strict contract."""

    def missing_annotation(value) -> rx.Component:
        return rx.text("x")

    with pytest.raises(TypeError, match="Missing annotation"):
        _analyze_params(missing_annotation, for_component=True)


def test_memo_rejects_invalid_children_annotation():
    """Component memos should validate the special children annotation."""
    with pytest.raises(TypeError, match="children"):

        @rx.memo
        def bad_children(children: rx.Var[str]) -> rx.Component:
            return rx.text(children)


def test_memo_rejects_multiple_rest_props():
    """Experimental memos should only allow a single RestProp."""
    with pytest.raises(TypeError, match="only supports one"):

        @rx.memo
        def too_many_rest(
            first: rx.RestProp,
            second: rx.RestProp,
        ) -> rx.Var[Any]:
            return first


def test_memo_rejects_component_and_function_name_collision():
    """Experimental memos should reject same exported name across kinds."""

    @rx.memo
    def foo_bar() -> rx.Component:
        return rx.box()

    assert ("FooBar", __name__) in MEMOS

    with pytest.raises(ValueError, match=r"name collision.*FooBar"):

        @rx.memo
        def FooBar() -> rx.Var[str]:
            return rx.Var.create("x")


def test_memo_rejects_component_export_name_collision():
    """Experimental memos should reject duplicate component export names."""

    @rx.memo
    def foo_bar() -> rx.Component:
        return rx.box()

    with pytest.raises(ValueError, match=r"name collision.*FooBar"):

        @rx.memo
        def foo__bar() -> rx.Component:
            return rx.box()


def test_same_module_same_name_shadow_is_last_wins():
    """Two memos sharing a name in one module: the later definition wins.

    This is plain Python shadowing — a second ``def`` of the same name rebinds
    the module global — and the registry follows suit rather than erroring,
    because a genuine shadow is indistinguishable from a hot-reload
    re-registration (same type/python_name/module/qualname). The factory builds
    two distinct function objects with identical identity metadata, exactly as
    two module-level ``def shadow`` would.
    """

    def _make_shadow(marker: str):
        def shadow() -> rx.Component:
            return rx.text(marker)

        return shadow

    rx.memo(_make_shadow("first-shadow-body"))
    rx.memo(_make_shadow("second-shadow-body"))

    shadow_keys = [k for k in MEMOS if isinstance(k, tuple) and k[0] == "Shadow"]
    assert len(shadow_keys) == 1

    definition = MEMOS["Shadow", __name__]
    files, _ = compiler.compile_memo_components((definition,))
    code = "\n".join(c for _, c in files)
    assert "second-shadow-body" in code
    assert "first-shadow-body" not in code


def test_memo_rejects_varargs():
    """Experimental memos should reject *args and **kwargs."""
    with pytest.raises(TypeError, match=r"\*args"):

        @rx.memo
        def bad_args(*values: rx.Var[str]) -> rx.Var[str]:
            return rx.Var.create("x")

    with pytest.raises(TypeError, match=r"\*\*kwargs"):

        @rx.memo
        def bad_kwargs(**values: rx.Var[str]) -> rx.Var[str]:
            return rx.Var.create("x")


def test_component_memo_rejects_invalid_positional_usage():
    """Component memos should only accept positional children."""

    @rx.memo
    def title_card(*, title: rx.Var[str]) -> rx.Component:
        return rx.box(rx.heading(title))

    with pytest.raises(TypeError, match="only accepts keyword props"):
        title_card(rx.text("child"))

    @rx.memo
    def child_card(
        children: rx.Var[rx.Component], *, title: rx.Var[str]
    ) -> rx.Component:
        return rx.box(rx.heading(title), children)

    with pytest.raises(TypeError, match="only accepts positional children"):
        child_card("not a component", title="Hello")


def test_var_memo_rejects_invalid_positional_usage():
    """Var memos should also reserve positional arguments for children only."""

    @rx.memo
    def format_price(amount: rx.Var[int], currency: rx.Var[str]) -> rx.Var[str]:
        return currency.to(str) + ": $" + amount.to(str)

    price = Var(_js_expr="price", _var_type=int)
    currency = Var(_js_expr="currency", _var_type=str)

    with pytest.raises(TypeError, match="only accepts keyword props"):
        format_price(price, currency)

    @rx.memo
    def child_label(
        children: rx.Var[rx.Component], *, label: rx.Var[str]
    ) -> rx.Var[str]:
        return label

    with pytest.raises(TypeError, match="only accepts positional children"):
        child_label("not a component", label="Hello")


def test_var_returning_memo_rejects_hooks():
    """Var-returning memos should reject hook-bearing expressions (lazily)."""

    @rx.memo
    def bad_hook(value: rx.Var[str]) -> rx.Var[str]:
        return Var(
            _js_expr="value",
            _var_type=str,
            _var_data=VarData(hooks={"const badHook = 1": None}),
        )

    # Decoration defers the body; reading ``.function`` surfaces the error.
    definition = MEMOS["bad_hook", __name__]
    assert isinstance(definition, MemoFunctionDefinition)
    with pytest.raises(TypeError, match="cannot depend on hooks"):
        _ = definition.function


def test_var_returning_memo_rejects_non_bundled_imports():
    """Var-returning memos should reject non-bundled imports (lazily)."""

    @rx.memo
    def bad_import(value: rx.Var[str]) -> rx.Var[str]:
        return Var(
            _js_expr="value",
            _var_type=str,
            _var_data=VarData(imports={"some-lib": [ImportVar(tag="x")]}),
        )

    # Decoration defers the body; reading ``.function`` surfaces the error.
    definition = MEMOS["bad_import", __name__]
    assert isinstance(definition, MemoFunctionDefinition)
    with pytest.raises(TypeError, match="not bundled"):
        _ = definition.function


def test_compile_memo_components_includes_functions_and_components():
    """The shared memo output should include both function and component memos."""

    @rx.memo
    def text_wrapper(title: rx.Var[str]) -> rx.Component:
        return rx.text(title)

    @rx.memo
    def format_price(amount: rx.Var[int], currency: rx.Var[str]) -> rx.Var[str]:
        return currency.to(str) + ": $" + amount.to(str)

    @rx.memo
    def my_card(children: rx.Var[rx.Component], *, title: rx.Var[str]) -> rx.Component:
        return rx.box(rx.heading(title), children)

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)

    text_wrapper_sym = memo_paths.mirrored_symbol("TextWrapper", __name__)
    format_price_sym = memo_paths.mirrored_symbol("format_price", __name__)
    my_card_sym = memo_paths.mirrored_symbol("MyCard", __name__)
    assert f"export const {text_wrapper_sym} = memo(" in code
    assert f"export const {format_price_sym} =" in code
    assert f"export const {my_card_sym} = memo(" in code


def test_compile_memo_components_groups_by_source_module():
    """Memos sharing a source module are concatenated into one mirrored file."""

    @rx.memo
    def grouped_first(title: rx.Var[str]) -> rx.Component:
        return rx.text(title)

    @rx.memo
    def grouped_second(title: rx.Var[str]) -> rx.Component:
        return rx.heading(title)

    definition = MEMOS["GroupedFirst", __name__]
    assert definition.source_module is not None
    segments = memo_paths.module_to_mirrored_segments(definition.source_module)
    assert segments is not None

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    exp_path = compiler_utils.get_memo_module_path(segments)

    grouped_files = [(path, code) for path, code in files if path == exp_path]
    assert len(grouped_files) == 1
    code = grouped_files[0][1]
    first_sym = memo_paths.mirrored_symbol("GroupedFirst", __name__)
    second_sym = memo_paths.mirrored_symbol("GroupedSecond", __name__)
    assert f"export const {first_sym} = memo(" in code
    assert f"export const {second_sym} = memo(" in code
    # The merged module must carry imports its memos use, not just the
    # framework-level ones added by the compiler.
    assert "RadixThemesText" in code
    assert "RadixThemesHeading" in code


def test_compile_memo_components_falls_back_when_no_source_module():
    """Memos with no source module emit to the legacy per-name path."""
    legacy_definition = MemoComponentDefinition(
        fn=lambda: None,
        python_name="legacy_memo",
        params=(),
        export_name="LegacyMemo",
        _component=_LazyBody.ready(rx.fragment()),
        passthrough_hole_child=None,
    )

    files, _ = compiler.compile_memo_components((legacy_definition,))
    exp_path = compiler._memo_component_file_path(
        compiler_utils.get_memo_components_dir(), "LegacyMemo"
    )
    assert any(path == exp_path for path, _ in files)


def test_compile_memo_components_mirrors_underscore_module_without_error():
    """A module named ``_internal`` mirrors normally — no reserved-name restriction.

    There is no reserved memo output directory anymore, so a developer is free
    to name a package ``_internal``; it simply mirrors to
    ``app_components/_internal/...`` like any other module.
    """
    definition = MemoComponentDefinition(
        fn=lambda: None,
        python_name="thing",
        params=(),
        export_name="Thing",
        _component=_LazyBody.ready(rx.fragment()),
        passthrough_hole_child=None,
        source_module="_internal.widgets",
    )

    files, _ = compiler.compile_memo_components((definition,))
    exp_path = compiler_utils.get_memo_module_path(("_internal", "widgets"))
    assert any(path == exp_path for path, _ in files)


def test_compile_memo_components_rejects_case_insensitive_path_collision():
    """Two modules whose mirrored paths differ only by case fail loudly.

    On case-insensitive filesystems (macOS/Windows) both would resolve to one
    file, silently overwriting one memo module with the other.
    """

    def _definition(export_name: str, source_module: str) -> MemoComponentDefinition:
        return MemoComponentDefinition(
            fn=lambda: None,
            python_name=export_name.lower(),
            params=(),
            export_name=export_name,
            _component=_LazyBody.ready(rx.fragment()),
            passthrough_hole_child=None,
            source_module=source_module,
        )

    with pytest.raises(ReflexError, match="case"):
        compiler.compile_memo_components((
            _definition("Upper", "casecollide.Widget"),
            _definition("Lower", "casecollide.widget"),
        ))


def test_compile_memo_components_extends_imports_without_remerging(
    monkeypatch: pytest.MonkeyPatch,
):
    """Memo import aggregation should not repeatedly reprocess prior imports."""

    def noop() -> None:
        pass

    memos = tuple(
        MemoComponentDefinition(
            fn=noop,
            python_name=f"memo_{idx}",
            params=(),
            export_name=f"Memo{idx}",
            _component=_LazyBody.ready(rx.fragment()),
            passthrough_hole_child=None,
        )
        for idx in range(5)
    )

    def fake_compile_experimental_component_memo(
        definition: MemoComponentDefinition,
    ) -> tuple[dict[str, str], dict[str, list[ImportVar]]]:
        return {"name": definition.export_name}, {}

    def fake_compile_single_memo_component(
        component_render: dict[str, str],
        component_imports: dict[str, list[ImportVar]],
    ) -> tuple[str, dict[str, list[ImportVar]]]:
        return (
            f"export const {component_render['name']} = null",
            {"shared-lib": [ImportVar(tag=component_render["name"])]},
        )

    real_merge_imports = compiler_utils.merge_imports

    def reject_growing_merge(*imports):
        if len(imports) == 2 and imports[0]:
            msg = "aggregate imports should be extended, not remerged"
            raise AssertionError(msg)
        return real_merge_imports(*imports)

    monkeypatch.setattr(
        compiler_utils,
        "compile_experimental_component_memo",
        fake_compile_experimental_component_memo,
    )
    monkeypatch.setattr(
        compiler,
        "_compile_single_memo_component",
        fake_compile_single_memo_component,
    )
    monkeypatch.setattr(compiler_utils, "merge_imports", reject_growing_merge)

    files, aggregate_imports = compiler.compile_memo_components(memos)

    assert len(files) == len(memos)
    assert [import_var.tag for import_var in aggregate_imports["shared-lib"]] == [
        f"Memo{idx}" for idx in range(5)
    ]


def test_experimental_component_memo_get_imports():
    """Experimental component memos should resolve imports during compilation."""

    class Inner(Component):
        tag = "Inner"
        library = "inner"

    @rx.memo
    def wrapper() -> rx.Component:
        return Inner.create()

    experimental_component = wrapper()

    assert "inner" not in experimental_component._get_all_imports()

    definition = MEMOS["Wrapper", __name__]
    assert isinstance(definition, MemoComponentDefinition)
    _, imports = compiler_utils.compile_experimental_component_memo(definition)
    assert "inner" in imports


def test_compile_experimental_component_memo_does_not_mutate_definition(
    monkeypatch: pytest.MonkeyPatch,
):
    """Experimental component memo compilation should not mutate stored components."""

    @rx.memo
    def wrapper() -> rx.Component:
        return rx.box("hi")

    definition = MEMOS["Wrapper", __name__]
    assert isinstance(definition, MemoComponentDefinition)
    # Reading ``.component`` triggers the deferred body evaluation.
    assert definition.component.style == Style()

    monkeypatch.setattr(
        "reflex.utils.prerequisites.get_and_validate_app",
        lambda: SimpleNamespace(
            app=SimpleNamespace(
                style={type(definition.component): Style({"color": "red"})}
            )
        ),
    )

    render, _ = compiler_utils.compile_experimental_component_memo(definition)

    assert render["render"]["props"] == ['css:({ ["color"] : "red" })']
    assert definition.component.style == Style()


def test_component_returning_memo_is_transparent_for_child_validation():
    """Experimental memo wrappers should not break `_valid_parents` checks."""

    class ValidParent(Component):
        tag = "ValidParent"
        library = "valid-parent"

    class RestrictedChild(Component):
        tag = "RestrictedChild"
        library = "restricted-child"
        _valid_parents = ["ValidParent"]

    @rx.memo
    def transparent(children: rx.Var[rx.Component]) -> rx.Component:
        return children  # type: ignore[return-value]

    wrapped_child = transparent(RestrictedChild.create())
    parent = ValidParent.create(wrapped_child)

    assert isinstance(wrapped_child, MemoComponent)
    assert parent.children == [wrapped_child]


def test_compile_memo_components_includes_experimental_custom_code():
    """Experimental component memos should include custom code in compiled output."""

    class FooComponent(rx.Fragment):
        def add_custom_code(self) -> list[str]:
            return [
                "const foo = 'bar'",
            ]

    @rx.memo
    def foo_component(label: rx.Var[str]) -> rx.Component:
        return FooComponent.create(label, rx.Var("foo"))

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)

    assert "const foo = 'bar'" in code


def test_component_memo_accepts_event_handler():
    """Component memos should accept EventHandler params with passthrough specs."""

    @rx.memo
    def eh_memo(
        some_value: rx.Var[str],
        event: rx.EventHandler[rx.event.passthrough_event_spec(str)],
    ) -> rx.Component:
        return rx.vstack(
            rx.button(some_value, on_click=event(some_value)),
            rx.input(on_change=event),
        )

    definition = MEMOS["EhMemo", __name__]
    assert isinstance(definition, MemoComponentDefinition)
    event_param = next(p for p in definition.params if p.name == "event")
    assert event_param.kind is MemoParamKind.EVENT_TRIGGER
    assert event_param.kind_data is not None
    assert event_param.kind_data is not no_args_event_spec


def test_component_memo_accepts_bare_event_handler():
    """Component memos should accept bare EventHandler (no spec) params."""

    @rx.memo
    def bare_eh_memo(event: rx.EventHandler) -> rx.Component:
        return rx.button("click", on_click=event())

    definition = MEMOS["BareEhMemo", __name__]
    assert isinstance(definition, MemoComponentDefinition)
    event_param = next(p for p in definition.params if p.name == "event")
    assert event_param.kind is MemoParamKind.EVENT_TRIGGER
    assert event_param.kind_data is no_args_event_spec


def test_component_memo_event_handler_compiles_to_prop_callback():
    """`event(value)` and `on_change=event` should compile to the destructured JS prop."""

    @rx.memo
    def eh_compile_memo(
        some_value: rx.Var[str],
        event: rx.EventHandler[rx.event.passthrough_event_spec(str)],
    ) -> rx.Component:
        return rx.vstack(
            rx.button(some_value, on_click=event(some_value)),
            rx.input(on_change=event),
        )

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)

    # Signature destructures the EH prop with the RxMemo suffix.
    assert "event:eventRxMemo" in code
    # Partial application: event(some_value) -> eventRxMemo(someValueRxMemo).
    assert "eventRxMemo(someValueRxMemo)" in code
    # Raw pass-through: on_change=event -> eventRxMemo(...input event arg...).
    assert (
        "eventRxMemo(_ev_0)" in code or "eventRxMemo(" in code.split("onChange:", 1)[1]
    )


def test_component_memo_event_handler_wires_event_chain_at_call_site():
    """Instantiating an EH memo should wrap the handler in an EventChain trigger."""

    def _handler_fn(value: str):  # pyright: ignore[reportUnusedFunction]
        pass

    raw_handler = EventHandler(fn=_handler_fn)

    @rx.memo
    def eh_wired_memo(
        some_value: rx.Var[str],
        event: rx.EventHandler[rx.event.passthrough_event_spec(str)],
    ) -> rx.Component:
        return rx.button(some_value, on_click=event(some_value))

    component = eh_wired_memo(some_value="hello", event=raw_handler)
    assert isinstance(component, MemoComponent)
    # EH props live on event_triggers, not in get_props().
    assert "event" not in component.get_props()
    assert "event" in component.event_triggers
    assert isinstance(component.event_triggers["event"], EventChain)


def test_var_returning_memo_rejects_event_handler():
    """Var-returning memos should reject EventHandler params."""
    with pytest.raises(TypeError, match="component-returning"):

        @rx.memo
        def bad_var_eh(
            event: rx.EventHandler[rx.event.passthrough_event_spec(str)],
        ) -> rx.Var[str]:
            return rx.Var.create("x")


def test_component_memo_rejects_event_handler_with_default():
    """EH params should not allow defaults (matches old CustomComponent behavior)."""
    with pytest.raises(TypeError, match="default"):

        @rx.memo
        def bad_eh_default(
            event: rx.EventHandler[rx.event.passthrough_event_spec(str)] = None,  # pyright: ignore[reportArgumentType]
        ) -> rx.Component:
            return rx.button("hi")


def test_strip_optional_unwraps_none_union():
    """`_strip_optional` collapses a ``X | None`` union to ``X``; any other
    annotation passes through unchanged.
    """
    assert _strip_optional(int | None) is int
    var = rx.Var[str]
    assert _strip_optional(var) is var


def test_analyze_params_unwraps_optional_event_handler_default(
    monkeypatch: pytest.MonkeyPatch,
):
    """Regression: on Python 3.10 ``get_type_hints`` rewrites ``event: EH = None``
    to ``Optional[EH]``. With that shim active, ``_analyze_params`` must still see
    the ``EventHandler`` underneath and reject the default (it silently passed on
    3.10 before the fix, since ``Optional[...]`` is not recognized as an EH).

    Force the shim on so this exercises the path on every Python version, not
    only the <=3.10 interpreters that actually wrap the annotation.
    """
    monkeypatch.setattr(
        "reflex_base.components.memo._GET_TYPE_HINTS_WRAPS_NONE_DEFAULT", True
    )

    def fn(event=None) -> rx.Component:
        return rx.button("hi")

    # Python <=3.10 wraps a ``= None`` param into a union with ``None`` (its
    # ``get_type_hints`` adds ``Optional``); the ``EventHandler`` underneath
    # must still be recognized so the default is rejected.
    wrapped_hints = {"event": EventHandler | None}
    with pytest.raises(TypeError, match="default"):
        _analyze_params(fn, for_component=True, hints=wrapped_hints)


def test_component_memo_rejects_event_handler_named_children():
    """A `children` parameter must not be an EventHandler."""
    with pytest.raises(TypeError, match="children"):

        @rx.memo
        def bad_eh_children(
            children: rx.EventHandler[rx.event.passthrough_event_spec(str)],
        ) -> rx.Component:
            return rx.box()


# ---------------------------------------------------------------------------
# Interface-level tests: target the _MemoParamSpec Seam directly.
# These exercise per-kind behavior without going through the @rx.memo decorator,
# giving a tight feedback loop for adding new kinds in the future.
# ---------------------------------------------------------------------------


def _make_param(
    *,
    name: str = "x",
    kind: MemoParamKind,
    annotation: Any = None,
    kind_data: Any = None,
    placeholder_name: str | None = None,
    js_prop_name: str | None = None,
) -> MemoParam:
    """Build a MemoParam directly, bypassing _analyze_params.

    Returns:
        A populated ``MemoParam`` with sensible defaults for tests.
    """
    js = js_prop_name if js_prop_name is not None else format_utils.to_camel_case(name)
    return MemoParam(
        name=name,
        kind=kind,
        kind_data=kind_data,
        annotation=annotation if annotation is not None else rx.Var[int],
        parameter_kind=inspect.Parameter.KEYWORD_ONLY,
        js_prop_name=js,
        placeholder_name=placeholder_name if placeholder_name is not None else name,
    )


def test_classify_routes_each_annotation_to_the_expected_kind():
    """Ordered classification routes each supported annotation to one kind."""
    from reflex_base.components.memo import _classify_parameter

    cases = [
        ("var", rx.Var[int], "x", MemoParamKind.VALUE),
        ("rest", rx.RestProp, "rest", MemoParamKind.REST),
        (
            "event_with_spec",
            rx.EventHandler[rx.event.passthrough_event_spec(str)],
            "event",
            MemoParamKind.EVENT_TRIGGER,
        ),
        ("bare_event", rx.EventHandler, "event", MemoParamKind.EVENT_TRIGGER),
        ("children_var", rx.Var[rx.Component], "children", MemoParamKind.CHILDREN),
        # Var[Component] *not* named children classifies as VALUE — that's the
        # path conditional_slot/component-typed slots take in the existing suite.
        ("named_x_var_component", rx.Var[rx.Component], "x", MemoParamKind.VALUE),
    ]
    for case_name, annotation, param_name, expected in cases:
        kind, _ = _classify_parameter(annotation, param_name, "test_fn")
        assert kind is expected, f"{case_name}: got {kind}, expected {expected}"


def test_classify_value_excludes_rest_independent_of_order():
    """The VALUE classifier must reject RestProp even called in isolation.

    ``_CLASSIFICATION_ORDER`` puts REST before VALUE, but the classifier itself
    is also self-exclusive so a reordering wouldn't silently regress.
    """
    assert _SPECS[MemoParamKind.VALUE].classify(rx.RestProp, "x") == (False, None)
    assert _SPECS[MemoParamKind.VALUE].classify(rx.Var[int], "x") == (True, None)


def test_children_classifier_requires_named_children():
    """CHILDREN is the only name-sensitive kind; verify it gates on the name."""
    spec = _SPECS[MemoParamKind.CHILDREN]
    component_var_annotation = rx.Var[rx.Component]
    assert spec.classify(component_var_annotation, "children")[0] is True
    assert spec.classify(component_var_annotation, "x")[0] is False


def test_value_make_placeholder_returns_typed_var():
    """VALUE kind builds a Var placeholder whose _var_type unwraps the annotation."""
    param = _make_param(
        kind=MemoParamKind.VALUE,
        annotation=rx.Var[int],
        placeholder_name="xRxMemo",
    )
    placeholder = param.make_placeholder()
    assert isinstance(placeholder, Var)
    assert placeholder._js_expr == "xRxMemo"


def test_event_trigger_make_placeholder_returns_plain_callable():
    """EVENT_TRIGGER kind builds a plain callable, not an EventHandler.

    The body's `event(value)` call site must compile to the destructured JS
    prop name, which requires call_event_fn to actually execute the placeholder.
    A synthetic EventHandler(fn=_stub) would bake the Python identifier into
    the rendered ReflexEvent instead.
    """
    spec = rx.event.passthrough_event_spec(str)
    param = _make_param(
        name="event",
        kind=MemoParamKind.EVENT_TRIGGER,
        annotation=rx.EventHandler[spec],
        kind_data=spec,
        placeholder_name="eventRxMemo",
        js_prop_name="event",
    )
    placeholder = param.make_placeholder()
    assert callable(placeholder)
    assert not isinstance(placeholder, EventHandler)

    arg = Var(_js_expr="someValueRxMemo", _var_type=str)
    rendered = str(placeholder(arg))
    assert "eventRxMemo" in rendered
    assert "someValueRxMemo" in rendered


def test_bind_value_routes_to_props():
    """VALUE binding pops the kwarg into binding._props (camelCased)."""
    binding = _MemoCallBinding({"my_value": 42, "other": "x"})
    param = _make_param(name="my_value", kind=MemoParamKind.VALUE)
    param.bind_call_value(binding)

    assert "my_value" not in binding.raw_kwargs
    assert "other" in binding.raw_kwargs  # untouched
    assert binding._props["myValue"]._js_expr == "42"
    assert binding._event_triggers == {}


def test_bind_event_trigger_routes_to_event_triggers():
    """EVENT_TRIGGER binding wraps the value in an EventChain on event_triggers."""

    def _handler(value: str):
        pass

    handler = EventHandler(fn=_handler)
    spec = rx.event.passthrough_event_spec(str)
    binding = _MemoCallBinding({"event": handler})
    param = _make_param(
        name="event",
        kind=MemoParamKind.EVENT_TRIGGER,
        kind_data=spec,
    )

    param.bind_call_value(binding)
    assert "event" not in binding.raw_kwargs
    assert binding._props == {}
    assert isinstance(binding._event_triggers["event"], EventChain)


def test_bind_children_and_rest_are_noops_at_the_param_level():
    """CHILDREN comes in positionally; REST is swept by binding.take_rest."""
    binding = _MemoCallBinding({"children": object(), "extra": 1})
    children_param = _make_param(name="children", kind=MemoParamKind.CHILDREN)
    rest_param = _make_param(name="rest", kind=MemoParamKind.REST)

    children_param.bind_call_value(binding)
    rest_param.bind_call_value(binding)

    # Neither method consumed any kwarg.
    assert binding.raw_kwargs == {
        "children": binding.raw_kwargs["children"],
        "extra": 1,
    }
    assert binding._props == {}
    assert binding._event_triggers == {}


def test_take_rest_sweeps_unconsumed_keys_into_camel_cased_dict():
    """binding.take_rest collects every leftover kwarg not on the Component."""
    binding = _MemoCallBinding({"foo_bar": "x", "class_name": "y"})
    rest = binding.take_rest(component_fields={})
    assert set(rest) == {"fooBar", "className"}
    assert binding.raw_kwargs == {}


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (MemoParamKind.VALUE, "amount:amountRxMemo"),
        (MemoParamKind.EVENT_TRIGGER, "amount:amountRxMemo"),
        (MemoParamKind.CHILDREN, None),
        (MemoParamKind.REST, None),
    ],
)
def test_signature_field_for_each_kind(kind: MemoParamKind, expected: str | None):
    """VALUE/EVENT_TRIGGER destructure; CHILDREN/REST emit out-of-band."""
    param = _make_param(
        name="amount",
        kind=kind,
        js_prop_name="amount",
        placeholder_name="amountRxMemo",
    )
    assert param.signature_field() == expected


def test_event_trigger_validate_rejects_default_directly():
    """The validate hook on _SPECS[EVENT_TRIGGER] rejects defaults without
    going through the decorator. This pins per-kind invariants at the Seam.
    """
    parameter = inspect.Parameter(
        name="event",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=None,
        annotation=rx.EventHandler[rx.event.passthrough_event_spec(str)],
    )
    with pytest.raises(TypeError, match="default"):
        _SPECS[MemoParamKind.EVENT_TRIGGER].validate(parameter, "fn", True)


def test_event_trigger_validate_rejects_in_var_returning_memo():
    """EVENT_TRIGGER is only valid on component-returning memos."""
    parameter = inspect.Parameter(
        name="event",
        kind=inspect.Parameter.KEYWORD_ONLY,
        annotation=rx.EventHandler,
    )
    with pytest.raises(TypeError, match="component-returning"):
        _SPECS[MemoParamKind.EVENT_TRIGGER].validate(parameter, "fn", False)


def test_self_referencing_component_memo():
    """Component memos whose body recursively calls themselves should decorate."""

    @rx.memo
    def recursive_box(items: rx.Var[list[int]]) -> rx.Component:
        return rx.box(
            rx.foreach(items, lambda item: recursive_box(items=items)),
        )

    assert ("RecursiveBox", __name__) in MEMOS
    definition = MEMOS["RecursiveBox", __name__]
    assert isinstance(definition, MemoComponentDefinition)

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    # The memo mirrors to its source module's combined file (named after the
    # module, not the memo), so look it up by that path rather than a per-name
    # ``RecursiveBox.jsx``.
    segments = memo_paths.module_to_mirrored_segments(definition.source_module)
    assert segments is not None
    exp_path = compiler_utils.get_memo_module_path(segments)
    body_source = next(code for path, code in files if path == exp_path)
    # ``>= 2``: once for the export, once for the recursive foreach call site.
    assert body_source.count("RecursiveBox") >= 2

    instance = recursive_box(items=Var(_js_expr="items", _var_type=list[int]))
    assert isinstance(instance, MemoComponent)
    assert type(instance).tag == memo_paths.mirrored_symbol("RecursiveBox", __name__)


def test_self_referencing_memo_omits_self_import_from_aggregate():
    """A self-importing memo must not leak its own specifier into the aggregate.

    The mirrored module specifier a memo uses to reference itself must be
    stripped from the aggregate import set returned to the frontend-package scan.
    """

    @rx.memo
    def recursive_card(items: rx.Var[list[int]]) -> rx.Component:
        return rx.box(rx.foreach(items, lambda item: recursive_card(items=items)))

    definition = MEMOS["RecursiveCard", __name__]
    segments = memo_paths.module_to_mirrored_segments(definition.source_module)
    assert segments is not None
    self_specifier = memo_paths.mirrored_library_specifier(segments)

    _, aggregate_imports = compiler.compile_memo_components((definition,))
    assert self_specifier not in aggregate_imports


def test_reset_memo_component_classes_recomputes_stale_library(monkeypatch):
    """Resetting the class cache re-resolves a memo's library.

    A module that flips to a package across hot-reload compiles keeps its name
    but gains an ``index`` segment; without a reset the cached wrapper class
    would keep serving the pre-flip specifier.
    """
    from reflex_base.components.memo import (
        _get_memo_component_class,
        reset_memo_component_classes,
    )

    reset_memo_component_classes()
    monkeypatch.setattr(
        memo_paths, "module_to_mirrored_segments", lambda module: ("pkgflip",)
    )
    flat = _get_memo_component_class("Flip", source_module="pkgflip")
    assert flat.library == "$/app_components/pkgflip"

    # The module is now a package: same name, segments gain ``index``.
    monkeypatch.setattr(
        memo_paths, "module_to_mirrored_segments", lambda module: ("pkgflip", "index")
    )
    # Stale until the cache is cleared.
    assert (
        _get_memo_component_class("Flip", source_module="pkgflip").library
        == "$/app_components/pkgflip"
    )
    reset_memo_component_classes()
    assert (
        _get_memo_component_class("Flip", source_module="pkgflip").library
        == "$/app_components/pkgflip/index"
    )
    reset_memo_component_classes()


def test_self_referencing_var_memo():
    """Var-returning memos whose body recursively calls themselves should decorate."""

    @rx.memo
    def recursive_count(n: rx.vars.NumberVar[int]) -> rx.Var[int]:
        recurse = cast("rx.vars.NumberVar[int]", recursive_count(n=n - 1))
        return cast("rx.Var[int]", rx.cond(n.bool(), n + recurse, 0))

    definition = MEMOS["recursive_count", __name__]
    assert isinstance(definition, MemoFunctionDefinition)
    assert "recursive_count" in str(definition.function)

    invoked = recursive_count(n=Var(_js_expr="three", _var_type=int))
    assert "recursive_count" in str(invoked)
