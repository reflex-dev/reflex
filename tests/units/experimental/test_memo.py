"""Tests for experimental memo support."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from reflex_base.components.component import CUSTOM_COMPONENTS, Component
from reflex_base.style import Style
from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData
from reflex_base.vars.base import Var
from reflex_base.vars.function import FunctionVar

import reflex as rx
from reflex.compiler import compiler
from reflex.compiler import utils as compiler_utils
from reflex.experimental.memo import (
    EXPERIMENTAL_MEMOS,
    ExperimentalMemoComponent,
    ExperimentalMemoComponentDefinition,
    ExperimentalMemoFunctionDefinition,
)


@pytest.fixture(autouse=True)
def _restore_memo_registries(preserve_memo_registries):
    """Autouse wrapper around the shared preserve_memo_registries fixture."""


def test_var_returning_memo():
    """Var-returning memos should behave like imported function vars."""

    @rx._x.memo
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

    definition = EXPERIMENTAL_MEMOS["format_price"]
    assert isinstance(definition, ExperimentalMemoFunctionDefinition)
    assert (
        str(definition.function) == '((amount, currency) => ((currency+": $")+amount))'
    )

    with pytest.raises(TypeError, match="only accepts keyword props"):
        format_price(price, currency)


def test_component_returning_memo_with_children_and_rest():
    """Component-returning memos should accept positional children and forwarded props."""

    @rx._x.memo
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

    assert isinstance(component, ExperimentalMemoComponent)
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

    definition = EXPERIMENTAL_MEMOS["MyCard"]
    assert isinstance(definition, ExperimentalMemoComponentDefinition)
    assert any(str(prop) == "rest" for prop in definition.component.special_props)

    _, code, _ = compiler.compile_memo_components(
        (), tuple(EXPERIMENTAL_MEMOS.values())
    )
    assert "export const MyCard = memo(({children, title:title" in code
    assert "...rest" in code
    assert "jsx(RadixThemesBox,{...rest}" in code


def test_component_returning_memo_accepts_component_var_result():
    """Component-returning memos should accept component-typed var results."""

    @rx._x.memo
    def conditional_slot(
        show: rx.Var[bool],
        first: rx.Var[rx.Component],
        second: rx.Var[rx.Component],
    ) -> rx.Var[rx.Component]:
        return rx.cond(show, first, second)

    definition = EXPERIMENTAL_MEMOS["ConditionalSlot"]
    assert isinstance(definition, ExperimentalMemoComponentDefinition)
    assert definition.component.render() == {
        "contents": "(showRxMemo ? firstRxMemo : secondRxMemo)"
    }

    _, code, _ = compiler.compile_memo_components(
        (), tuple(EXPERIMENTAL_MEMOS.values())
    )
    assert "export const ConditionalSlot = memo(({show:showRxMemo" in code
    assert "(showRxMemo ? firstRxMemo : secondRxMemo)" in code


def test_var_returning_memo_with_rest_props():
    """Var-returning memos should capture extra keyword args into RestProp."""

    @rx._x.memo
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

    _, code, _ = compiler.compile_memo_components(
        (), tuple(EXPERIMENTAL_MEMOS.values())
    )
    assert (
        "export const merge_styles = (({base, ...overrides}) => ({...base, ...overrides}));"
        in code
    )

    with pytest.raises(TypeError, match="Do not pass `overrides=` directly"):
        merge_styles(base=base, overrides={"color": "red"})


def test_var_returning_memo_with_children_and_rest():
    """Var-returning memos should accept positional children plus keyword props."""

    @rx._x.memo
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

    _, code, _ = compiler.compile_memo_components(
        (), tuple(EXPERIMENTAL_MEMOS.values())
    )
    assert "export const label_slot = (({children, label, ...rest}) => label);" in code


def test_memo_requires_var_annotations():
    """Experimental memos should require Var annotations on parameters."""
    with pytest.raises(TypeError, match="must be annotated"):

        @rx._x.memo
        def bad_annotation(value: int) -> rx.Var[str]:
            return rx.Var.create("x")

    with pytest.raises(TypeError, match="Missing annotation"):

        @rx._x.memo
        def missing_annotation(value) -> rx.Var[str]:
            return rx.Var.create("x")


def test_memo_rejects_invalid_children_annotation():
    """Component memos should validate the special children annotation."""
    with pytest.raises(TypeError, match="children"):

        @rx._x.memo
        def bad_children(children: rx.Var[str]) -> rx.Component:
            return rx.text(children)


def test_memo_rejects_multiple_rest_props():
    """Experimental memos should only allow a single RestProp."""
    with pytest.raises(TypeError, match="only supports one"):

        @rx._x.memo
        def too_many_rest(
            first: rx.RestProp,
            second: rx.RestProp,
        ) -> rx.Var[Any]:
            return first


def test_memo_rejects_component_and_function_name_collision():
    """Experimental memos should reject same exported name across kinds."""

    @rx._x.memo
    def foo_bar() -> rx.Component:
        return rx.box()

    assert "FooBar" in EXPERIMENTAL_MEMOS

    with pytest.raises(ValueError, match=r"name collision.*FooBar"):

        @rx._x.memo
        def FooBar() -> rx.Var[str]:
            return rx.Var.create("x")


def test_memo_rejects_component_export_name_collision():
    """Experimental memos should reject duplicate component export names."""

    @rx._x.memo
    def foo_bar() -> rx.Component:
        return rx.box()

    with pytest.raises(ValueError, match=r"name collision.*FooBar"):

        @rx._x.memo
        def foo__bar() -> rx.Component:
            return rx.box()


def test_memo_rejects_varargs():
    """Experimental memos should reject *args and **kwargs."""
    with pytest.raises(TypeError, match=r"\*args"):

        @rx._x.memo
        def bad_args(*values: rx.Var[str]) -> rx.Var[str]:
            return rx.Var.create("x")

    with pytest.raises(TypeError, match=r"\*\*kwargs"):

        @rx._x.memo
        def bad_kwargs(**values: rx.Var[str]) -> rx.Var[str]:
            return rx.Var.create("x")


def test_component_memo_rejects_invalid_positional_usage():
    """Component memos should only accept positional children."""

    @rx._x.memo
    def title_card(*, title: rx.Var[str]) -> rx.Component:
        return rx.box(rx.heading(title))

    with pytest.raises(TypeError, match="only accepts keyword props"):
        title_card(rx.text("child"))

    @rx._x.memo
    def child_card(
        children: rx.Var[rx.Component], *, title: rx.Var[str]
    ) -> rx.Component:
        return rx.box(rx.heading(title), children)

    with pytest.raises(TypeError, match="only accepts positional children"):
        child_card("not a component", title="Hello")


def test_var_memo_rejects_invalid_positional_usage():
    """Var memos should also reserve positional arguments for children only."""

    @rx._x.memo
    def format_price(amount: rx.Var[int], currency: rx.Var[str]) -> rx.Var[str]:
        return currency.to(str) + ": $" + amount.to(str)

    price = Var(_js_expr="price", _var_type=int)
    currency = Var(_js_expr="currency", _var_type=str)

    with pytest.raises(TypeError, match="only accepts keyword props"):
        format_price(price, currency)

    @rx._x.memo
    def child_label(
        children: rx.Var[rx.Component], *, label: rx.Var[str]
    ) -> rx.Var[str]:
        return label

    with pytest.raises(TypeError, match="only accepts positional children"):
        child_label("not a component", label="Hello")


def test_var_returning_memo_rejects_hooks():
    """Var-returning memos should reject hook-bearing expressions."""
    with pytest.raises(TypeError, match="cannot depend on hooks"):

        @rx._x.memo
        def bad_hook(value: rx.Var[str]) -> rx.Var[str]:
            return Var(
                _js_expr="value",
                _var_type=str,
                _var_data=VarData(hooks={"const badHook = 1": None}),
            )


def test_var_returning_memo_rejects_non_bundled_imports():
    """Var-returning memos should reject non-bundled imports."""
    with pytest.raises(TypeError, match="not bundled"):

        @rx._x.memo
        def bad_import(value: rx.Var[str]) -> rx.Var[str]:
            return Var(
                _js_expr="value",
                _var_type=str,
                _var_data=VarData(imports={"some-lib": [ImportVar(tag="x")]}),
            )


def test_compile_memo_components_includes_experimental_functions_and_components():
    """The shared memo output should include both experimental functions and components."""

    @rx.memo
    def old_wrapper(title: rx.Var[str]) -> rx.Component:
        return rx.text(title)

    @rx._x.memo
    def format_price(amount: rx.Var[int], currency: rx.Var[str]) -> rx.Var[str]:
        return currency.to(str) + ": $" + amount.to(str)

    @rx._x.memo
    def my_card(children: rx.Var[rx.Component], *, title: rx.Var[str]) -> rx.Component:
        return rx.box(rx.heading(title), children)

    _, code, _ = compiler.compile_memo_components(
        dict.fromkeys(CUSTOM_COMPONENTS.values()),
        tuple(EXPERIMENTAL_MEMOS.values()),
    )

    assert "export const OldWrapper = memo(" in code
    assert "export const format_price =" in code
    assert "export const MyCard = memo(" in code


def test_experimental_component_memo_get_imports():
    """Experimental component memos should resolve imports during compilation."""

    class Inner(Component):
        tag = "Inner"
        library = "inner"

    @rx._x.memo
    def wrapper() -> rx.Component:
        return Inner.create()

    experimental_component = wrapper()

    assert "inner" not in experimental_component._get_all_imports()

    definition = EXPERIMENTAL_MEMOS["Wrapper"]
    assert isinstance(definition, ExperimentalMemoComponentDefinition)
    _, imports = compiler_utils.compile_experimental_component_memo(definition)
    assert "inner" in imports


def test_compile_experimental_component_memo_does_not_mutate_definition(
    monkeypatch: pytest.MonkeyPatch,
):
    """Experimental component memo compilation should not mutate stored components."""

    @rx._x.memo
    def wrapper() -> rx.Component:
        return rx.box("hi")

    definition = EXPERIMENTAL_MEMOS["Wrapper"]
    assert isinstance(definition, ExperimentalMemoComponentDefinition)
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


def test_compile_memo_components_includes_experimental_custom_code():
    """Experimental component memos should include custom code in compiled output."""

    class FooComponent(rx.Fragment):
        def add_custom_code(self) -> list[str]:
            return [
                "const foo = 'bar'",
            ]

    @rx._x.memo
    def foo_component(label: rx.Var[str]) -> rx.Component:
        return FooComponent.create(label, rx.Var("foo"))

    _, code, _ = compiler.compile_memo_components(
        (), tuple(EXPERIMENTAL_MEMOS.values())
    )

    assert "const foo = 'bar'" in code
