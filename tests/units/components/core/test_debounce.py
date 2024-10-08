"""Test that DebounceInput collapses nested forms."""

import pytest

import reflex as rx
from reflex.components.core.debounce import DEFAULT_DEBOUNCE_TIMEOUT
from reflex.state import BaseState
from reflex.vars.base import LiteralVar, Var


def test_create_no_child():
    """DebounceInput raises RuntimeError if no child is provided."""
    with pytest.raises(RuntimeError):
        _ = rx.debounce_input()


def test_create_no_child_recursive():
    """DebounceInput raises RuntimeError if no child is provided."""
    with pytest.raises(RuntimeError):
        _ = rx.debounce_input(rx.debounce_input(rx.debounce_input()))


def test_create_many_child():
    """DebounceInput raises RuntimeError if more than 1 child is provided."""
    with pytest.raises(RuntimeError):
        _ = rx.debounce_input("foo", "bar")


def test_create_no_on_change():
    """DebounceInput raises ValueError if child has no on_change handler."""
    with pytest.raises(ValueError):
        _ = rx.debounce_input(rx.input())


class S(BaseState):
    """Example state for debounce tests."""

    value: str = ""

    def on_change(self, v: str):
        """Dummy on_change handler.


        Args:
            v: The changed value.
        """
        pass


def test_render_child_props():
    """DebounceInput should render props from child component."""
    tag = rx.debounce_input(
        rx.input(
            foo="bar",
            baz="quuc",
            value="real",
            on_change=S.on_change,
        )
    )._render()
    assert "css" in tag.props and isinstance(tag.props["css"], rx.vars.Var)
    for prop in ["foo", "bar", "baz", "quuc"]:
        assert prop in str(tag.props["css"])
    assert tag.props["value"].equals(LiteralVar.create("real"))
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""


def test_render_with_class_name():
    tag = rx.debounce_input(
        rx.input(
            on_change=S.on_change,
            class_name="foo baz",
        )
    )._render()
    assert isinstance(tag.props["className"], rx.vars.Var)
    assert "foo baz" in str(tag.props["className"])


def test_render_with_ref():
    tag = rx.debounce_input(
        rx.input(
            on_change=S.on_change,
            id="foo_bar",
        )
    )._render()
    assert isinstance(tag.props["inputRef"], rx.vars.Var)
    assert "foo_bar" in str(tag.props["inputRef"])


def test_render_with_key():
    tag = rx.debounce_input(
        rx.input(
            on_change=S.on_change,
            key="foo_bar",
        )
    )._render()
    assert isinstance(tag.props["key"], rx.vars.Var)
    assert "foo_bar" in str(tag.props["key"])


def test_render_with_special_props():
    special_prop = Var(_js_expr="{foo_bar}")
    tag = rx.debounce_input(
        rx.input(
            on_change=S.on_change,
            special_props=[special_prop],
        )
    )._render()
    assert len(tag.special_props) == 1
    assert list(tag.special_props)[0].equals(special_prop)


def test_event_triggers():
    debounced_input = rx.debounce_input(
        rx.input(
            on_change=S.on_change,
        )
    )
    assert tuple(debounced_input.get_event_triggers()) == (
        *rx.Component().get_event_triggers(),  # default event triggers
        "on_change",
    )


def test_render_child_props_recursive():
    """DebounceInput should render props from child component.

    If the child component is a DebounceInput, then props will be copied from it
    recursively.
    """
    tag = rx.debounce_input(
        rx.debounce_input(
            rx.debounce_input(
                rx.debounce_input(
                    rx.input(
                        foo="bar",
                        baz="quuc",
                        value="real",
                        on_change=S.on_change,
                    ),
                    value="inner",
                    debounce_timeout=666,
                    force_notify_on_blur=False,
                ),
                debounce_timeout=42,
            ),
            value="outer",
        ),
        force_notify_by_enter=False,
    )._render()
    assert "css" in tag.props and isinstance(tag.props["css"], rx.vars.Var)
    for prop in ["foo", "bar", "baz", "quuc"]:
        assert prop in str(tag.props["css"])
    assert tag.props["value"].equals(LiteralVar.create("outer"))
    assert tag.props["forceNotifyOnBlur"]._js_expr == "false"
    assert tag.props["forceNotifyByEnter"]._js_expr == "false"
    assert tag.props["debounceTimeout"]._js_expr == "42"
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""


def test_full_control_implicit_debounce():
    """DebounceInput is used when value and on_change are used together."""
    tag = rx.input(
        value=S.value,
        on_change=S.on_change,
    )._render()
    assert tag.props["debounceTimeout"]._js_expr == str(DEFAULT_DEBOUNCE_TIMEOUT)
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""


def test_full_control_implicit_debounce_text_area():
    """DebounceInput is used when value and on_change are used together."""
    tag = rx.text_area(
        value=S.value,
        on_change=S.on_change,
    )._render()
    assert tag.props["debounceTimeout"]._js_expr == str(DEFAULT_DEBOUNCE_TIMEOUT)
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""
