"""Baseline check on reflex 0.9.8 (Python 3.12): handler-arg-only alias usage.

State var stays plain `str` (alias-annotated state vars crash at class
definition on 0.9.8 - separate, fixed by #6944). Only handler args use the
PEP 695 aliases. Claim: 0.9.8 fails identically on the uncalled forms.
"""

from typing import Literal

import reflex as rx

type Key = Literal["a", "b"]
type Pair[K, V] = dict[K, V]


class S(rx.State):
    k: str = "a"

    @rx.event
    def choose(self, value: Key):
        self.k = value

    @rx.event
    def submit(self, form_data: Pair[str, str]):
        pass


cases = [
    ("bare alias, uncalled (on_change=S.choose)", lambda: rx.input(on_change=S.choose)),
    ("param alias, uncalled (on_submit=S.submit)", lambda: rx.form(on_submit=S.submit)),
    ("pre-called (on_click=S.choose('a'))", lambda: rx.button(on_click=S.choose("a"))),
    ("lambda wrapped (on_change=lambda v: S.choose(v))",
     lambda: rx.input(on_change=lambda v: S.choose(v))),
]

for name, fn in cases:
    try:
        fn()
        print(f"OK    | {name}")
    except Exception as e:
        print(f"CRASH | {name} -> {type(e).__name__}: {e}")
