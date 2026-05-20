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
    MEMOS,
    MemoComponent,
    MemoComponentDefinition,
    MemoFunctionDefinition,
    MemoParam,
    MemoParamKind,
    _MemoCallBinding,
)
from reflex_base.event import EventChain, EventHandler, no_args_event_spec
from reflex_base.style import Style
from reflex_base.utils import console
from reflex_base.utils import format as format_utils
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

    assert (
        str(format_price(amount=price, currency=currency))
        == "(format_price(price, currency))"
    )
    assert (
        str(format_price.call(amount=price, currency=currency))
        == "(format_price(price, currency))"
    )
    assert isinstance(format_price._as_var(), FunctionVar)

    definition = MEMOS["format_price"]
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

    assert isinstance(component, MemoComponent)
    assert len(component.children) == 2
    assert component.get_props() == ("title", "foo")
    assert type(component) is type(component_again)
    assert type(component).tag == "MyCard"
    assert type(component).get_fields()["tag"].default == "MyCard"

    rendered = component.render()
    assert rendered["name"] == "MyCard"
    assert 'title:"Hello"' in rendered["props"]
    assert 'foo:"extra"' in rendered["props"]
    assert 'className:"extra"' in rendered["props"]

    definition = MEMOS["MyCard"]
    assert isinstance(definition, MemoComponentDefinition)
    assert any(str(prop) == "rest" for prop in definition.component.special_props)

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert "export const MyCard = memo(({children, title:title" in code
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

    definition = MEMOS["ConditionalSlot"]
    assert isinstance(definition, MemoComponentDefinition)
    assert definition.component.render() == {
        "contents": "(showRxMemo ? firstRxMemo : secondRxMemo)"
    }

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert "export const ConditionalSlot = memo(({show:showRxMemo" in code
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

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert (
        "export const merge_styles = (({base, ...overrides}) => ({...base, ...overrides}));"
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

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    code = "\n".join(c for _, c in files)
    assert "export const label_slot = (({children, label, ...rest}) => label);" in code


def test_memo_requires_var_annotations():
    """Memos should reject non-Var annotations on parameters."""
    with pytest.raises(TypeError, match="must be annotated"):

        @rx.memo
        def bad_annotation(value: int) -> rx.Var[str]:
            return rx.Var.create("x")


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

    assert "FooBar" in MEMOS

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
    """Var-returning memos should reject hook-bearing expressions."""
    with pytest.raises(TypeError, match="cannot depend on hooks"):

        @rx.memo
        def bad_hook(value: rx.Var[str]) -> rx.Var[str]:
            return Var(
                _js_expr="value",
                _var_type=str,
                _var_data=VarData(hooks={"const badHook = 1": None}),
            )


def test_var_returning_memo_rejects_non_bundled_imports():
    """Var-returning memos should reject non-bundled imports."""
    with pytest.raises(TypeError, match="not bundled"):

        @rx.memo
        def bad_import(value: rx.Var[str]) -> rx.Var[str]:
            return Var(
                _js_expr="value",
                _var_type=str,
                _var_data=VarData(imports={"some-lib": [ImportVar(tag="x")]}),
            )


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

    assert "export const TextWrapper = memo(" in code
    assert "export const format_price =" in code
    assert "export const MyCard = memo(" in code


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
            component=rx.fragment(),
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

    assert len(files) == len(memos) + 1
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

    definition = MEMOS["Wrapper"]
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

    definition = MEMOS["Wrapper"]
    assert isinstance(definition, MemoComponentDefinition)
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

    definition = MEMOS["EhMemo"]
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

    definition = MEMOS["BareEhMemo"]
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

    assert "RecursiveBox" in MEMOS
    definition = MEMOS["RecursiveBox"]
    assert isinstance(definition, MemoComponentDefinition)

    files, _ = compiler.compile_memo_components(tuple(MEMOS.values()))
    body_source = next(
        code for path, code in files if path.endswith("RecursiveBox.jsx")
    )
    # ``>= 2``: once for the export, once for the recursive foreach call site.
    assert body_source.count("RecursiveBox") >= 2

    instance = recursive_box(items=Var(_js_expr="items", _var_type=list[int]))
    assert isinstance(instance, MemoComponent)
    assert type(instance).tag == "RecursiveBox"


def test_self_referencing_var_memo():
    """Var-returning memos whose body recursively calls themselves should decorate."""

    @rx.memo
    def recursive_count(n: rx.vars.NumberVar[int]) -> rx.Var[int]:
        recurse = cast("rx.vars.NumberVar[int]", recursive_count(n=n - 1))
        return cast("rx.Var[int]", rx.cond(n.bool(), n + recurse, 0))

    definition = MEMOS["recursive_count"]
    assert isinstance(definition, MemoFunctionDefinition)
    assert "recursive_count" in str(definition.function)

    invoked = recursive_count(n=Var(_js_expr="three", _var_type=int))
    assert "recursive_count" in str(invoked)
