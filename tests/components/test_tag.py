from typing import Dict

import pydantic
import pytest

from pynecone.components.tags import CondTag, Tag
from pynecone.event import EventHandler, EventSpec, EventChain
from pynecone.var import BaseVar, Var


def mock_event(arg):
    pass


@pytest.mark.parametrize(
    "cond,valid",
    [
        (BaseVar(name="p", type_=bool), True),
        (BaseVar(name="p", type_=int), False),
        (BaseVar(name="p", type_=str), False),
    ],
)
def test_validate_cond(cond: BaseVar, valid: bool):
    """Test that the cond is a boolean.

    Args:
        cond: The cond to test.
        valid: The expected validity of the cond.
    """
    if not valid:
        with pytest.raises(pydantic.ValidationError):
            Tag(cond=cond)
    else:
        assert cond == Tag(cond=cond).cond


@pytest.mark.parametrize(
    "attr,formatted",
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
            EventSpec(handler=EventHandler(fn=mock_event)),
            '{() => Event([E("mock_event", {})])}',
        ),
        (
            EventSpec(
                handler=EventHandler(fn=mock_event),
                local_args=("e",),
                args=(("arg", "e.target.value"),),
            ),
            '{(e) => Event([E("mock_event", {arg:e.target.value})])}',
        ),
    ],
)
def test_format_value(attr: Var, formatted: str):
    """Test that the formatted value of an attribute is correct.

    Args:
        attr: The attribute to test.
        formatted: The expected formatted value.
    """
    assert Tag.format_attr_value(attr) == formatted


@pytest.mark.parametrize(
    "attrs,formatted",
    [
        ({}, ""),
        ({"key": 1}, "key={1}"),
        ({"key": "value"}, 'key="value"'),
        ({"key": True, "key2": "value2"}, 'key={true}\nkey2="value2"'),
    ],
)
def test_format_attrs(attrs: Dict[str, Var], formatted: str):
    """Test that the formatted attributes are correct.

    Args:
        attrs: The attributes to test.
        formatted: The expected formatted attributes.
    """
    assert Tag(attrs=attrs).format_attrs() == formatted


@pytest.mark.parametrize(
    "attr,valid",
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
def test_is_valid_attr(attr: Var, valid: bool):
    """Test that the attribute is valid.

    Args:
        attr: The attribute to test.
        valid: The expected validity of the attribute.
    """
    assert Tag.is_valid_attr(attr) == valid


def test_add_attrs():
    """Test that the attributes are added."""
    tag = Tag().add_attrs(key="value", key2=42, invalid=None, invalid2={})
    assert tag.attrs["key"] == Var.create("value")
    assert tag.attrs["key2"] == Var.create(42)
    assert "invalid" not in tag.attrs
    assert "invalid2" not in tag.attrs


@pytest.mark.parametrize(
    "tag,expected",
    [
        (Tag(), "</>"),
        (Tag(name="br"), "<br/>"),
        (Tag(contents="hello"), "<>hello</>"),
        (Tag(name="h1", contents="hello"), "<h1>hello</h1>"),
        (
            Tag(name="box", attrs={"color": "red", "textAlign": "center"}),
            '<box color="red"\ntextAlign="center"/>',
        ),
        (
            Tag(
                name="box",
                attrs={"color": "red", "textAlign": "center"},
                contents="text",
            ),
            '<box color="red"\ntextAlign="center">text</box>',
        ),
        (
            Tag(
                name="h1",
                contents="hello",
                cond=BaseVar(name="logged_in", type_=bool),
            ),
            '{logged_in ? <h1>hello</h1> : ""}',
        ),
    ],
)
def test_format_tag(tag: Tag, expected: str):
    """Test that the formatted tag is correct.

    Args:
        tag: The tag to test.
        expected: The expected formatted tag.
    """
    assert str(tag) == expected


def test_format_cond_tag():
    """Test that the formatted cond tag is correct."""
    tag = CondTag(
        true_value=str(Tag(name="h1", contents="True content")),
        false_value=str(Tag(name="h2", contents="False content")),
        cond=BaseVar(name="logged_in", type_=bool),
    )
    assert str(tag) == "{logged_in ? <h1>True content</h1> : <h2>False content</h2>}"


def test_format_iter_tag():
    """Test that the formatted iter tag is correct."""
    # def render_todo(todo: str):
    #     return Tag(name="Text", contents=todo)

    # tag = IterTag(
    #     iterable=BaseVar(name="todos", type_=list),
    #     render_fn=render_todo
    # )
    # assert str(tag) == '{state.todos.map(render_todo)}'
