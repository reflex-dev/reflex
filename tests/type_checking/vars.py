"""Inferred types for `reflex.vars` that are part of the public contract."""

from typing import Any, Literal

from typing_extensions import assert_type

from reflex.vars.base import Var
from reflex.vars.number import (
    BooleanVar,
    LiteralBooleanVar,
    LiteralNumberVar,
    NumberVar,
)
from reflex.vars.sequence import LiteralArrayVar, LiteralStringVar, StringVar

# `Var.create` dispatches on the value type through a long overload set. Each of
# these picked `LiteralBooleanVar` while `Var.bool` shadowed the builtin `bool`
# in the `value: bool` annotation of the second overload.
assert_type(Var.create(True), LiteralBooleanVar)
assert_type(Var.create(1), LiteralNumberVar[int])
assert_type(Var.create(1.5), LiteralNumberVar[float])
assert_type(Var.create("x"), LiteralStringVar[Literal["x"]])
assert_type(Var.create([1, 2]), LiteralArrayVar[list[int]])
# Not asserted: `Var.create({"a": 1})`. pyright infers `LiteralObjectVar[dict[str,
# int]]`, ty infers `dict[Unknown, int]` for the key. Only assert what every
# checker agrees on, or this file stops being a gate for the ones that disagree.

# `Var.to` selects its return type from the requested output type. The `bool`
# overload was shadowed the same way.
_any_var: Var[Any] = Var.create(None)
assert_type(_any_var.to(bool), BooleanVar)
assert_type(_any_var.to(str), StringVar[str])
assert_type(_any_var.to(int), NumberVar[int])

# `guess_type` narrows on the declared inner type via a `self` annotation, so
# the `Var[bool]` overload is the one the `bool` shadow affected.
_bool_var: Var[bool] = Var("expr")
_str_var: Var[str] = Var("expr")
assert_type(_bool_var.guess_type(), BooleanVar)
assert_type(_str_var.guess_type(), StringVar[str])
