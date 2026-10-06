"""Use one published version's real Redis manager to read and update state."""

import asyncio
import hashlib
import importlib.metadata
import json
import os
import pickle
import sys
from pathlib import Path

import reflex
import reflex.state
import reflex_base
from redis.asyncio import Redis
from reflex.istate.manager.redis import StateManagerRedis
from reflex.istate.manager.token import BaseStateToken
from rolling_app import Rolling

TOKEN = sys.argv[1]
ACTION = sys.argv[2]
OUT = Path(sys.argv[3])
PREFIX = sys.argv[4]
EXPECTED_VERSION = sys.argv[5]
ORIGINS = {
    module.__name__: str(Path(module.__file__).resolve())
    for module in (reflex, reflex.state, reflex_base)
}


def snapshot(state: Rolling) -> dict:
    """Read user-facing state values without serializing mutable proxies.

    Args:
        state: The loaded app state.

    Returns:
        Plain snapshots of fields and computed value.
    """
    return {
        "count": state.count,
        "label": state.label,
        "values": list(state.values),
        "secret": state._secret,
        "items": list(state._items),
        "checksum": state.checksum,
    }


async def main() -> None:
    """Modify one unique Redis token and preserve cross-version evidence."""
    assert all(path.startswith(PREFIX + "/") for path in ORIGINS.values()), ORIGINS
    assert os.environ.get("PYTHONPATH") is None
    assert not any(
        "/Users/masenf/.codex/worktrees/48e6/reflex" in path for path in sys.path
    )
    assert importlib.metadata.version("reflex") == EXPECTED_VERSION
    assert importlib.metadata.version("reflex-base") == EXPECTED_VERSION
    distributions = []
    for distribution in importlib.metadata.distributions():
        assert distribution.read_text("direct_url.json") is None, distribution.metadata[
            "Name"
        ]
        distributions.append({
            "name": distribution.metadata["Name"],
            "version": distribution.version,
        })
    client = Redis(host="localhost", port=9141, db=5)
    manager = StateManagerRedis(redis=client)
    token = BaseStateToken(ident=TOKEN, cls=Rolling)
    result = {
        "action": ACTION,
        "database": 5,
        "token": TOKEN,
        "version": EXPECTED_VERSION,
        "executable": sys.executable,
        "python": sys.version,
        "cwd": str(Path.cwd()),
        "origins": ORIGINS,
        "distributions": sorted(distributions, key=lambda value: value["name"].lower()),
    }
    try:
        assert not manager._oplock_enabled
        async with manager.modify_state(token) as root:
            state = root.get_substate(Rolling.get_full_name().split("."))
            result["before"] = snapshot(state)
            state._clean()
            state._was_touched = False
            if ACTION == "seed":
                state.count = 7
                state.label = "persisted seed"
                state.values = [1, 2]
                state._secret = 11
                state._items = ["saved"]
            elif ACTION == "assign":
                state.count = 13
                state.label = "assigned"
                state.values = [3, 4]
                state._secret = 17
                state._items = ["assigned"]
            elif ACTION == "frontend_inplace":
                state.values.append(8)
            elif ACTION == "backend_inplace":
                state._items.append("inplace")
            elif ACTION != "read":
                message = f"Unknown action: {ACTION}"
                raise ValueError(message)
            result["after_in_memory"] = snapshot(state)
            result["dirty_vars"] = sorted(state.dirty_vars)
            result["schema"] = state._to_schema()
        payload = await client.get(str(token))
        assert payload is not None
        schema, stored = pickle.loads(payload)
        result["stored_schema"] = schema
        result["stored_snapshot"] = snapshot(stored)
        result["pickle_bytes"] = len(payload)
        result["pickle_sha256"] = hashlib.sha256(payload).hexdigest()
        result["pickle_keys"] = sorted(stored.__getstate__())
        result["stored_state_key"] = str(token)
        await asyncio.to_thread(OUT.with_suffix(".pickle").write_bytes, payload)
        result["status"] = "passed"
    finally:
        await manager.close()
        await asyncio.to_thread(OUT.write_text, json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
