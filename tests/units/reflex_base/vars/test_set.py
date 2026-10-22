"""Tests for reflex_base.vars.set."""

import operator
import re
import typing
from collections.abc import Sequence
from typing import Any

import pytest
from reflex_base.utils.exceptions import VarTypeError
from reflex_base.vars.base import LiteralVar, Var
from reflex_base.vars.number import BooleanVar, NumberVar
from reflex_base.vars.sequence import ArrayVar, LiteralArrayVar, StringVar
from reflex_base.vars.set import LiteralSetVar, SetVar

import reflex as rx


def _tags() -> SetVar[set[str]]:
    return Var(_js_expr="state.tags").to(set[str])


def test_set_literal_is_a_set_var():
    """A set literal renders as a sorted array and is typed by its elements."""
    var = LiteralVar.create({"b", "a"})
    typing.assert_type(var, LiteralSetVar[set[str]])
    assert isinstance(var, LiteralSetVar)
    assert var._var_type == set[str]
    assert str(var) == '["a", "b"]'
    assert var.json() == '["a", "b"]'


def test_frozenset_literal_is_a_set_var():
    """A frozenset literal keeps its frozenset type."""
    var = LiteralVar.create(frozenset({3, 1, 2}))
    typing.assert_type(var, LiteralSetVar[frozenset[int]])
    assert var._var_type == frozenset[int]
    assert str(var) == "[1, 2, 3]"
    assert LiteralVar.create(frozenset()).json() == "[]"


def test_set_literal_with_incomparable_elements():
    """Elements that do not sort stay in the set's own order."""
    var = LiteralVar.create({1, "a"})
    assert str(var) in ('[1, "a"]', '["a", 1]')


def test_set_literal_holds_vars():
    """A set literal carries the var data of its elements."""
    inner = Var(_js_expr="x", _var_type=str).guess_type()
    var = LiteralVar.create({inner})
    assert str(var) == "[x]"
    assert LiteralSetVar._get_all_var_data_without_creating_var({inner}) is None


def test_set_typed_var_guesses_set_var():
    """A var annotated set[T] or frozenset[T] becomes a SetVar, not an ArrayVar."""
    tags = _tags()
    assert isinstance(tags, SetVar)
    assert not isinstance(tags, ArrayVar)
    frozen = Var(_js_expr="f", _var_type=frozenset[int]).guess_type()
    assert isinstance(frozen, SetVar)
    assert isinstance(Var(_js_expr="s", _var_type=set).guess_type(), SetVar)
    assert isinstance(Var(_js_expr="s").to(set[str]), SetVar)
    typing.assert_type(Var(_js_expr="s").to(set[str]), SetVar[set[str]])
    typing.assert_type(Var(_js_expr="s").to(frozenset[str]), SetVar[frozenset[str]])
    assert isinstance(Var(_js_expr="l", _var_type=list[str]).guess_type(), ArrayVar)


def test_set_contains_and_length():
    tags = _tags()
    contains = tags.contains("x")
    typing.assert_type(contains, BooleanVar)
    assert isinstance(contains, BooleanVar)
    assert str(contains) == 'state.tags.includes("x")'
    assert str(tags.has("x")) == 'state.tags.includes("x")'
    length = tags.length()
    typing.assert_type(length, NumberVar[int])
    assert str(length) == "state.tags.length"
    assert str(tags.size()) == "state.tags.length"


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("union", "[...new Set([...state.tags, ...state.other])]"),
        (
            "intersection",
            "((a, b) => a.filter((x) => b.has(x)))(state.tags, new Set(state.other))",
        ),
        (
            "difference",
            "((a, b) => a.filter((x) => !b.has(x)))(state.tags, new Set(state.other))",
        ),
        (
            "symmetric_difference",
            (
                "((a, b) => [...[...a].filter((x) => !b.has(x)), ...[...b].filter((x) => !a.has(x))])"
                "(new Set(state.tags), new Set(state.other))"
            ),
        ),
    ],
)
def test_set_combinations_return_set_vars(operation: str, expected: str):
    tags = _tags()
    other = Var(_js_expr="state.other", _var_type=set[str]).guess_type()
    result = getattr(tags, operation)(other)
    assert isinstance(result, SetVar)
    assert result._var_type == set[str]
    assert str(result) == expected


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        (
            "issubset",
            "((a, b) => a.every((x) => b.has(x)))(state.tags, new Set(state.other))",
        ),
        (
            "issuperset",
            "((a, b) => b.every((x) => a.has(x)))(new Set(state.tags), state.other)",
        ),
        (
            "isdisjoint",
            "((a, b) => !a.some((x) => b.has(x)))(state.tags, new Set(state.other))",
        ),
    ],
)
def test_set_comparisons_return_boolean_vars(operation: str, expected: str):
    tags = _tags()
    other = Var(_js_expr="state.other", _var_type=set[str]).guess_type()
    result = getattr(tags, operation)(other)
    assert isinstance(result, BooleanVar)
    assert str(result) == expected


def test_set_operations_accept_literals_and_arrays():
    """The other operand may be a python set, frozenset, list, tuple or an array var."""
    tags = _tags()
    assert str(tags.union({"z"})) == '[...new Set([...state.tags, ...["z"]])]'
    assert (
        str(tags.union(frozenset({"z"}))) == '[...new Set([...state.tags, ...["z"]])]'
    )
    assert str(tags.issubset(["a", "b"])) == (
        '((a, b) => a.every((x) => b.has(x)))(state.tags, new Set(["a", "b"]))'
    )
    items = Var(_js_expr="state.items", _var_type=list[int]).guess_type()
    union = tags.union(items)
    assert union._var_type == set[str | int]
    assert str(tags.intersection(("a",))) == (
        '((a, b) => a.filter((x) => b.has(x)))(state.tags, new Set(["a"]))'
    )


def test_set_operations_keep_frozenset_type():
    frozen = Var(_js_expr="f").to(frozenset[int])
    assert frozen.union({1.5})._var_type == frozenset[int | float]
    assert frozen.intersection({1})._var_type == frozenset[int]
    assert frozen.symmetric_difference({"a"})._var_type == frozenset[int | str]


def test_untyped_set_operations():
    """A bare set type has Any elements."""
    bare = Var(_js_expr="s").to(set)
    assert bare.union({1})._var_type == set[Any | int]
    assert bare.intersection({1})._var_type is set
    assert bare.to_array()._var_type == Sequence[Any]


@pytest.mark.parametrize(
    "operation",
    [
        "union",
        "intersection",
        "difference",
        "symmetric_difference",
        "issubset",
        "issuperset",
        "isdisjoint",
    ],
)
def test_set_operations_reject_other_operands(operation: str):
    with pytest.raises(VarTypeError):
        getattr(_tags(), operation)(1)
    with pytest.raises(VarTypeError):
        getattr(_tags(), operation)(Var(_js_expr="n", _var_type=int).guess_type())


def test_set_to_array():
    """The array view is the same JS expression, typed as a sequence."""
    tags = _tags()
    array = tags.to_array()
    typing.assert_type(array, ArrayVar[Sequence[str]])
    assert isinstance(array, ArrayVar)
    assert array._var_type == Sequence[str]
    assert str(array) == "state.tags"
    first = array[0]
    typing.assert_type(first, StringVar)
    assert str(first) == "state.tags?.at?.(0)"
    assert re.fullmatch(
        r"state\.tags\.map\(\(\((\w+)\) => \1\.toUpperCase\(\)\)\)",
        str(array.map(lambda item: item.upper())),
    )
    frozen = Var(_js_expr="f").to(frozenset[int])
    typing.assert_type(frozen.to_array(), ArrayVar[Sequence[int]])
    assert frozen.to_array()._var_type == Sequence[int]


def test_set_array_operations_are_deprecated(mocker):
    """Sequence operations still work on a set var, with a deprecation warning."""
    deprecate = mocker.patch("reflex_base.vars.set.console.deprecate")
    tags = _tags()

    assert str(tags[0]) == "state.tags?.at?.(0)"  # pyright: ignore[reportDeprecated]
    deprecate.assert_called_once()
    assert deprecate.call_args.kwargs["feature_name"] == "SetVar.__getitem__"
    assert ".to_array()" in deprecate.call_args.kwargs["reason"]

    deprecate.reset_mock()
    assert re.fullmatch(
        r"state\.tags\.map\(\(\((\w+)\) => \1\.toUpperCase\(\)\)\)",
        str(tags.map(lambda item: item.upper())),  # pyright: ignore[reportDeprecated]
    )
    assert deprecate.call_args.kwargs["feature_name"] == "SetVar.map"

    deprecate.reset_mock()
    assert str(tags.join(",")) == 'state.tags.join(",")'  # pyright: ignore[reportDeprecated]
    assert str(tags.reverse()) == "state.tags.slice().reverse()"  # pyright: ignore[reportDeprecated]
    assert str(tags * 2) == (  # pyright: ignore[reportDeprecated]
        "Array.from({ length: 2 }).flatMap(() => state.tags)"
    )
    assert str(tags + tags.to_array()) == "[...state.tags, ...state.tags]"  # pyright: ignore[reportDeprecated]
    assert str(tags.filter(lambda item: item == "a")).startswith("state.tags.filter(")  # pyright: ignore[reportDeprecated]
    assert str(tags.reduce(operator.add, "")).startswith("state.tags.reduce(")  # pyright: ignore[reportDeprecated]
    assert str(tags.flat_map(lambda item: item)).startswith("pyFlatMap(state.tags")  # pyright: ignore[reportDeprecated]
    assert str(tags.pluck("a")).startswith("state.tags.map(")  # pyright: ignore[reportDeprecated]
    assert deprecate.call_count == 8


def test_state_set_fields_are_set_vars():
    """Set-typed state fields and computed vars are typed as SetVar statically and at runtime."""

    class SetState(rx.State):
        tags: rx.Field[set[str]] = rx.field({"a"})
        maybe: rx.Field[set[str] | None] = rx.field(None)

        @rx.var
        def doubled(self) -> set[str]:
            return {tag * 2 for tag in self.tags}

    typing.assert_type(SetState.tags, SetVar[set[str]])
    typing.assert_type(SetState.maybe, SetVar[set[str]])
    typing.assert_type(SetState.doubled, SetVar[set[str]])
    typing.assert_type(SetState.tags.contains("x"), BooleanVar)
    assert isinstance(SetState.tags, SetVar)
    assert isinstance(SetState.maybe, SetVar)
    assert isinstance(SetState.doubled, SetVar)
    assert SetState.tags.to_array()._var_type == Sequence[str]


def test_foreach_accepts_a_set_var():
    """rx.foreach iterates the array view of a set var."""
    tags = _tags()
    component = rx.foreach(tags, lambda tag: rx.text(tag))
    assert component.iterable._var_type == Sequence[str]
    assert str(component.iterable) == "state.tags"
    literal = rx.foreach({"a", "b"}, lambda tag: rx.text(tag))
    assert str(literal.iterable) == '["a", "b"]'


def test_set_inside_array_literal():
    """A set nested in an array literal still renders as an array."""
    var = LiteralVar.create([{2, 1}, "x"])
    assert isinstance(var, LiteralArrayVar)
    assert str(var) == '[[1, 2], "x"]'
    assert var.json() == '[[1, 2], "x"]'
