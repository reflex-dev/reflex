"""Why reflexle never shows the "Word is ..." banner after six wrong guesses.

Drives the real Reflexle state class in-process and prints the delta the frontend would
receive, next to the condition the compiler emitted for
`rx.cond(Reflexle.game_status == GameStatus.LOST, ...)`:

    .web/app_components/reflexle/reflexle.jsx:
    (state.game_status_rx_state_?.valueOf?.() === 2?.valueOf?.()) ? ... : ...

Run from the reflexle app dir (never from a reflex checkout):
  cd $SB/apps/up_nba_reflexle/reflexle && \
    REFLEX_TELEMETRY_ENABLED=false $SB/envs/up_nba_reflexle/bin/python \
      ../repro_reflexle_enum_delta.py
"""

import importlib.metadata as md
import json

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
print("reflex from:", rx.__file__, "version:", md.version("reflex"))

import importlib

mod = importlib.import_module("reflexle.reflexle")
if not hasattr(mod, "GameStatus"):
    mod = importlib.import_module("reflexle.reflexle.reflexle")
GameStatus, Reflexle = mod.GameStatus, mod.Reflexle  # noqa: E402

state = Reflexle(_reflex_internal_init=True)
state._clean()

# six guesses that are all in valid_guess but never in possible_solution -> guaranteed LOST
for word in ("homes", "gawks", "bumph", "vexed", "quips", "mylar"):
    state.current_guess = word
    Reflexle.event_handlers["received_letter"].fn(state, "Enter")

delta = state.get_delta()
substate_delta = next(iter(delta.values()))
print("\nbackend truth:")
print("  state.game_status =", repr(state.game_status), "== GameStatus.LOST ->", state.game_status == GameStatus.LOST)
print("  state.correct_word =", repr(state.correct_word))
print("\ndelta the frontend receives for game_status / correct_word:")
for key in ("game_status_rx_state_", "correct_word_rx_state_", "guesses_count_rx_state_"):
    val = substate_delta.get(key, "<ABSENT>")
    print(f"  {key} = {val!r}  (type {type(val).__name__})")

print("\nJSON-serialized (what actually goes over the socket):")
try:
    from reflex.utils.format import json_dumps  # type: ignore

    print(" ", json_dumps({k: v for k, v in substate_delta.items() if "game_status" in k or "correct_word" in k}))
except Exception as exc:  # noqa: BLE001
    print("  json_dumps unavailable:", exc)
    print(" ", json.dumps({k: str(v) for k, v in substate_delta.items() if "game_status" in k}))

gs = substate_delta.get("game_status_rx_state_")
print("\nfrontend comparison `game_status === 2` would be:", gs == 2, f"(delta value {gs!r})")
print("GameStatus.LOST.value =", GameStatus.LOST.value)
