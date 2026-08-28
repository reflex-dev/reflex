"""Repro: PEP695 aliases annotating event handler args of UNCALLED handlers.

Run (Python 3.12+): python repro_alias_event_arg.py

reflex 0.9.9a1 resolves TypeAliasType in Var.guess_type (PR #6944) but NOT in
typehint_issubclass, so passing a handler uncalled to an event trigger fails:

  1. bare alias (type Key = Literal[...]) as arg annotation ->
     TypeError: Could not compare types <class 'str'> and Key ...
     (typehint_issubclass raises "issubclass() arg 2 must be a class")
  2. parameterized alias (Pair[str, str] for type Pair[K, V] = dict[K, V]) ->
     EventHandlerArgTypeMismatchError: Event handler on_submit expects
     dict[str, typing.Any] for argument form_data but got Pair[str, str]
     (typehint_issubclass returns False instead of resolving the alias)

Both are fatal at page compile. Workarounds: pre-call the handler
(S.choose("a")) or wrap in a lambda (lambda v: S.choose(v)).
0.9.8 behaves the same (state vars crashed earlier there), so this is a
coverage gap of the new alias support, not a regression.
"""

from typing import Literal

import reflex as rx

type Key = Literal["a", "b"]
type Pair[K, V] = dict[K, V]


class S(rx.State):
    k: Key = "a"

    @rx.event
    def choose(self, value: Key):
        self.k = value

    @rx.event
    def submit(self, form_data: Pair[str, str]):
        pass


shapes = {
    "uncalled handler, bare Literal alias (on_change=S.choose)": lambda: rx.input(
        on_change=S.choose
    ),
    "uncalled handler, parameterized alias (on_submit=S.submit)": lambda: rx.form(
        on_submit=S.submit
    ),
    "pre-called handler (on_click=S.choose('a'))": lambda: rx.button(
        on_click=S.choose("a")
    ),
    "lambda wrapper (on_change=lambda v: S.choose(v))": lambda: rx.input(
        on_change=lambda v: S.choose(v)
    ),
    "lambda wrapper, parameterized alias (on_submit=lambda d: S.submit(d))": (
        lambda: rx.form(on_submit=lambda d: S.submit(d))
    ),
}
for name, fn in shapes.items():
    try:
        fn()
        print(f"OK   : {name}")
    except Exception as e:
        print(f"CRASH: {name} -> {type(e).__name__}: {e}")
