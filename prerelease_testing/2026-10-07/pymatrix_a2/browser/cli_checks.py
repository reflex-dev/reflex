"""Check CLI metadata, missing DB extra diagnostics and warning controls."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

assert "/envs/driver/" in sys.executable, sys.executable


def main():
    """Run CLI probes without starting servers or changing installed packages.

    Returns:
        Zero when supported interpreters report the expected CLI diagnostics.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--include-whole-fixture-controls", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    args.out.mkdir(parents=True, exist_ok=False)
    rows = []
    envnames = ["pymatrix-a2-311", "pymatrix-a2-313", "pymatrix-a2-314"]
    if args.include_whole_fixture_controls:
        envnames.extend(("stable", "alpha"))
    for envname in envnames:
        cwd = args.sb / "apps/pymatrix_a2" / ("cli-" + envname)
        shutil.copytree(
            source / "app", cwd, ignore=shutil.ignore_patterns("__pycache__")
        )
        env = dict(
            os.environ,
            REFLEX_TEST_ENV=envname,
            REFLEX_TELEMETRY_ENABLED="false",
            PYTHONWARNINGS="default",
            UV_CACHE_DIR=str(args.sb / "uv-cache"),
        )
        env.pop("PYTHONPATH", None)
        uv = [
            "uv",
            "--no-config",
            "run",
            "--no-project",
            "--python",
            str(args.sb / "envs" / envname / "bin/python"),
        ]
        metadata = json.loads(
            subprocess.check_output(
                [*uv, "python", str(source / "probe.py")], cwd=cwd, env=env, text=True
            )
        )
        probes = {
            "warning-import": [
                "python",
                "-c",
                "import pyapp.pyapp; print('APP_IMPORTED')",
            ]
        }
        if envname.startswith("pymatrix-"):
            probes.update(
                {
                    "version": ["reflex", "--version"],
                    "db-init-without-extra": ["reflex", "db", "init"],
                }
            )
        for label, command in probes.items():
            run = subprocess.run(
                [*uv, *command],
                cwd=cwd,
                env=env,
                text=True,
                capture_output=True,
                timeout=60,
            )
            output = run.stdout + run.stderr
            (args.out / f"{envname}-{label}.log").write_text(output)
            if label == "version":
                passed = run.returncode == 0 and "0.10.0a2" in run.stdout
            elif label == "db-init-without-extra":
                passed = (
                    run.returncode != 0
                    and "reflex[db]" in output
                    and "Traceback" not in output
                )
            else:
                passed = run.returncode == 0 and "APP_IMPORTED" in run.stdout
            rows.append(
                {
                    "env": envname,
                    "label": label,
                    "command": [*uv, *command],
                    "cwd": str(cwd),
                    "metadata": metadata,
                    "returncode": run.returncode,
                    "passed": passed,
                }
            )
    (args.out / "summary.json").write_text(json.dumps(rows, indent=2))
    print(
        json.dumps(
            [
                {key: row[key] for key in ("env", "label", "returncode", "passed")}
                for row in rows
            ],
            indent=2,
        )
    )
    return int(not all(row["passed"] for row in rows))


if __name__ == "__main__":
    sys.exit(main())
