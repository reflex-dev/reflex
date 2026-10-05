"""Assert actual Redis persistence across old and new published workers."""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import redis

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
OLD = "/private/tmp/reflex-pre-20261005-verify-stable"
NEW = "/private/tmp/reflex-alpha-core-state/venv"
RESULTS = {"database": 5, "scenarios": [], "tokens": []}
STORE = redis.Redis(host="localhost", port=9141, db=5)


def worker(prefix: str, token: str, action: str, label: str) -> dict:
    """Execute a fresh actual published worker and collect its result.

    Args:
        prefix: The exact isolated environment directory.
        token: This scenario's unique Redis session token.
        action: The app state mutation to perform.
        label: Its evidence filename.

    Returns:
        The worker's persisted state and provenance evidence.
    """
    version = "0.9.12" if prefix == OLD else "0.10.0a1"
    output = OUT / f"{label}.json"
    environment = {
        name: value for name, value in os.environ.items() if name != "PYTHONPATH"
    }
    environment["REFLEX_OPLOCK_ENABLED"] = "false"
    process = subprocess.run(
        [
            "/Users/masenf/.local/bin/uv",
            "run",
            "--no-project",
            "--python",
            prefix + "/bin/python",
            "worker.py",
            token,
            action,
            str(output),
            prefix,
            version,
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    (OUT / f"{label}.log").write_text(process.stdout + process.stderr)
    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads(output.read_text())
    assert result["status"] == "passed"
    return result


def token() -> str:
    """Allocate a Redis session token owned only by this reproduction.

    Returns:
        The unique session token.
    """
    value = "alpha-rolling-" + str(uuid.uuid4())
    RESULTS["tokens"].append(value)
    return value


try:
    session = token()
    seed = worker(NEW, session, "seed", "new-seed")
    old_read = worker(OLD, session, "read", "old-read-new")
    assert old_read["before"] == seed["stored_snapshot"]
    assert old_read["schema"] == seed["schema"]
    assigned = worker(OLD, session, "assign", "old-assign-new")
    new_read = worker(NEW, session, "read", "new-read-old-assignment")
    assert new_read["before"] == assigned["after_in_memory"]
    assert new_read["before"] == {
        "count": 13,
        "label": "assigned",
        "values": [3, 4],
        "secret": 17,
        "items": ["assigned"],
        "checksum": 38,
    }
    RESULTS["scenarios"].append({
        "name": "New pickle -> old read and frontend/backend assignments -> new read",
        "status": "passed",
        "schema": seed["schema"],
        "snapshot": new_read["before"],
    })
    frontend = worker(OLD, session, "frontend_inplace", "old-frontend-inplace")
    new_read = worker(NEW, session, "read", "new-read-old-frontend-inplace")
    assert frontend["after_in_memory"]["values"] == [3, 4, 8]
    assert new_read["before"]["values"] == [3, 4, 8]
    RESULTS["scenarios"].append({
        "name": "Old worker frontend mutable mutation on a new pickle persists",
        "status": "passed",
        "snapshot": new_read["before"],
    })
    session = token()
    seed = worker(NEW, session, "seed", "caveat-new-seed")
    mutated = worker(OLD, session, "backend_inplace", "caveat-old-backend-inplace")
    new_read = worker(NEW, session, "read", "caveat-new-read")
    assert mutated["after_in_memory"]["items"] == ["saved", "inplace"]
    assert not mutated["dirty_vars"]
    assert new_read["before"]["items"] == ["saved"]
    assert new_read["before"] == seed["stored_snapshot"]
    RESULTS["scenarios"].append({
        "name": "Advertised old-worker in-place mutable backend exception reproduced",
        "status": "expected limitation",
        "old_in_memory": mutated["after_in_memory"],
        "new_persisted": new_read["before"],
    })
    session = token()
    seed = worker(OLD, session, "seed", "old-seed")
    new_read = worker(NEW, session, "read", "new-read-old")
    assert new_read["before"] == seed["stored_snapshot"]
    assert new_read["schema"] == seed["schema"]
    assigned = worker(NEW, session, "assign", "new-assign-old")
    old_read = worker(OLD, session, "read", "old-read-new-assignment")
    assert old_read["before"] == assigned["after_in_memory"]
    RESULTS["scenarios"].append({
        "name": "Old pickle -> new read and assignments -> old read",
        "status": "passed",
        "schema": seed["schema"],
        "snapshot": old_read["before"],
    })
    RESULTS["status"] = "passed"
finally:
    cleaned = []
    for session in RESULTS["tokens"]:
        keys = list(STORE.scan_iter(match=session + "*"))
        assert all(
            key.decode().startswith(session + "_") or key.decode() == session
            for key in keys
        )
        if keys:
            STORE.delete(*keys)
            cleaned.extend(key.decode() for key in keys)
    RESULTS["cleaned_keys"] = cleaned
    (OUT / "results.json").write_text(json.dumps(RESULTS, indent=2))
