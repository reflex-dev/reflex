from typing import Dict, List

import pytest

from pynecone.components.tags import Tag
from pynecone.event import EventChain, EventHandler, EventSpec
from pynecone.var import BaseVar, Var


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
        ({"a": "red", "b": "blue"}, '{{"a": "red", "b": "blue"}}'),
        (BaseVar(name="var", type_="int"), "{var}"),
        (BaseVar(name='state.colors["a"]', type_="str"), '{state.colors["a"]}'),
        ({"a": BaseVar(name="val", type_="str")}, '{{"a": val}}'),
        ({"a": BaseVar(name='"val"', type_="str")}, '{{"a": "val"}}'),
        (
            {"a": BaseVar(name='state.colors["val"]', type_="str")},
            '{{"a": state.colors["val"]}}',
        ),
    ],
)
def test_format_prop(prop: Var, formatted: str):
    """Test that the formatted value of an prop is correct.

    Args:
        prop: The prop to test.
        formatted: The expected formatted value.
    """
    assert Tag.format_prop(prop) == formatted


@pytest.mark.parametrize(
    "props,test_props",
    [
        ({}, []),
        ({"key": 1}, ["key={1}"]),
        ({"key": "value"}, ['key="value"']),
        ({"key": True, "key2": "value2"}, ["key={true}", 'key2="value2"']),
    ],
)
def test_format_props(props: Dict[str, Var], test_props: List):
    """Test that the formatted props are correct.

    Args:
        props: The props to test.
        test_props: The expected props.
    """
    tag_props = Tag(props=props).format_props()
    for tag_prop, test_prop in zip(tag_props, test_props):
        assert tag_prop == test_prop


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


# def test_format_cond_tag():
#     """Test that the formatted cond tag is correct."""
#     tag = CondTag(
#         true_value=str(Tag(name="h1", contents="True content")),
#         false_value=str(Tag(name="h2", contents="False content")),
#         cond=BaseVar(name="logged_in", type_=bool),
#     )
#     assert str(tag) == "{logged_in ? <h1>True content</h1> : <h2>False content</h2>}"
