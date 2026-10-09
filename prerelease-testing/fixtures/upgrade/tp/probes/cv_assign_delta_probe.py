"""A computed var that assigns another state var while it is computed (reflex-google-auth's
GoogleAuthState.tokeninfo does this to drop an invalid token). Is the assignment in the delta?

Usage: <venv>/bin/python cv_assign_delta_probe.py <expected-venv-name>
"""
import asyncio
import json
import sys

import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class TokState(rx.State):
    tok: str = rx.LocalStorage(name="tok")
    plain: str = ""

    @rx.var(cache=True)
    def tok_check(self) -> str:
        if self.tok == "bad":
            self.tok = ""
            return "cleared"
        return f"value={self.tok!r}"

    @rx.var(cache=True)
    def plain_check(self) -> str:
        if self.plain == "bad":
            self.plain = "fixed-by-cv"
            return "fixed"
        return f"value={self.plain!r}"


def short(delta):
    out = {}
    for state_name, fields in delta.items():
        if "tok_state" in state_name:
            out = {k: v for k, v in fields.items()}
    return out


async def main():
    root = rx.State(_reflex_internal_init=True)
    s = root.get_substate(TokState.get_full_name().split(".")[1:])
    # 1) plain var set to a value the computed var rewrites
    s.plain = "bad"
    d1 = root.get_delta()
    if asyncio.iscoroutine(d1):
        d1 = await d1
    print("delta after plain='bad':", json.dumps(short(d1)))
    print("  backend plain now:", repr(s.plain))
    root._clean()
    d1b = root.get_delta()
    if asyncio.iscoroutine(d1b):
        d1b = await d1b
    print("  next delta (after _clean, no further change):", json.dumps(short(d1b)))
    root._clean()
    # 2) LocalStorage var set to a value the computed var clears (to the default "")
    s.tok = "bad"
    d2 = root.get_delta()
    if asyncio.iscoroutine(d2):
        d2 = await d2
    print("delta after tok='bad':", json.dumps(short(d2)))
    print("  backend tok now:", repr(s.tok))
    root._clean()
    d2b = root.get_delta()
    if asyncio.iscoroutine(d2b):
        d2b = await d2b
    print("  next delta (after _clean, no further change):", json.dumps(short(d2b)))
    # full dict view, like a hydrate
    print("  dict():", json.dumps({k: v for k, v in root.dict().items()}, default=str)[:0] or "", end="")


asyncio.run(main())
