"""Record final provenance, assertion counts, source hashes, and owned cleanup."""

import hashlib
import importlib
import json
import py_compile
import shutil
import socket
import sys
from pathlib import Path

import redis


def main() -> None:
    """Verify evidence and remove only this reproduction's Redis keys."""
    artifact = Path(sys.argv[1])
    evidence = artifact / "evidence"
    browser = json.loads((evidence / "browser/browser-results.json").read_text())
    locks = json.loads((evidence / "oplock-results.json").read_text())
    missing = json.loads((evidence / "missing-db-results.json").read_text())
    database = json.loads((evidence / "db-results.json").read_text())
    compatibility = json.loads((evidence / "compatibility/results.json").read_text())
    assert all(
        result["status"] == "passed"
        for result in (browser, locks, missing, database, compatibility)
    )
    before = json.loads((evidence / "provenance-before-db.json").read_text())
    after = json.loads((evidence / "provenance-with-db.json").read_text())
    old_versions = {
        value["name"]: value["version"] for value in before["distributions"]
    }
    new_versions = {value["name"]: value["version"] for value in after["distributions"]}
    assert all(new_versions[name] == value for name, value in old_versions.items())
    additions = {
        name: version
        for name, version in new_versions.items()
        if name not in old_versions
    }
    assert {name.lower() for name in additions} == {
        "sqlalchemy",
        "alembic",
        "mako",
        "markupsafe",
    }
    (evidence / "requirements-before-db.lock.txt").write_text(
        "\n".join(
            f"{name}=={version}" for name, version in sorted(old_versions.items())
        )
        + "\n"
    )
    origins = {}
    for name in (
        "reflex",
        "reflex.state",
        "reflex.istate.manager.redis",
        "reflex.istate.manager.token",
        "reflex.model",
        "reflex_base",
        "reflex_base.components.memo",
    ):
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        assert str(path).startswith("/private/tmp/reflex-alpha-core-state/venv/")
        origins[name] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    store = redis.Redis(host="localhost", port=9141, db=5)
    cleaned = []
    for token in browser["session_tokens"]:
        keys = list(store.scan_iter(match=token + "*"))
        assert all(
            key.decode().startswith(token + "_") or key.decode() == token
            for key in keys
        )
        if keys:
            store.delete(*keys)
            cleaned.extend(key.decode() for key in keys)
    ports = {}
    for port in (3111, 8111):
        with socket.socket() as connection:
            connection.settimeout(0.5)
            ports[port] = connection.connect_ex(("localhost", port)) != 0
            assert ports[port], port
    source_hashes = {}
    compiled_dir = Path("/private/tmp/reflex-alpha-core-state/redis/verified-source")
    compiled_dir.mkdir(exist_ok=True)
    for source in artifact.rglob("*.py"):
        py_compile.compile(
            str(source),
            cfile=str(compiled_dir / (source.parent.name + "-" + source.name + "c")),
            doraise=True,
        )
        source_hashes[str(source.relative_to(artifact))] = hashlib.sha256(
            source.read_bytes()
        ).hexdigest()
    shutil.copyfile(
        "/private/tmp/reflex-alpha-core-state/redis-server.log",
        evidence / "redis-server.log",
    )
    shutil.copyfile(
        "/private/tmp/reflex-alpha-core-state/oplock-checks.log",
        evidence / "oplock-checks.log",
    )
    shutil.copyfile(
        "/private/tmp/reflex-alpha-core-state/db-install.log",
        evidence / "db-install.log",
    )
    shutil.copyfile(
        "/private/tmp/reflex-alpha-core-state/db-checks.log", evidence / "db-checks.log"
    )
    for source in Path(
        "/private/tmp/reflex-alpha-core-state/plain-db-final/alembic/versions"
    ).glob("*.py"):
        shutil.copyfile(
            source, evidence / ("generated-migration-" + source.stem + ".txt")
        )
    summary = {
        "status": "passed",
        "browser_scenarios": len(browser["scenarios"]),
        "browser_value_assertions": sum(
            len(scenario["assertions"]) for scenario in browser["scenarios"]
        ),
        "browser_diagnostics": {
            name: len(browser[name])
            for name in ("console", "page_errors", "request_failures", "http_errors")
        },
        "oplock_scenarios": len(locks["scenarios"]),
        "rolling_deploy_scenarios": len(compatibility["scenarios"]),
        "missing_db_cli_commands": len(missing["commands"]),
        "db_cli_and_session_commands": len(database["commands"]),
        "versions_added_for_sqlalchemy_only": additions,
        "installed_module_origins": origins,
        "source_sha256": source_hashes,
        "cleanup": {
            "database": 5,
            "initial_dbsize": browser["initial_dbsize"],
            "deleted_browser_keys": cleaned,
            "final_dbsize": store.dbsize(),
            "ports_closed": ports,
            "root_owned_redis_service_preserved": store.ping(),
        },
    }
    assert summary["cleanup"]["final_dbsize"] == browser["initial_dbsize"] == 0
    (evidence / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps({
            name: value
            for name, value in summary.items()
            if name
            in (
                "status",
                "browser_scenarios",
                "browser_value_assertions",
                "oplock_scenarios",
                "rolling_deploy_scenarios",
            )
        })
    )


if __name__ == "__main__":
    main()
