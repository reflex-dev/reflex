"""Claim A in rx.ComponentState.get_component and a foreach over a backend constant.

Usage: <venv>/bin/python derive_a_componentstate.py <expected-venv-name>
"""

import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class Counter(rx.ComponentState):
    count: int = 0
    _step = 5
    _OPTIONS = ["a", "b"]

    @rx.event
    def incr(self):
        self.count += self._step

    @classmethod
    def get_component(cls, **props):
        return rx.button(f"+{cls._step}", on_click=cls.incr, **props)


def t(label, fn):
    try:
        print(f"{label}: {str(fn())[:150]}")
    except Exception as e:  # noqa: BLE001
        print(f"{label}: EXC {type(e).__name__}: {str(e)[:150]}")


t("Counter.create() button label (f-string of cls._step)", lambda: str(Counter.create())[-90:])
t("rx.foreach(Counter._OPTIONS, rx.text)", lambda: rx.foreach(Counter._OPTIONS, rx.text))
root = rx.State(_reflex_internal_init=True)
