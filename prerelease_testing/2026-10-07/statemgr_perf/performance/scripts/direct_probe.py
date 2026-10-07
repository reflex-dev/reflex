"""Public manager-created state probes; timings require explicit quiet authorization."""

import argparse
import asyncio
import importlib.metadata
import json
import os
import statistics
import time
from pathlib import Path
import reflex as rx
from reflex.istate.manager.memory import StateManagerMemory

assert str(Path(os.environ["REFLEX_EXPECT_ENV"]) / "lib") in rx.__file__, rx.__file__


class DirectState(rx.State):
    """One scalar field for isolated read/write method measurements."""

    counter: int = 1


async def probe(smoke: bool, repeats: int) -> dict:
    """Use a supported state manager rather than privately instantiating State.

    Args:
        smoke: Perform correctness checks without collecting timings.
        repeats: Number of measured loop repetitions in this process.

    Returns:
        Correctness result and optional three-repeat timing samples.
    """
    manager = StateManagerMemory()
    root = await manager.get_state(
        rx.BaseStateToken(ident="isolated-probe", cls=DirectState)
    )
    state = await root.get_state(DirectState)
    state.counter = 2
    assert state.counter == 2
    result = {
        "reflex": importlib.metadata.version("reflex"),
        "path": rx.__file__,
        "mode": os.environ.get("REFLEX_ENV_MODE", "dev"),
        "smoke": smoke,
    }
    try:
        if smoke:
            return result
        assert os.environ.get("PERF_QUIET_CONFIRMED") == "1", (
            "Timing is blocked until the parent confirms a quiet machine."
        )
        rows = []
        count = 100000
        for repeat in range(repeats):
            state.counter = 2
            started = time.perf_counter_ns()
            checksum = 0
            for _ in range(count):
                checksum += state.counter
            reads = time.perf_counter_ns() - started
            assert checksum == 2 * count
            started = time.perf_counter_ns()
            for value in range(count):
                state.counter = value
            writes = time.perf_counter_ns() - started
            assert state.counter == count - 1
            rows.append(
                {
                    "repeat": repeat,
                    "reads_ns": reads,
                    "writes_ns": writes,
                    "checksum": checksum,
                }
            )
        result.update(
            count=count,
            samples=rows,
            median_read_ns_per_op=statistics.median(
                r["reads_ns"] / count for r in rows
            ),
            median_write_ns_per_op=statistics.median(
                r["writes_ns"] / count for r in rows
            ),
        )
        return result
    finally:
        await manager.close()


parser = argparse.ArgumentParser()
parser.add_argument("--smoke", action="store_true")
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
print(json.dumps(asyncio.run(probe(args.smoke, args.repeats)), indent=1))
