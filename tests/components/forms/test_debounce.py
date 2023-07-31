"""Test that DebounceInput collapses nested forms."""

import pytest

import reflex as rx
from reflex.vars import BaseVar


def test_render_no_child():
    """DebounceInput raises RuntimeError if no child is provided."""
    with pytest.raises(RuntimeError):
        _ = rx.debounce_input().render()


def test_render_no_child_recursive():
    """DebounceInput raises RuntimeError if no child is provided."""
    with pytest.raises(RuntimeError):
        _ = rx.debounce_input(rx.debounce_input(rx.debounce_input())).render()


def test_render_many_child():
    """DebounceInput raises RuntimeError if more than 1 child is provided."""
    with pytest.raises(RuntimeError):
        _ = rx.debounce_input("foo", "bar").render()


class S(rx.State):
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
    assert tag.props["sx"] == {"foo": "bar", "baz": "quuc"}
    assert tag.props["value"] == BaseVar(
        name="real", type_=str, is_local=True, is_string=False
    )
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""


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
                    force_notify_on_blur=False,
                ),
                debounce_timeout=42,
            ),
            value="outer",
        ),
        force_notify_by_enter=False,
    )._render()
    assert tag.props["sx"] == {"foo": "bar", "baz": "quuc"}
    assert tag.props["value"] == BaseVar(
        name="real", type_=str, is_local=True, is_string=False
    )
    assert tag.props["forceNotifyOnBlur"].name == "false"
    assert tag.props["forceNotifyByEnter"].name == "false"
    assert tag.props["debounceTimeout"] == 42
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""


def test_full_control_implicit_debounce():
    """DebounceInput is used when value and on_change are used together."""
    tag = rx.input(
        value=S.value,
        on_change=S.on_change,
    )._render()
    assert tag.props["debounceTimeout"] == 0
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""


def test_full_control_implicit_debounce_text_area():
    """DebounceInput is used when value and on_change are used together."""
    tag = rx.text_area(
        value=S.value,
        on_change=S.on_change,
    )._render()
    assert tag.props["debounceTimeout"] == 0
    assert len(tag.props["onChange"].events) == 1
    assert tag.props["onChange"].events[0].handler == S.on_change
    assert tag.contents == ""
