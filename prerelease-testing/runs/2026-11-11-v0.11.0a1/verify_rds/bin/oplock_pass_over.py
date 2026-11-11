"""Deterministic-ish in-process repro of the oplock "second waiter on the same instance is passed over" stall.

Two StateManagerRedis instances (A, B) with oplock on share one redis, like two granian workers.
Per trial: A1 holds the lock under a lease; B1 and B2 (two waiters on instance B) and A2 queue behind it.
Measures how long each waiter waits to enter modify_state. A stall ~= lock_expiration/10 (1 s default) means a
waiter was passed over by a lease taken while it was still queued.

--patch applies a TEST-ONLY variant of `_request_lock_release` that only SREMs the instance from
`<lock>_waiters` when the exiting waiter is the instance's last local waiter (the suspected fix shape).

Usage: <venv>/bin/python oplock_pass_over.py <expected venv name> REDIS_PORT [--trials N] [--patch]
"""

import argparse
import asyncio
import contextlib
import json
import sys
import time
import uuid

import reflex

ap = argparse.ArgumentParser()
ap.add_argument("venv")
ap.add_argument("port")
ap.add_argument("--trials", type=int, default=20)
ap.add_argument("--patch", action="store_true")
ap.add_argument("--out", default="")
ap.add_argument("--a2-delay", type=float, default=0.02)
ap.add_argument("--b2-delay", type=float, default=0.01)
ap.add_argument("--verbose", action="store_true")
ap.add_argument("--burst", type=int, default=0)
ap.add_argument("--debug", action="store_true")
ap.add_argument("--a-gap", type=float, default=0.0, help="stream mode: sleep between A modifies (outside the lock)")
ap.add_argument("--a-events", type=int, default=300)
ap.add_argument("--no-oplock", action="store_true")
ap.add_argument("--stream", type=int, default=0, help="B concurrency per round in stream mode (0 = off)")
a = ap.parse_args()
assert f"/envs/{a.venv}/" in reflex.__file__, reflex.__file__

from redis.asyncio import Redis  # noqa: E402
from reflex.istate.manager.redis import StateManagerRedis  # noqa: E402
from reflex.istate.manager.token import BaseStateToken  # noqa: E402
from reflex.state import BaseState  # noqa: E402


class PassOverRoot(BaseState):
    """Root state for the repro."""

    count: int = 0


if a.patch:

    @contextlib.asynccontextmanager
    async def _request_lock_release(self, lock_key, lock_id):
        if not self._oplock_enabled:
            yield
            return
        await self._register_lock_contender(lock_key)
        try:
            yield
        finally:
            # The exiting waiter is still in the local list here (the _lock_waiter context is outer).
            if self._n_lock_waiters(lock_key) <= 1:
                await self.redis.srem(lock_key + b"_waiters", self._instance_id)

    StateManagerRedis._request_lock_release = _request_lock_release


async def mk():
    m = StateManagerRedis(redis=Redis.from_url(f"redis://localhost:{a.port}"))
    m._oplock_enabled = not a.no_oplock
    m._debug_enabled = a.debug
    await m._ensure_lock_task_subscribed()
    return m


async def trial(A, B):
    tok = BaseStateToken(ident=str(uuid.uuid4()), cls=PassOverRoot)
    waits = {}
    a1_in = asyncio.Event()

    async def mod(name, mgr, hold, delay=0.0):
        await asyncio.sleep(delay)
        t0 = time.monotonic()
        async with mgr.modify_state(tok) as st:
            waits[name] = round(time.monotonic() - t0, 3)
            st.count += 1
            if name == "A1":
                a1_in.set()
            await asyncio.sleep(hold)

    t_start = time.monotonic()
    a1 = asyncio.create_task(mod("A1", A, 0.3))
    await a1_in.wait()
    if a.burst:
        # N waiters per instance, staggered by 7 ms (A) and 11 ms (B), each holding 20 ms.
        others = [asyncio.create_task(mod(f"A{i + 2}", A, 0.02, i * 0.007)) for i in range(a.burst)]
        others += [asyncio.create_task(mod(f"B{i + 1}", B, 0.02, i * 0.011)) for i in range(a.burst)]
    else:
        others = [
            asyncio.create_task(mod("B1", B, 0.05)),
            asyncio.create_task(mod("B2", B, 0.05, a.b2_delay)),
            asyncio.create_task(mod("A2", A, 0.05, a.a2_delay)),
        ]
    await asyncio.gather(a1, *others)
    total = round(time.monotonic() - t_start, 3)
    # Locked read from a third instance: forces A/B leases to break and flush.
    C = await mk()
    async with C.modify_state(tok) as st:
        final = st.count
    await C.close()
    return {"waits": waits, "total_s": total, "final": final, "max_wait": max(waits.values())}


async def stream_trial(A, B):
    """A runs 300 back-to-back modifies (like pipelined socket events on its worker) while B runs 20 rounds of
    `--stream` concurrent modifies (like concurrent /api/bump requests that landed on the other worker)."""
    tok = BaseStateToken(ident=str(uuid.uuid4()), cls=PassOverRoot)
    b_waits = []
    a_done = asyncio.Event()

    async def one(mgr, hold):
        t0 = time.monotonic()
        async with mgr.modify_state(tok) as st:
            w = time.monotonic() - t0
            st.count += 1
            await asyncio.sleep(hold)
        return w

    async def a_side():
        asyncio.current_task().set_name("A-side")
        for _ in range(a.a_events):
            await one(A, 0.002)
            if a.a_gap:
                await asyncio.sleep(a.a_gap)
        a_done.set()

    async def b_side():
        asyncio.current_task().set_name("B-side")
        await asyncio.sleep(0.05)
        for _ in range(20):
            if a.debug:
                logging.getLogger("passover").debug(f"B ROUND {len(b_waits)} start")
            b_waits.extend(await asyncio.gather(*[one(B, 0.002) for _ in range(a.stream)]))
            if a.debug:
                logging.getLogger("passover").debug(f"B ROUND done waits={b_waits[-a.stream:]}")
            await asyncio.sleep(0.03)

    t0 = time.monotonic()
    await asyncio.gather(a_side(), b_side())
    total = round(time.monotonic() - t0, 3)
    C = await mk()
    async with C.modify_state(tok) as st:
        final = st.count
    await C.close()
    return {"total_s": total, "final": final, "expected": a.a_events + 20 * a.stream, "b_over_0.8s": sum(w > 0.8 for w in b_waits),
            "b_max": round(max(b_waits), 3), "b_stall_idx": [i for i, w in enumerate(b_waits) if w > 0.8], "b_p50": round(sorted(b_waits)[len(b_waits) // 2], 3)}


async def main():
    A, B = await mk(), await mk()
    if a.stream:
        rs = [await stream_trial(A, B) for _ in range(a.trials)]
        await A.close()
        await B.close()
        summ = {"venv": a.venv, "patched": a.patch, "oplock": not a.no_oplock, "mode": "stream", "b_concurrency": a.stream, "a_gap": a.a_gap, "a_events": a.a_events, "trials": a.trials,
                "final_ok": sum(r["final"] == r["expected"] for r in rs), "trials_with_b_wait_over_0.8s": sum(r["b_over_0.8s"] > 0 for r in rs),
                "b_waits_over_0.8s_total": sum(r["b_over_0.8s"] for r in rs), "b_max": [r["b_max"] for r in rs], "b_stall_idx": [r["b_stall_idx"] for r in rs], "totals": [r["total_s"] for r in rs]}
        print(json.dumps(summ))
        if a.out:
            with open(a.out, "a") as f:
                f.write(json.dumps(summ) + "\n")
        return
    res = []
    for _ in range(a.trials):
        res.append(await trial(A, B))
        if a.verbose:
            print(json.dumps(res[-1]))
    await A.close()
    await B.close()
    summ = {
        "venv": a.venv,
        "patched": a.patch,
        "a2_delay": a.a2_delay,
        "b2_delay": a.b2_delay,
        "trials": a.trials,
        "lock_expiration_ms": A.lock_expiration,
        "oplock_hold_time_ms": A.oplock_hold_time_ms,
        "burst": a.burst,
        "final_counts_ok": sum(r["final"] == (1 + 2 * a.burst if a.burst else 4) for r in res),
        "trials_with_wait_over_0.8s": sum(r["max_wait"] > 0.8 for r in res),
        "max_waits": sorted(r["max_wait"] for r in res),
        "stalled_waiter_names": [k for r in res for k, v in r["waits"].items() if v > 0.8],
        "totals": [r["total_s"] for r in res],
    }
    print(json.dumps(summ))
    if a.out:
        with open(a.out, "a") as f:
            f.write(json.dumps(summ) + "\n")


if a.debug:
    import logging

    logging.basicConfig(level=logging.DEBUG, format="%(relativeCreated)8.1f %(taskName)s %(message)s", filename=a.out + ".debug.log", filemode="w")

asyncio.run(main())
