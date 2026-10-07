"""Compare accepted, rejected and deprecated duration configurations."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

assert "/envs/driver/" in sys.executable, sys.executable


def main():
    """Run isolated duration subprocesses from a neutral app directory.

    Returns:
        One on unexpected probe outcomes, otherwise zero.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise RuntimeError("Refusing to replace prior evidence")
    args.out.mkdir(parents=True)
    source = Path(__file__).resolve().parent
    appdir = args.sb / "apps/statemgr_expiry/duration-probes"
    appdir.mkdir(parents=True, exist_ok=False)
    shutil.copy(source / "app/rxconfig.py", appdir / "rxconfig.py")
    rows = []
    cases = [
        (
            "new-ms",
            "alpha2",
            "debounce",
            {"REFLEX_STATE_MANAGER_DISK_DEBOUNCE": "250ms"},
            False,
            0.25,
        ),
        (
            "new-bare",
            "alpha2",
            "debounce",
            {"REFLEX_STATE_MANAGER_DISK_DEBOUNCE": "0.25"},
            False,
            0.25,
        ),
        (
            "new-zero",
            "alpha2",
            "debounce",
            {"REFLEX_STATE_MANAGER_DISK_DEBOUNCE": "0"},
            False,
            0.0,
        ),
        (
            "new-negative",
            "alpha2",
            "debounce",
            {"REFLEX_STATE_MANAGER_DISK_DEBOUNCE": "-5s"},
            False,
            -5.0,
        ),
        (
            "new-abc",
            "alpha2",
            "debounce",
            {"REFLEX_STATE_MANAGER_DISK_DEBOUNCE": "abc"},
            False,
            None,
        ),
        (
            "new-5x",
            "alpha2",
            "debounce",
            {"REFLEX_STATE_MANAGER_DISK_DEBOUNCE": "5x"},
            False,
            None,
        ),
        (
            "old-direct",
            "alpha2",
            "debounce",
            {"REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS": "0.25"},
            False,
            0.25,
        ),
        (
            "old-generated",
            "alpha2",
            "debounce",
            {"REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS": "0.25"},
            True,
            0.25,
        ),
        (
            "old-stable",
            "stable",
            "debounce",
            {"REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS": "0.25"},
            False,
            0.25,
        ),
        (
            "both-priority",
            "alpha2",
            "debounce",
            {
                "REFLEX_STATE_MANAGER_DISK_DEBOUNCE": "500ms",
                "REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS": "0.25",
            },
            False,
            0.5,
        ),
        (
            "cooldown-old-generated",
            "alpha2",
            "cooldown",
            {"REFLEX_AUTO_RELOAD_COOLDOWN_TIME_MS": "500"},
            True,
            0.5,
        ),
    ]
    for label, train, setting, values, generated, expected in cases:
        env = dict(
            os.environ,
            REFLEX_TEST_ENV=train,
            REFLEX_TELEMETRY_ENABLED="false",
            REFLEX_STATE_MANAGER_MODE="disk",
            REFLEX_STATES_WORKDIR=str(appdir / ".states"),
        )
        for key in (
            "REFLEX_STATE_MANAGER_DISK_DEBOUNCE",
            "REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS",
            "REFLEX_AUTO_RELOAD_COOLDOWN",
            "REFLEX_AUTO_RELOAD_COOLDOWN_TIME_MS",
        ):
            env.pop(key, None)
        env.update(values)
        command = [
            str(args.sb / "envs" / train / "bin/python"),
            str(source / "duration_probe.py"),
            "--setting",
            setting,
        ]
        if generated:
            command.append("--generated")
        completed = subprocess.run(
            command, cwd=appdir, env=env, text=True, capture_output=True, timeout=30
        )
        (args.out / f"{label}.log").write_text(completed.stdout + completed.stderr)
        line = next(
            (
                line
                for line in completed.stdout.splitlines()
                if line.startswith("QA_DURATION_RESULT=")
            ),
            None,
        )
        result = json.loads(line.split("=", 1)[1]) if line else {}
        passed = (
            (
                completed.returncode == 1
                and "Invalid duration value" in result.get("error", "")
            )
            if expected is None
            else (
                completed.returncode == 0
                and (
                    result.get("seconds") == [expected] * 3
                    or result.get("legacy_seconds") == expected
                )
            )
        )
        if passed and expected is not None and setting == "debounce":
            passed = result.get("manager_debounce_seconds") == expected
        rows.append({
            "label": label,
            "train": train,
            "environment": values,
            "command": command,
            "cwd": str(appdir),
            "returncode": completed.returncode,
            "expected_seconds": expected,
            "passed": passed,
            "result": result,
        })
        print(label, "PASS" if passed else "FAIL", result, flush=True)
    (args.out / "results.json").write_text(json.dumps(rows, indent=2))
    return int(any(not row["passed"] for row in rows))


if __name__ == "__main__":
    sys.exit(main())
