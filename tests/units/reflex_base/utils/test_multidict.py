"""Tests for the MultiDict mapping."""

import pickle
from collections.abc import Mapping

import pytest
from reflex_base.utils.multidict import MultiDict

import reflex as rx

ITEMS = [("tag", "a"), ("name", "x"), ("tag", "b")]


def test_multidict_reads_like_a_dict_of_last_values():
    """Indexing, iteration and length see each key once, with its last value."""
    multidict = MultiDict(ITEMS)
    assert isinstance(multidict, Mapping)
    assert multidict["tag"] == "b"
    assert multidict.get("name") == "x"
    assert multidict.get("missing") is None
    assert "tag" in multidict
    assert "missing" not in multidict
    assert list(multidict) == ["tag", "name"]
    assert len(multidict) == 2
    assert dict(multidict) == {"tag": "b", "name": "x"}
    with pytest.raises(KeyError):
        multidict["missing"]


def test_multidict_keeps_every_value_in_order():
    """Every value of a repeated key is kept, in order."""
    multidict = MultiDict(ITEMS)
    assert multidict.getlist("tag") == ["a", "b"]
    assert multidict.getlist("name") == ["x"]
    assert multidict.getlist("missing") == []
    assert multidict.multi_items() == ITEMS


@pytest.mark.parametrize(
    "source",
    [
        ITEMS,
        [list(item) for item in ITEMS],
        iter(ITEMS),
        MultiDict(ITEMS),
    ],
)
def test_multidict_from_items(source):
    """Pairs, two-item lists, iterators and MultiDicts all keep every item."""
    assert MultiDict(source).multi_items() == ITEMS


def test_multidict_from_mapping():
    """A plain mapping gives one item per key."""
    multidict = MultiDict({"tag": "a", "name": "x"})
    assert multidict.multi_items() == [("tag", "a"), ("name", "x")]
    assert MultiDict().multi_items() == []


def test_multidict_equality():
    """MultiDicts compare their items in order; a dict compares last values."""
    assert MultiDict(ITEMS) == MultiDict(ITEMS)
    assert MultiDict(ITEMS) != MultiDict(list(reversed(ITEMS)))
    assert MultiDict(ITEMS) == {"tag": "b", "name": "x"}
    assert MultiDict(ITEMS) != {"tag": "a", "name": "x"}


def test_multidict_is_immutable():
    """A MultiDict cannot be changed after it is built."""
    multidict = MultiDict(ITEMS)
    with pytest.raises(TypeError):
        multidict["tag"] = "c"  # pyright: ignore[reportIndexIssue]
    with pytest.raises(AttributeError):
        multidict.other = 1  # pyright: ignore[reportAttributeAccessIssue]


def test_multidict_repr_and_pickle():
    """The repr shows every item and pickling keeps them."""
    multidict = MultiDict(ITEMS)
    assert repr(multidict) == f"MultiDict({ITEMS!r})"
    assert pickle.loads(pickle.dumps(multidict)).multi_items() == ITEMS


def test_multidict_is_exported_from_reflex():
    """Apps annotate form data with rx.MultiDict."""
    assert rx.MultiDict is MultiDict
