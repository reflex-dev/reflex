import pytest

from reflex.components.tags import CondTag, Tag, tagless
from reflex.vars.base import LiteralVar, Var


@pytest.mark.parametrize(
    ("props", "test_props"),
    [
        ({}, []),
        ({"key-hyphen": 1}, ['"key-hyphen":1']),
        ({"key": 1}, ["key:1"]),
        ({"key": "value"}, ['key:"value"']),
        ({"key": True, "key2": "value2"}, ["key:true", 'key2:"value2"']),
    ],
)
def test_format_props(props: dict[str, Var], test_props: list):
    """Test that the formatted props are correct.

    Args:
        props: The props to test.
        test_props: The expected props.
    """
    tag_props = Tag(props=props).format_props()
    for i, tag_prop in enumerate(tag_props):
        assert tag_prop == test_props[i]


@pytest.mark.parametrize(
    ("prop", "valid"),
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
    assert tag.props["key"].equals(LiteralVar.create("value"))
    assert tag.props["key2"].equals(LiteralVar.create(42))
    assert "invalid" not in tag.props
    assert "invalid2" not in tag.props


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        (
            Tag(),
            {
                "name": "",
                "children": [],
                "props": [],
            },
        ),
        (
            Tag(name="br"),
            {
                "name": "br",
                "children": [],
                "props": [],
            },
        ),
        (
            tagless.Tagless(contents="hello"),
            {
                "contents": "hello",
            },
        ),
        (
            Tag(name="box", props={"color": "red", "textAlign": "center"}),
            {
                "name": "box",
                "children": [],
                "props": ['color:"red"', 'textAlign:"center"'],
            },
        ),
    ],
)
def test_format_tag(tag: Tag, expected: dict):
    """Test that the tag dict is correct.

    Args:
        tag: The tag to test.
        expected: The expected tag dictionary.
    """
    tag_dict = dict(tag)
    assert tag_dict == expected


def test_format_cond_tag():
    """Test that the cond tag dict is correct."""
    tag = CondTag(
        true_value=dict(tagless.Tagless(contents="True content")),
        false_value=dict(tagless.Tagless(contents="False content")),
        cond=Var("logged_in", _var_type=bool),
    )
    tag_dict = dict(tag)
    cond, true_value, false_value = (
        tag_dict["cond"],
        tag_dict["true_value"],
        tag_dict["false_value"],
    )
    assert cond._js_expr == "logged_in"
    assert cond._var_type is bool

    assert true_value["contents"] == "True content"

    assert false_value["contents"] == "False content"


def test_tagless_string_representation():
    """Test that the string representation of a tagless is correct."""
    tag = tagless.Tagless(contents="Hello world")
    expected_output = "Hello world"
    assert str(tag) == expected_output
