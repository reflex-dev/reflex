"""Compare directional lockstep detection through two published release CLIs."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    """Create a disposable Git fixture and compare safe detection commands."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.scratch.mkdir(parents=True)
    root = Path(__file__).parent
    commands = []

    def run(command, env=None):
        """Run only the specified local fixture operation and retain outputs.

        Args:
            command: Exact subprocess arguments.
            env: Explicit environment overrides.

        Returns:
            Complete subprocess evidence.
        """
        environment = {**os.environ, **(env or {})}
        for key in (
            "PYTHONPATH",
            "GITHUB_TOKEN",
            "GH_TOKEN",
            "TWINE_PASSWORD",
            "PYPI_TOKEN",
        ):
            environment.pop(key, None)
        child = subprocess.run(
            command,
            cwd=args.scratch,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        result = {
            "command": command,
            "returncode": child.returncode,
            "stdout": child.stdout,
            "stderr": child.stderr,
        }
        commands.append(result)
        return result

    config = '[tool.reflex-release]\npackages-dir = "packages"\n[[tool.reflex-release.lockstep]]\nmembers = ["demo-core", "demo-app"]\npublish-last = ["demo-app"]\npin-exact = true\n'
    for package in ("demo-core", "demo-app"):
        directory = args.scratch / "packages" / package
        directory.mkdir(parents=True)
        (directory / "pyproject.toml").write_text(
            f'[project]\nname = "{package}"\nversion = "1.0.0"\n'
        )
    assert run(["git", "init", "-b", "main"])["returncode"] == 0
    assert (
        run(
            [
                "git",
                "-c",
                "user.name=Tooling Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "--allow-empty",
                "-m",
                "Local release baseline",
            ]
        )["returncode"]
        == 0
    )
    cases = []
    definitions = [
        ("together", "1.0.0", "1.0.0", False),
        ("only-last", "1.0.0", "1.0.0", False),
        ("early-independent", "1.1.0", "1.0.0", False),
        ("unmet-late", "1.1.0", "1.2.0", False),
        ("symmetric-mismatch", "1.1.0", "1.0.0", True),
    ]
    for name, core_version, app_version, symmetric in definitions:
        (args.scratch / "pyproject.toml").write_text(
            config
            if not symmetric
            else config.replace('publish-last = ["demo-app"]\npin-exact = true\n', "")
        )
        for package, version in (
            ("demo-core", core_version),
            ("demo-app", app_version),
        ):
            (args.scratch / "packages" / package / "CHANGELOG.md").write_text(
                f"## v{version} (2026-10-07)\n\nFixture.\n"
            )
        if name == "only-last":
            assert run(["git", "tag", "demo-core-v1.0.0"])["returncode"] == 0
        for env_name, version in (
            ("tooling-cli-release-old", "0.1.2a1"),
            ("tooling-cli-a2", "0.2.0a1"),
        ):
            environment = args.sb / "envs" / env_name
            output = args.scratch / f"{name}-{version}.out"
            output.touch()
            result = run(
                [
                    shutil.which("uv"),
                    "--no-config",
                    "run",
                    "--no-project",
                    "--python",
                    str(environment / "bin/python"),
                    "python",
                    str(root / "release_entry.py"),
                    "--root",
                    str(args.scratch),
                    "detect",
                    "--ref-name",
                    "main",
                ],
                {
                    "TOOLING_FIXTURE_ROOT": str(args.scratch),
                    "TOOLING_EXPECT_ENV": str(environment),
                    "GITHUB_OUTPUT": str(output),
                    "GITHUB_STEP_SUMMARY": str(args.scratch / f"{name}-{version}.md"),
                },
            )
            fields = dict(
                line.split("=", 1)
                for line in output.read_text().splitlines()
                if "=" in line
            )
            expected_success = name in ("together", "only-last") or (
                name == "early-independent" and version == "0.2.0a1"
            )
            cases.append(
                {
                    "case": name,
                    "version": version,
                    "expected_success": expected_success,
                    "pass": (result["returncode"] == 0) == expected_success,
                    "outputs": fields,
                    "result": result,
                }
            )
            args.output.write_text(
                json.dumps(
                    {
                        "cases": cases,
                        "commands": commands,
                        "scope": "local detection only; no remote configured, upload, push, or publication",
                    },
                    indent=2,
                )
                + "\n"
            )
            print(name, version, result["returncode"], cases[-1]["pass"], flush=True)
    raise SystemExit(int(any(not case["pass"] for case in cases)))


if __name__ == "__main__":
    main()
