"""Replay published type checkers against isolated release environments."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    """Record diagnostics and ensure deliberate mistakes are detected.

    Returns:
        Zero when only the two deliberate mistakes are diagnosed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", type=Path, required=True)
    parser.add_argument("--env", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert Path(sys.prefix) == args.sb / "envs/driver", sys.prefix
    work = args.sb / "apps/pymatrix-typing"
    work.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).parent / "source/handlers_0_5.py"
    negative_lines = {
        index
        for index, line in enumerate(source.read_text().splitlines(), 1)
        if line.startswith("Shop.") and "# expect-error" in line
    }
    assert len(negative_lines) == 2, negative_lines
    shutil.copy2(source, work / source.name)
    env = {**os.environ, "REFLEX_TELEMETRY_ENABLED": "false", "NO_COLOR": "1"}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    tools_python = args.sb / "envs/pymatrix-tools/bin/python"
    tool_prefix = [
        "uv",
        "--no-config",
        "run",
        "--no-project",
        "--python",
        str(tools_python),
    ]
    rows = []
    for name in args.env:
        target = args.sb / "envs" / name
        command = [
            "uv",
            "--no-config",
            "run",
            "--no-project",
            "--python",
            str(target / "bin/python"),
            "python",
            "-c",
            "import importlib.metadata as m,json,sys,reflex; "
            "assert sys.argv[1] in reflex.__file__,reflex.__file__; "
            "print(json.dumps({'python':sys.version,'prefix':sys.prefix,'reflex_path':reflex.__file__,"
            "'reflex':m.version('reflex'),'reflex_base':m.version('reflex-base')}))",
            str(target / "lib"),
        ]
        metadata = subprocess.run(
            command, cwd=work, env=env, text=True, capture_output=True, check=True
        )
        info = json.loads(metadata.stdout)
        version = ".".join(info["python"].split()[0].split(".")[:2])
        (args.out / f"{name}-metadata.json").write_text(json.dumps(info, indent=2))
        frozen = subprocess.run(
            [
                "uv",
                "--no-config",
                "pip",
                "freeze",
                "--python",
                str(target / "bin/python"),
            ],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        (args.out / f"{name}-freeze.txt").write_text(frozen.stdout)
        commands = {
            "ty": tool_prefix
            + [
                "ty",
                "check",
                "--python",
                str(target),
                "--python-version",
                version,
                "--project",
                str(work),
                "--output-format",
                "concise",
                "--color",
                "never",
                source.name,
            ],
            "pyright": tool_prefix
            + [
                "pyright",
                "--pythonpath",
                str(target / "bin/python"),
                "--pythonversion",
                version,
                "--outputjson",
                source.name,
            ],
        }
        for tool, argv in commands.items():
            completed = subprocess.run(
                argv,
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            label = f"{name}-{tool}"
            (args.out / f"{label}.stdout").write_text(completed.stdout)
            (args.out / f"{label}.stderr").write_text(completed.stderr)
            if tool == "ty":
                diagnostics = [
                    {
                        "line": int(match[1]),
                        "column": int(match[2]),
                        "rule": match[3],
                        "message": match[4],
                    }
                    for match in re.finditer(
                        r"handlers_0_5\.py:(\d+):(\d+): error\[([^]]+)\] (.*)",
                        completed.stdout,
                    )
                ]
            else:
                diagnostics = [
                    {
                        "line": diag["range"]["start"]["line"] + 1,
                        "column": diag["range"]["start"]["character"] + 1,
                        "rule": diag.get("rule"),
                        "message": diag["message"],
                    }
                    for diag in json.loads(completed.stdout)["generalDiagnostics"]
                ]
            observed = {diag["line"] for diag in diagnostics}
            row = {
                "label": label,
                "command": argv,
                "cwd": str(work),
                "returncode": completed.returncode,
                "metadata": info,
                "diagnostics": diagnostics,
                "negative_control_lines": sorted(negative_lines),
                "negative_controls_detected": negative_lines <= observed,
                "positive_case_error_lines": sorted(observed - negative_lines),
            }
            rows.append(row)
            print(
                label,
                row["positive_case_error_lines"],
                "negative_controls",
                row["negative_controls_detected"],
                flush=True,
            )
            (args.out / "results.json").write_text(json.dumps(rows, indent=2))
    tool_freeze = subprocess.run(
        ["uv", "--no-config", "pip", "freeze", "--python", str(tools_python)],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    (args.out / "tools-freeze.txt").write_text(tool_freeze.stdout)
    return int(
        any(
            row["returncode"] not in (0, 1)
            or not row["negative_controls_detected"]
            or row["positive_case_error_lines"]
            for row in rows
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
