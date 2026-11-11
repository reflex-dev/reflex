"""ES-2: which coroutine stays unawaited when a get_delta override withholds an async cache=False var.

Run: cd $SB/apps/verify_es && EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_es2.py
Three filter styles: pop the key without closing the coroutine (the explorer's repro), pop + .close() (what
reflex-enterprise's enforcement.py does and what PR #7410's tests do), and no withholding. Also counts how often the
user's async var body actually ran, to tell a leaked wrapper from a leaked user computation.
"""

import asyncio
import gc
import importlib.metadata
import os
import warnings

import reflex as rx
from reflex.istate.delta import resolve_delta

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__
print("reflex", importlib.metadata.version("reflex"))

BODY_RUNS = {"n": 0}
MODE = {"v": "none"}  # none | pop | pop_close


class AState(rx.State):
    n: int = 0

    @rx.var(cache=False)
    async def av(self) -> int:
        BODY_RUNS["n"] += 1
        await asyncio.sleep(0)
        return self.n * 10

    @rx.state._override_base_method
    def get_delta(self):
        delta = super().get_delta()
        sub = delta.get(self.get_full_name(), {})
        if MODE["v"] != "none":
            value = sub.pop("av_rx_state_", None)
            if MODE["v"] == "pop_close" and asyncio.iscoroutine(value):
                value.close()
        return delta


async def case(mode: str):
    MODE["v"] = mode
    BODY_RUNS["n"] = 0
    s = AState(_reflex_internal_init=True)
    s.n = 1
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        delta = await resolve_delta(s)
        del s
        gc.collect()
        await asyncio.sleep(0)
        gc.collect()
    keys = sorted(k.replace("_rx_state_", "") for k in delta.get(AState.get_full_name(), {}))
    print(f"mode={mode:9} delta keys={keys} body_runs={BODY_RUNS['n']} warnings={[(x.category.__name__, str(x.message)) for x in w]}")


for m in ("none", "pop", "pop_close"):
    asyncio.run(case(m))
