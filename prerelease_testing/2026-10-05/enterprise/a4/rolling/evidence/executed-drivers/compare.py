"""Compare real Redis backend mutation persistence across published workers."""

import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import redis

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence"
UV = "/Users/masenf/.local/bin/uv"
ALPHA = "/private/tmp/reflex-enterprise-a4-20261005-root-venv"
STABLE = "/private/tmp/reflex-enterprise-a4-20261005-root-stable-venv"
STORE = redis.Redis(host="127.0.0.1", port=9141, db=5)
RESULT = {"database": 5, "cases": [], "owned_tokens": []}


def worker(prefix: str, token: str, action: str, label: str) -> dict:
    """Run one fresh published worker with its original source unchanged.

    Args:
        prefix: The exact published package environment.
        token: The owned Redis token for this case.
        action: The mutation or read to execute.
        label: The evidence file prefix.

    Returns:
        The saved worker result.
    """
    version = "0.9.12" if prefix == STABLE else "0.10.0a1"
    target = OUT / f"{label}.json"
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment.update({
        "REFLEX_OPLOCK_ENABLED": "false",
        "REFLEX_DIR": str(ROOT / "runtime"),
        "UV_CACHE_DIR": str(ROOT / "uv-cache"),
    })
    command = [
        UV, "--no-config", "run", "--no-project", "--python",
        prefix + "/bin/python", str(ROOT / "worker.py"), token, action,
        str(target), prefix, version,
    ]
    process = subprocess.run(
        command, cwd=ROOT, env=environment, capture_output=True, text=True, check=False
    )
    (OUT / f"{label}.stdout.log").write_text(process.stdout)
    (OUT / f"{label}.stderr.log").write_text(process.stderr)
    (OUT / f"{label}.invocation.json").write_text(json.dumps({
        "command": command, "returncode": process.returncode,
        "cwd": str(ROOT), "PYTHONPATH_unset": "PYTHONPATH" not in environment,
        "environment_overrides": {
            key: environment[key]
            for key in ("REFLEX_OPLOCK_ENABLED", "REFLEX_DIR", "UV_CACHE_DIR")
        },
    }, indent=2))
    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads(target.read_text())
    assert result["status"] == "passed"
    return result


def main() -> None:
    """Run three bounded cases and delete only this run's owned tokens."""
    assert "PYTHONPATH" not in os.environ
    assert sys.executable.startswith(STABLE + "/")
    assert str(Path(redis.__file__).resolve()).startswith(STABLE + "/")
    RESULT["orchestrator_executable"] = sys.executable
    RESULT["redis_package_origin"] = str(Path(redis.__file__).resolve())
    RESULT["redis_server_version"] = STORE.info("server")["redis_version"]
    RESULT["redis_persistence_configuration"] = {
        **STORE.config_get("save"), **STORE.config_get("appendonly")
    }
    assert RESULT["redis_persistence_configuration"] == {"save": "", "appendonly": "no"}
    RESULT["initial_dbsize"] = STORE.dbsize()
    assert RESULT["initial_dbsize"] == 0
    RESULT["source_sha256"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("rolling_app.py", "worker.py")
    }
    try:
        for label, seeder, mutator, reader in (
            ("stable-stable-stable", STABLE, STABLE, STABLE),
            ("alpha-stable-alpha", ALPHA, STABLE, ALPHA),
            ("alpha-alpha-alpha", ALPHA, ALPHA, ALPHA),
        ):
            token = "rolling-a4-" + str(uuid.uuid4())
            RESULT["owned_tokens"].append(token)
            seed = worker(seeder, token, "seed", label + "-seed")
            mutation = worker(mutator, token, "backend_inplace", label + "-mutate")
            read = worker(reader, token, "read", label + "-read")
            assert seed["stored_snapshot"]["items"] == ["saved"]
            assert mutation["before"]["items"] == ["saved"]
            assert mutation["after_in_memory"]["items"] == ["saved", "inplace"]
            case = {
                "name": label, "seed_version": seed["version"],
                "mutation_version": mutation["version"], "read_version": read["version"],
                "before": mutation["before"],
                "after_in_memory": mutation["after_in_memory"],
                "mutation_dirty_vars": mutation["dirty_vars"],
                "fresh_read": read["before"],
                "backend_append_persisted": read["before"]["items"] == ["saved", "inplace"],
                "seed_pickle_sha256": seed["pickle_sha256"],
                "post_mutation_pickle_sha256": mutation["pickle_sha256"],
            }
            RESULT["cases"].append(case)
        controls_pass = all(
            case["backend_append_persisted"]
            for case in RESULT["cases"] if case["name"] != "alpha-stable-alpha"
        )
        mixed_loses = not RESULT["cases"][1]["backend_append_persisted"]
        RESULT["controls_pass"] = controls_pass
        RESULT["mixed_version_append_lost"] = mixed_loses
        RESULT["new_rolling_regression_confirmed"] = controls_pass and mixed_loses
        assert controls_pass
        assert mixed_loses
        RESULT["execution_status"] = "completed"
    finally:
        removed = []
        for token in RESULT["owned_tokens"]:
            keys = list(STORE.scan_iter(match=token + "*"))
            assert all(key.decode().startswith(token + "_") or key.decode() == token for key in keys)
            if keys:
                STORE.delete(*keys)
                removed.extend(key.decode() for key in keys)
        RESULT["deleted_owned_keys"] = removed
        RESULT["final_dbsize"] = STORE.dbsize()
        (OUT / "results.json").write_text(json.dumps(RESULT, indent=2))
        STORE.close()


if __name__ == "__main__":
    main()
