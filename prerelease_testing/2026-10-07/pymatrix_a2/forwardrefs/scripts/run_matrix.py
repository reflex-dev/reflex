"""Run assigned published environments serially without mutating them."""

import json
import os
import subprocess
from pathlib import Path

SB = Path(os.environ["REFLEX_TEST_SB"])
ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENTS = [
    ("pymatrix-a2-311", "0.10.0a2", "3.11"),
    ("pymatrix-a2-313", "0.10.0a2", "3.13"),
    ("pymatrix-a2-314", "0.10.0a2", "3.14.7"),
    ("pymatrix-stable-311", "0.9.12", "3.11"),
    ("pymatrix-stable-3147", "0.9.12", "3.14.7"),
    ("pymatrix-a1-3147", "0.10.0a1", "3.14.7"),
]
(ROOT / "logs").mkdir(exist_ok=True)
(ROOT / "results").mkdir(exist_ok=True)
rows = []
failures = []
for name, version, python_version in ENVIRONMENTS:
    interpreter = SB / "envs" / name / "bin/python"
    env = {
        **os.environ,
        "REFLEX_EXPECT_ENV": str(SB / "envs" / name),
        "REFLEX_EXPECT_VERSION": version,
        "PYTHON_EXPECT_VERSION": python_version,
        "REFLEX_TELEMETRY_ENABLED": "false",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)
    freeze = subprocess.run(
        ["uv", "--no-config", "pip", "freeze", "--python", str(interpreter)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    (ROOT / f"logs/{name}-freeze.txt").write_text(freeze.stdout)
    cases = [
        "future_missing_list",
        "future_missing_optional",
        "future_valid",
        "bare_valid",
    ]
    if python_version.startswith("3.14"):
        cases += ["bare_missing_list", "bare_missing_optional"]
    for case in cases:
        label = f"{name}-{case}"
        output = ROOT / f"results/{label}.json"
        command = [
            "uv",
            "--no-config",
            "run",
            "--no-project",
            "--python",
            str(interpreter),
            "python",
            str(ROOT / "scripts/probe.py"),
            case,
            str(output),
        ]
        completed = subprocess.run(
            command, cwd=ROOT, env=env, capture_output=True, text=True, check=False
        )
        (ROOT / f"logs/{label}.stdout").write_text(completed.stdout)
        (ROOT / f"logs/{label}.stderr").write_text(completed.stderr)
        row = (
            json.loads(output.read_text())
            if output.exists()
            else {"driver_error": True}
        )
        row.update(environment=name, returncode=completed.returncode, command=command)
        rows.append(row)
        if completed.returncode or not row.get("fixture_expectation_pass"):
            failures.append(label)
        print(
            name,
            case,
            row.get("exception_type", "accepted"),
            row.get("exception_message", ""),
            flush=True,
        )
(ROOT / "results/matrix.json").write_text(json.dumps(rows, indent=2))
print("Unexpected fixture outcomes:", failures, flush=True)
raise SystemExit(1 if failures else 0)
