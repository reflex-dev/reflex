"""Preserve exact graphs, validate unchanged sources, and stop owned Redis."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import redis

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence"
ORIGINAL = Path(
    "/Users/masenf/.codex/worktrees/48e6/reflex/prerelease_testing/2026-10-05/core_state/redis/compatibility"
)


def main() -> None:
    """Save graph and source checks before stopping this run's server."""
    source_checks = {}
    for name in ("rolling_app.py", "worker.py"):
        source_checks[name] = {
            "identical_to_retained_original": (ROOT / name).read_bytes()
            == (ORIGINAL / name).read_bytes(),
            "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest(),
        }
        assert source_checks[name]["identical_to_retained_original"]
    syntax_checks = {}
    for name in ("rolling_app.py", "worker.py", "compare.py", "finalize.py"):
        ast.parse((ROOT / name).read_text(), filename=name)
        syntax_checks[name] = "passed"
    provenance = {}
    for graph, label in (
        ("stable", "stable-stable-stable-seed"),
        ("alpha", "alpha-stable-alpha-seed"),
    ):
        result = json.loads((OUT / f"{label}.json").read_text())
        distributions = result["distributions"]
        assert len(distributions) == (91 if graph == "stable" else 104)
        (ROOT / f"requirements-{graph}-lock.txt").write_text(
            "".join(f"{item['name']}=={item['version']}\n" for item in distributions)
        )
        versions = {item["name"].lower(): item["version"] for item in distributions}
        assert versions["reflex-enterprise"] == "0.9.7a4"
        provenance[graph] = {
            "distributions": len(distributions),
            "python": result["python"],
            "executable": result["executable"],
            "origins": result["origins"],
            "reflex": versions["reflex"],
            "reflex-base": versions["reflex-base"],
            "reflex-enterprise": versions["reflex-enterprise"],
            "worker_asserted_no_direct_url_or_checkout_paths": True,
        }
    store = redis.Redis(host="127.0.0.1", port=9141, db=5)
    cleanup = {"dbsize_before_shutdown": store.dbsize()}
    assert cleanup["dbsize_before_shutdown"] == 0
    store.shutdown(nosave=True)
    store.close()
    cleanup["shutdown_without_save"] = True
    process = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-iTCP:9141", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    cleanup.update(
        {
            "final_port_audit_returncode": process.returncode,
            "final_port_audit_stdout": process.stdout,
            "final_port_audit_stderr": process.stderr,
        }
    )
    assert process.returncode == 1 and not process.stdout
    (OUT / "finalization.json").write_text(
        json.dumps(
            {
                "source_checks": source_checks,
                "syntax_checks": syntax_checks,
                "provenance": provenance,
                "cleanup": cleanup,
                "initial_port_audit": {
                    "command": ["/usr/sbin/lsof", "-nP", "-iTCP:9141", "-sTCP:LISTEN"],
                    "returncode": 1,
                    "stdout": "",
                    "recorded_from_prelaunch_tool_result": True,
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
