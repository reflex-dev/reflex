import platform
from typing import Dict

import pytest

from pynecone.components import Box
from pynecone.components.tags import CondTag, IterTag, Tag
from pynecone.event import EventChain, EventHandler, EventSpec
from pynecone.var import BaseVar, Var
from pynecone.propcond import PropCond


def mock_event(arg):
    pass


@pytest.mark.parametrize(
    "prop,formatted",
    [
        ("string", '"string"'),
        ("{wrapped_string}", "{wrapped_string}"),
        (True, "{true}"),
        (False, "{false}"),
        (123, "{123}"),
        (3.14, "{3.14}"),
        ([1, 2, 3], "{[1, 2, 3]}"),
        (["a", "b", "c"], '{["a", "b", "c"]}'),
        ({"a": 1, "b": 2, "c": 3}, '{{"a": 1, "b": 2, "c": 3}}'),
        (
            EventChain(events=[EventSpec(handler=EventHandler(fn=mock_event))]),
            '{() => Event([E("mock_event", {})])}',
        ),
        (
            EventChain(
                events=[
                    EventSpec(
                        handler=EventHandler(fn=mock_event),
                        local_args=("e",),
                        args=(("arg", "e.target.value"),),
                    )
                ]
            ),
            '{(e) => Event([E("mock_event", {arg:e.target.value})])}',
        ),
        (
            PropCond.create(
                cond=BaseVar(name="random_var", type_=str),
                prop1="true_value",
                prop2="false_value",
            ),
            "{random_var ? 'true_value' : 'false_value'}",
        ),
    ],
)
def test_format_value(prop: Var, formatted: str):
    """Test that the formatted value of an prop is correct.

    Args:
        prop: The prop to test.
        formatted: The expected formatted value.
    """
    assert Tag.format_prop(prop) == formatted


@pytest.mark.parametrize(
    "props,formatted",
    [
        ({}, ""),
        ({"key": 1}, "key={1}"),
        ({"key": "value"}, 'key="value"'),
        ({"key": True, "key2": "value2"}, 'key={true}\nkey2="value2"'),
    ],
)
def test_format_props(props: Dict[str, Var], formatted: str, windows_platform: bool):
    """Test that the formatted props are correct.

    Args:
        props: The props to test.
        formatted: The expected formatted props.
        windows_platform: Whether the system is windows.
    """
    assert Tag(props=props).format_props() == (
        formatted.replace("\n", "\r\n") if windows_platform else formatted
    )


@pytest.mark.parametrize(
    "prop,valid",
    [
        (1, True),
        (3.14, True),
        ("string", True),
        (False, True),
        ([], True),
        ({}, False),
        (None, False),
    ],
)
def test_is_valid_prop(prop: Var, valid: bool):
    """Test that the prop is valid.

    Args:
        prop: The prop to test.
        valid: The expected validity of the prop.
    """
    assert Tag.is_valid_prop(prop) == valid


def test_add_props():
    """Test that the props are added."""
    tag = Tag().add_props(key="value", key2=42, invalid=None, invalid2={})
    assert tag.props["key"] == Var.create("value")
    assert tag.props["key2"] == Var.create(42)
    assert "invalid" not in tag.props
    assert "invalid2" not in tag.props


@pytest.mark.parametrize(
    "tag,expected",
    [
        (Tag(), "</>"),
        (Tag(name="br"), "<br/>"),
        (Tag(contents="hello"), "<>hello</>"),
        (Tag(name="h1", contents="hello"), "<h1>hello</h1>"),
        (
            Tag(name="box", props={"color": "red", "textAlign": "center"}),
            '<box color="red"\ntextAlign="center"/>',
        ),
        (
            Tag(
                name="box",
                props={"color": "red", "textAlign": "center"},
                contents="text",
            ),
            '<box color="red"\ntextAlign="center">text</box>',
        ),
    ],
)
def test_format_tag(tag: Tag, expected: str, windows_platform: bool):
    """Test that the formatted tag is correct.

    Args:
        tag: The tag to test.
        expected: The expected formatted tag.
        windows_platform: Whether the system is windows.
    """

    expected = expected.replace("\n", "\r\n") if windows_platform else expected
    assert str(tag) == expected


def test_format_cond_tag():
    """Test that the formatted cond tag is correct."""
    tag = CondTag(
        true_value=str(Tag(name="h1", contents="True content")),
        false_value=str(Tag(name="h2", contents="False content")),
        cond=BaseVar(name="logged_in", type_=bool),
    )
    assert str(tag) == "{logged_in ? <h1>True content</h1> : <h2>False content</h2>}"
