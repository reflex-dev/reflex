"""Independent verifier repro for BUG 1 (0.9.9a1, Python 3.12+).

Uncalled event handler whose arg is annotated with a PEP 695 alias, passed to a
component event trigger. Expected per claim:
  - bare alias -> TypeError: Could not compare types ...
  - parameterized alias -> EventHandlerArgTypeMismatchError
  - pre-called / lambda-wrapped -> OK
Extra refutation probe: the SAME annotation written as an old-style implicit
alias (Key2 = Literal[...]) should work, isolating TypeAliasType as the trigger.
"""

import traceback
from typing import Literal

import reflex as rx

type Key = Literal["a", "b"]
type Pair[K, V] = dict[K, V]

OldKey = Literal["a", "b"]


class S(rx.State):
    k: Key = "a"

    @rx.event
    def choose(self, value: Key):
        self.k = value

    @rx.event
    def choose_old(self, value: OldKey):
        self.k = value

    @rx.event
    def submit(self, form_data: Pair[str, str]):
        pass


cases = [
    ("bare alias, uncalled (on_change=S.choose)", lambda: rx.input(on_change=S.choose)),
    ("param alias, uncalled (on_submit=S.submit)", lambda: rx.form(on_submit=S.submit)),
    ("old-style Literal alias, uncalled (on_change=S.choose_old)",
     lambda: rx.input(on_change=S.choose_old)),
    ("pre-called (on_click=S.choose('a'))", lambda: rx.button(on_click=S.choose("a"))),
    ("lambda wrapped (on_change=lambda v: S.choose(v))",
     lambda: rx.input(on_change=lambda v: S.choose(v))),
    ("lambda wrapped param alias (on_submit=lambda d: S.submit(d))",
     lambda: rx.form(on_submit=lambda d: S.submit(d))),
]

for name, fn in cases:
    try:
        fn()
        print(f"OK    | {name}")
    except Exception as e:
        print(f"CRASH | {name} -> {type(e).__name__}: {e}")

print("\n-- full traceback of the bare-alias case --")
try:
    rx.input(on_change=S.choose)
except Exception:
    traceback.print_exc()
