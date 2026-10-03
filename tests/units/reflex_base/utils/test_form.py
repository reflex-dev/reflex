"""Tests for submitted form data."""

import pickle
from collections.abc import Mapping
from typing import Any, Generic, TypedDict, TypeVar

import pytest
import typing_extensions
from reflex_base.utils.form import (
    FORM_DATA_ENTRIES_KEY,
    FormData,
    form_data_as_dict,
    transform_form_data,
)
from typing_extensions import NotRequired, TypeAliasType

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
                ["subscribe", ""],
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


_T = TypeVar("_T")


class _GenericPreferences(typing_extensions.TypedDict, Generic[_T]):
    tag: list[_T]
    agree: bool


class _GenericField(typing_extensions.TypedDict, Generic[_T]):
    value: _T
    maybe: _T | None


def test_transform_form_data_to_specialized_generic_typed_dict():
    """A specialized generic TypedDict is coerced like a plain one."""
    assert _transform(_GenericPreferences[str]) == {
        "tag": ["a", "b"],
        "name": "x",
        "agree": False,
    }


@pytest.mark.parametrize(
    ("argument", "expected"),
    [
        (bool, {"name": "x", "value": False, "maybe": None}),
        (list[str], {"name": "x", "value": [], "maybe": None}),
        (str, {"name": "x"}),
    ],
)
def test_transform_form_data_substitutes_typed_dict_type_parameters(argument, expected):
    """A type parameter resolving to a list or bool field type is coerced."""
    form_data = _transform(
        _GenericField[argument], {FORM_DATA_ENTRIES_KEY: [["name", "x"]]}
    )
    assert form_data == expected


_SubmittedFormData = TypeAliasType("_SubmittedFormData", FormData[str, str])
_Tags = TypeAliasType("_Tags", list[str])
_Agreement = TypeAliasType("_Agreement", bool)


class _AliasedFields(TypedDict):
    tag: _Tags
    agree: _Agreement


def test_transform_form_data_for_form_data_type_alias():
    """An alias of FormData receives every submitted entry."""
    form_data = _transform(_SubmittedFormData)
    assert type(form_data) is FormData
    assert form_data.getlist("tag") == ["a", "b"]


def test_transform_form_data_resolves_typed_dict_field_aliases():
    """Aliases of list and bool field types are coerced."""
    assert _transform(_AliasedFields) == {
        "tag": ["a", "b"],
        "name": "x",
        "agree": False,
    }


class _RangeData(TypedDict):
    bounds: list[str]
    name: str


def test_transform_form_data_collects_bracketed_names_into_list_fields():
    """A TypedDict list field takes the ``name[]`` entries a two-thumb slider submits."""
    form_data = _transform(
        _RangeData,
        {
            FORM_DATA_ENTRIES_KEY: [
                ["bounds[]", "20"],
                ["name", "x"],
                ["bounds[]", "80"],
            ]
        },
    )
    assert form_data == {"bounds": ["20", "80"], "name": "x"}


def test_transform_form_data_keeps_order_across_plain_and_bracketed_names():
    """A list field keeps submission order when ``name`` and ``name[]`` interleave."""
    form_data = _transform(
        _RangeData,
        {
            FORM_DATA_ENTRIES_KEY: [
                ["bounds[]", "20"],
                ["bounds", "50"],
                ["bounds[]", "80"],
                ["name", "x"],
            ]
        },
    )
    assert form_data == {"bounds": ["20", "50", "80"], "name": "x"}


class _ScalarData(TypedDict):
    pick: str


def test_transform_form_data_maps_bracketed_names_only_into_list_fields():
    """A non-list field does not take ``name[]`` entries, which stay a list."""
    form_data = _transform(
        _ScalarData, {FORM_DATA_ENTRIES_KEY: [["pick[]", "a"], ["pick[]", "b"]]}
    )
    assert form_data == {"pick[]": ["a", "b"]}


_LiteralBrackets = TypedDict("_LiteralBrackets", {"tags": list[str], "tags[]": str})
_BracketListsFirst = TypedDict(
    "_BracketListsFirst", {"tags[]": list[str], "tags": list[str]}
)
_PlainListsFirst = TypedDict(
    "_PlainListsFirst", {"tags": list[str], "tags[]": list[str]}
)
_PLAIN_AND_BRACKETED = {
    FORM_DATA_ENTRIES_KEY: [["tags", "plain"], ["tags[]", "bracket"]]
}


def test_transform_form_data_keeps_declared_bracketed_field():
    """A declared ``name[]`` field keeps its own value instead of joining ``name``."""
    assert _transform(_LiteralBrackets, _PLAIN_AND_BRACKETED) == {
        "tags": ["plain"],
        "tags[]": "bracket",
    }


@pytest.mark.parametrize("typed_dict", [_BracketListsFirst, _PlainListsFirst])
def test_transform_form_data_declared_bracketed_list_ignores_field_order(typed_dict):
    """Declared ``name`` and ``name[]`` list fields each keep their own values."""
    assert _transform(typed_dict, _PLAIN_AND_BRACKETED) == {
        "tags": ["plain"],
        "tags[]": ["bracket"],
    }


_U = TypeVar("_U")


class _GenericBaseFields(typing_extensions.TypedDict, Generic[_T]):
    tags: _T
    maybe: _T | None


class _InheritedFields(_GenericBaseFields[list[str]]):
    agree: bool


class _InheritedFlags(_GenericBaseFields[bool]):
    pass


class _MiddleFields(_GenericBaseFields[list[_U]], Generic[_U]):
    pass


class _ConcreteFields(_MiddleFields[str]):
    pass


@pytest.mark.parametrize(
    "typed_dict", [_InheritedFields, _ConcreteFields, _MiddleFields[str]]
)
def test_transform_form_data_resolves_inherited_generic_list_fields(typed_dict):
    """Fields inherited from a specialized generic base take its type arguments."""
    form_data = _transform(
        typed_dict, {FORM_DATA_ENTRIES_KEY: [["tags", "first"], ["tags", "second"]]}
    )
    assert form_data["tags"] == ["first", "second"]
    assert form_data["maybe"] is None


def test_transform_form_data_resolves_inherited_generic_bool_fields():
    """An inherited bool specialization is coerced like a declared bool field."""
    assert _transform(_InheritedFlags, {FORM_DATA_ENTRIES_KEY: []}) == {
        "tags": False,
        "maybe": None,
    }


_BRACKETED_ITEMS = [("range[]", "20"), ("name", "x"), ("range[]", "80"), ("one[]", "a")]


def test_form_data_bracketed_names_read_like_other_names():
    """A ``name[]`` key reads its last value; ``getlist`` gives them all."""
    form_data: FormData[str, str] = FormData(_BRACKETED_ITEMS)
    assert form_data["range[]"] == "80"
    assert form_data["range[]"].upper() == "80"
    assert form_data.get("range[]") == "80"
    assert form_data["one[]"] == "a"
    assert dict(form_data) == {"range[]": "80", "name": "x", "one[]": "a"}
    assert form_data.getlist("range[]") == ["20", "80"]
    assert form_data.getAll("range[]") == ["20", "80"]
    assert form_data.multi_items() == _BRACKETED_ITEMS


def test_form_data_from_mapping_keeps_list_values():
    """A mapping's list value is one item, whatever its key."""
    form_data = FormData({"range[]": ["20", "80"]})
    assert form_data.multi_items() == [("range[]", ["20", "80"])]


@pytest.mark.parametrize("hint", [FormData, FormData[str, str]])
def test_transform_form_data_bracketed_names_to_form_data(hint: Any):
    """A FormData annotation keeps ``name[]`` entries as ordinary items."""
    form_data = _transform(
        hint, {FORM_DATA_ENTRIES_KEY: [list(item) for item in _BRACKETED_ITEMS]}
    )
    assert form_data["range[]"] == "80"
    assert form_data.getlist("range[]") == ["20", "80"]


@pytest.mark.parametrize("hint", [Any, dict, dict[str, Any]])
def test_transform_form_data_bracketed_names_to_dict(hint: Any):
    """A dict of submitted form data holds ``name[]`` values as lists."""
    assert _transform(
        hint, {FORM_DATA_ENTRIES_KEY: [list(item) for item in _BRACKETED_ITEMS]}
    ) == {"range[]": ["20", "80"], "name": "x", "one[]": ["a"]}


def test_form_data_as_dict_bracketed_names():
    """The fallback dict also holds ``name[]`` values as lists."""
    assert form_data_as_dict({FORM_DATA_ENTRIES_KEY: [["one[]", "a"]]}) == {
        "one[]": ["a"]
    }


_BracketedScalars = TypedDict(
    "_BracketedScalars",
    {"pick[]": str, "agree[]": bool, "missing[]": str, "picks[]": list[str]},
)


def test_transform_form_data_bracketed_typed_dict_fields_follow_their_type():
    """A declared ``name[]`` field that is not a list gets its last value."""
    form_data = _transform(
        _BracketedScalars,
        {
            FORM_DATA_ENTRIES_KEY: [
                ["pick[]", "a"],
                ["pick[]", "b"],
                ["agree[]", ""],
                ["picks[]", "c"],
                ["other[]", "d"],
            ]
        },
    )
    assert form_data == {
        "pick[]": "b",
        "agree[]": False,
        "picks[]": ["c"],
        "other[]": ["d"],
    }
