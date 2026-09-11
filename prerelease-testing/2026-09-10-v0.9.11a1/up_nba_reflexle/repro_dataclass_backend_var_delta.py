"""Minimal repro for the reflexle "Word is ..." banner never appearing.

A cached @rx.var that depends ONLY on a private (backend) var holding a mutable dataclass is
NOT included in the delta when the handler mutates that dataclass in place -- while a var that
also depends on a plain public var IS recomputed and sent. The backend value is right; only the
frontend never learns about it.

Run from this directory (never from a reflex checkout):
  cd $SB/apps/up_nba_reflexle && $SB/envs/up_nba_reflexle/bin/python repro_dataclass_backend_var_delta.py
"""

import asyncio
import sys
from dataclasses import dataclass, field

import reflex as rx

assert "/envs/up_nba_" in rx.__file__ or "/envs/" in rx.__file__, rx.__file__
print("reflex from:", rx.__file__)
import importlib.metadata as md

print("reflex version:", md.version("reflex"))


@dataclass
class Game:
    guesses: list[str] = field(default_factory=list)

    def guess(self, word: str):
        self.guesses.append(word)


class S(rx.State):
    _game: Game = Game()
    current: str = ""

    @rx.var
    def rows(self) -> list[str]:  # depends on _game AND current
        return [*self._game.guesses, self.current]

    @rx.var
    def status(self) -> str:  # depends ONLY on _game
        return "LOST" if len(self._game.guesses) >= 2 else "ONGOING"

    @rx.var
    def n_guesses(self) -> int:  # depends ONLY on _game
        return len(self._game.guesses)

    @rx.event
    def submit(self, word: str):
        self._game.guess(word)
        self.current = ""

    @rx.event
    def submit_and_reassign(self, word: str):
        """Same thing, but re-binding the attribute afterwards."""
        self._game.guess(word)
        self._game = self._game
        self.current = ""


async def main():
    app = rx.App()
    app.add_page(lambda: rx.text(S.status), route="/")

    state = S(_reflex_internal_init=True)
    print("\ninitial computed values:", state.rows, state.status, state.n_guesses)
    state._clean()

    for word in ("aaaaa", "bbbbb"):
        S.event_handlers["submit"].fn(state, word)
        delta = state.get_delta()
        state._clean()
        print(
            f"\nafter submit({word!r}):",
            f"\n  backend truth: status={state.status!r} n_guesses={state.n_guesses}",
            f"\n  delta        : {delta}",
        )
        keys = set(next(iter(delta.values())).keys()) if delta else set()
        for name in ("rows", "status", "n_guesses"):
            print(f"  {name} in delta: {name in keys}")

    # control: the same mutation followed by a re-assignment of the dataclass attribute
    state2 = S(_reflex_internal_init=True)
    state2._clean()
    S.event_handlers["submit_and_reassign"].fn(state2, "ccccc")
    delta2 = state2.get_delta()
    keys2 = set(next(iter(delta2.values())).keys()) if delta2 else set()
    print("\ncontrol (mutate + `self._game = self._game`):")
    print("  delta:", delta2)
    for name in ("rows", "status", "n_guesses"):
        print(f"  {name} in delta: {name in keys2}")

    return 0


sys.exit(asyncio.run(main()))
