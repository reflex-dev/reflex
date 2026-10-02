"""Tests for submitted form data."""

import pickle
from collections.abc import Mapping
from typing import Any, TypedDict

import pytest
from reflex_base.utils.form import (
    FORM_DATA_ENTRIES_KEY,
    FormData,
    form_data_as_dict,
    transform_form_data,
)
from typing_extensions import NotRequired

ITEMS = [("tag", "a"), ("name", "x"), ("tag", "b")]


def test_form_data_reads_like_a_dict_of_last_values():
    """Indexing, iteration and length see each key once, with its last value."""
    form_data = FormData(ITEMS)
    assert isinstance(form_data, Mapping)
    assert form_data["tag"] == "b"
    assert form_data.get("name") == "x"
    assert form_data.get("missing") is None
    assert "tag" in form_data
    assert "missing" not in form_data
    assert list(form_data) == ["tag", "name"]
    assert len(form_data) == 2
    assert dict(form_data) == {"tag": "b", "name": "x"}
    with pytest.raises(KeyError):
        form_data["missing"]


def test_form_data_keeps_every_value_in_order():
    """Every value of a repeated key is kept, in order."""
    form_data = FormData(ITEMS)
    assert form_data.getlist("tag") == ["a", "b"]
    assert form_data.getlist("name") == ["x"]
    assert form_data.getlist("missing") == []
    assert form_data.getAll("tag") == ["a", "b"]
    assert form_data.multi_items() == ITEMS


@pytest.mark.parametrize(
    "source",
    [
        ITEMS,
        [list(item) for item in ITEMS],
        iter(ITEMS),
        FormData(ITEMS),
    ],
)
def test_form_data_from_items(source):
    """Pairs, two-item lists, iterators and FormDatas all keep every item."""
    assert FormData(source).multi_items() == ITEMS


def test_form_data_from_mapping():
    """A plain mapping gives one item per key."""
    form_data = FormData({"tag": "a", "name": "x"})
    assert form_data.multi_items() == [("tag", "a"), ("name", "x")]
    assert FormData().multi_items() == []


def test_form_data_equality():
    """FormDatas compare their items in order; a dict compares last values."""
    assert FormData(ITEMS) == FormData(ITEMS)
    assert FormData(ITEMS) != FormData(list(reversed(ITEMS)))
    assert FormData(ITEMS) == {"tag": "b", "name": "x"}
    assert FormData(ITEMS) != {"tag": "a", "name": "x"}


def test_form_data_is_immutable():
    """A FormData cannot be changed after it is built."""
    form_data = FormData(ITEMS)
    with pytest.raises(TypeError):
        form_data["tag"] = "c"  # pyright: ignore[reportIndexIssue]
    with pytest.raises(AttributeError):
        form_data.other = 1  # pyright: ignore[reportAttributeAccessIssue]


def test_form_data_repr_and_pickle():
    """The repr shows every item and pickling keeps them."""
    form_data = FormData(ITEMS)
    assert repr(form_data) == f"FormData({ITEMS!r})"
    assert pickle.loads(pickle.dumps(form_data)).multi_items() == ITEMS


_FORM_DATA_ENTRIES = [["tag", "a"], ["name", "x"], ["tag", "b"]]


def _transform(hint: Any, value: Any = None) -> Any:
    """Transform submitted form entries (or ``value``) for an annotation.

    Args:
        hint: The handler's annotation for the arg.
        value: The wire value, defaulting to the wrapped form entries.

    Returns:
        The value the handler receives.
    """
    if value is None:
        value = {FORM_DATA_ENTRIES_KEY: _FORM_DATA_ENTRIES}
    return transform_form_data(value, hint)


class _TagsData(TypedDict):
    tag: str
    name: str


class _TagsMultiData(TypedDict):
    tag: list[str]
    name: str
    subscribe: bool
    topics: NotRequired[list[str]]
    agree: NotRequired[bool]


class _TagsOptionalData(TypedDict):
    name: str
    tag: list[str] | None
    subscribe: bool | None
    topics: NotRequired[list[str] | None]
    agree: NotRequired[bool | None]


class _SubFormData(FormData[str, str]):
    pass


@pytest.mark.parametrize(
    "hint", [Any, dict, dict[str, Any], Mapping[str, Any], _TagsData]
)
def test_transform_form_data_to_dict(hint: Any):
    """Submitted form entries become a dict keeping each name's last value."""
    form_data = _transform(hint)
    assert type(form_data) is dict
    assert form_data == {"tag": "b", "name": "x"}


@pytest.mark.parametrize(
    ("hint", "expected_type"),
    [
        (FormData, FormData),
        (FormData[str, str], FormData),
        (FormData | None, FormData),
        (_SubFormData, _SubFormData),
    ],
)
def test_transform_form_data_for_form_data_annotation(hint: Any, expected_type: type):
    """A FormData annotation receives every submitted entry in order."""
    form_data = _transform(hint)
    assert type(form_data) is expected_type
    assert form_data.getlist("tag") == ["a", "b"]
    assert form_data["tag"] == "b"
    assert form_data.multi_items() == [("tag", "a"), ("name", "x"), ("tag", "b")]


def test_transform_plain_mapping_for_form_data_annotation():
    """A plain dict payload, e.g. from a backend-built event, becomes a FormData."""
    form_data = _transform(FormData, {"tag": "a"})
    assert type(form_data) is FormData
    assert form_data.getlist("tag") == ["a"]


def test_transform_form_data_instance_passes_through():
    """A FormData built by a previous handler is passed on unchanged."""
    form_data = FormData([("tag", "a"), ("tag", "b")])
    assert _transform(FormData, form_data) is form_data


def test_transform_form_data_to_typed_dict_coerces_lists_and_bools():
    """TypedDict list fields take every value and bool fields are cast."""
    form_data = _transform(
        _TagsMultiData,
        {
            FORM_DATA_ENTRIES_KEY: [
                *_FORM_DATA_ENTRIES,
                ["subscribe", "on"],
                ["topics", "news"],
                ["topics", "events"],
                ["agree", ""],
            ]
        },
    )
    assert form_data == {
        "tag": ["a", "b"],
        "name": "x",
        "subscribe": True,
        "topics": ["news", "events"],
        "agree": False,
    }


def test_transform_form_data_to_typed_dict_with_missing_fields():
    """Unsubmitted required fields are empty or False; NotRequired ones are left out."""
    form_data = _transform(_TagsMultiData, {FORM_DATA_ENTRIES_KEY: [["name", "x"]]})
    assert form_data == {"tag": [], "name": "x", "subscribe": False}


def test_transform_form_data_to_typed_dict_with_optional_fields():
    """Submitted optional list and bool fields are coerced like required ones."""
    form_data = _transform(
        _TagsOptionalData,
        {
            FORM_DATA_ENTRIES_KEY: [
                *_FORM_DATA_ENTRIES,
                ["subscribe", ""],
                ["topics", "news"],
                ["agree", "on"],
            ]
        },
    )
    assert form_data == {
        "tag": ["a", "b"],
        "name": "x",
        "subscribe": False,
        "topics": ["news"],
        "agree": True,
    }


def test_transform_form_data_to_typed_dict_with_missing_optional_fields():
    """Unsubmitted optional fields are None, or left out when NotRequired."""
    form_data = _transform(_TagsOptionalData, {FORM_DATA_ENTRIES_KEY: [["name", "x"]]})
    assert form_data == {"name": "x", "tag": None, "subscribe": None}


def test_transform_form_data_instance_to_typed_dict():
    """A FormData from a previous handler is coerced like submitted entries."""
    form_data = _transform(
        _TagsMultiData, FormData([("tag", "a"), ("tag", "b"), ("name", "x")])
    )
    assert form_data["tag"] == ["a", "b"]
    assert form_data["subscribe"] is False


def test_transform_plain_dict_to_typed_dict_is_unchanged():
    """A dict that is not form data, e.g. an already coerced one, is left alone."""
    value = {"tag": ["a", "b"], "name": "x", "subscribe": True}
    assert _transform(_TagsMultiData, value) is value


def test_form_data_as_dict():
    """Submitted form data becomes a dict of last values; other values pass."""
    assert form_data_as_dict({FORM_DATA_ENTRIES_KEY: _FORM_DATA_ENTRIES}) == {
        "tag": "b",
        "name": "x",
    }
    value = {"tag": "a"}
    assert form_data_as_dict(value) is value
    assert form_data_as_dict("text") == "text"
