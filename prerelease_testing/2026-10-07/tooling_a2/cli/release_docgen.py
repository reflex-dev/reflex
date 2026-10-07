"""Check published release workflow generation and docgen input boundaries."""

import argparse
import copy
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import yaml

from guard import install


def main() -> None:
    """Run only local workflow generation, dry detection, and document parsing."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert "/envs/tooling-cli-" in sys.prefix
    root = Path(__file__).parent
    args.scratch.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        TOOLING_FIXTURE_ROOT=str(args.scratch),
        TOOLING_EXPECT_ENV=sys.prefix,
        REFLEX_DIR=str(args.scratch / "runtime"),
        REFLEX_TELEMETRY_ENABLED="false",
        REFLEX_CHECK_LATEST_VERSION="false",
    )
    for key in (
        "PYTHONPATH",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "PYPI_TOKEN",
        "TWINE_PASSWORD",
        "REFLEX_ACCESS_TOKEN",
    ):
        os.environ.pop(key, None)
    install()
    import reflex_docgen
    import reflex_release
    from reflex_docgen.markdown import parse_document

    for module in (reflex_docgen, reflex_release):
        assert Path(module.__file__).is_relative_to(Path(sys.prefix)), module.__file__
    results = {
        "provenance": {
            "python": sys.executable,
            "versions": {
                name: importlib.metadata.version(name)
                for name in ("reflex", "reflex-base", "reflex-release", "reflex-docgen")
            },
            "paths": {m.__name__: m.__file__ for m in (reflex_docgen, reflex_release)},
        },
        "cases": [],
        "commands": [],
    }

    def command(argv, cwd, extra=None):
        """Retain both output streams for a local command.

        Args:
            argv: Exact command argument vector.
            cwd: Task-owned fixture directory.
            extra: Additional fixture environment values.

        Returns:
            Complete command evidence.
        """
        child = subprocess.run(
            argv,
            cwd=cwd,
            env={**os.environ, **(extra or {})},
            capture_output=True,
            text=True,
            timeout=45,
        )
        row = {
            "command": argv,
            "cwd": str(cwd),
            "returncode": child.returncode,
            "stdout": child.stdout,
            "stderr": child.stderr,
        }
        results["commands"].append(row)
        return row

    def cli(fixture, *arguments, extra=None):
        """Call the real published release parser and command dispatcher.

        Args:
            fixture: Temporary repository root.
            *arguments: Release CLI arguments.
            extra: Fixture output-file environment.

        Returns:
            Command evidence.
        """
        return command(
            [
                shutil.which("uv"),
                "--no-config",
                "run",
                "--no-project",
                "--python",
                sys.executable,
                "python",
                str(root / "release_entry.py"),
                "--root",
                str(fixture),
                *arguments,
            ],
            args.scratch,
            extra,
        )

    def record(name, function):
        """Record a case without discarding errors from earlier attempts.

        Args:
            name: Stable case name.
            function: Case callable returning evidence.
        """
        row = {"name": name}
        try:
            row.update(function())
            row["pass"] = True
        except Exception as error:
            row.update(
                {
                    "pass": False,
                    "error": repr(error),
                    "traceback": traceback.format_exc(),
                }
            )
        results["cases"].append(row)
        args.output.write_text(json.dumps(results, indent=2) + "\n")
        print(name, row["pass"], flush=True)

    for count in (19, 20, 24, 25):

        def generate(count=count):
            """Check dispatch inputs around GitHub's 25-input boundary.

            Args:
                count: Number of independently releasable packages.

            Returns:
                Parsed workflow counts and drift-check results.
            """
            fixture = args.scratch / f"packages-{count}"
            fixture.mkdir()
            (fixture / "pyproject.toml").write_text(
                '[tool.reflex-release]\npackages-dir = "packages"\n'
            )
            for index in range(count):
                package = fixture / "packages" / f"sample-{index:02}"
                package.mkdir(parents=True)
                (package / "pyproject.toml").write_text(
                    f'[project]\nname = "sample-{index:02}"\nversion = "1.0.0"\n'
                )
            assert cli(fixture, "init")["returncode"] == 0
            path = fixture / ".github/workflows/dispatch_release.yml"
            text = path.read_text()
            document = yaml.load(text, Loader=yaml.BaseLoader)
            inputs = document["on"]["workflow_dispatch"]["inputs"]
            booleans = [
                key for key, value in inputs.items() if value["type"] == "boolean"
            ]
            assert len(inputs) <= 25 and len(booleans) == (count if count <= 24 else 0)
            assert cli(fixture, "sync", "--check")["returncode"] == 0
            path.write_text(text + "\n# deliberate fixture drift\n")
            assert cli(fixture, "sync", "--check")["returncode"] != 0
            assert cli(fixture, "sync")["returncode"] == 0
            assert cli(fixture, "sync", "--check")["returncode"] == 0
            return {
                "package_count": count,
                "input_count": len(inputs),
                "boolean_count": len(booleans),
                "inputs": inputs,
                "drift_detected_and_repaired": True,
            }

        record(f"release-dispatch-{count}", generate)

    def lockstep():
        """Exercise publish-last generation and real CLI release detection.

        Returns:
            Parsed workflow gate and detection outputs.
        """
        fixture = args.scratch / "lockstep"
        fixture.mkdir()
        config = '[tool.reflex-release]\npackages-dir = "packages"\n[[tool.reflex-release.lockstep]]\nmembers = ["demo-core", "demo-app"]\npublish-last = ["demo-app"]\npin-exact = true\n'
        (fixture / "pyproject.toml").write_text(config)
        for name in ("demo-core", "demo-app"):
            package = fixture / "packages" / name
            package.mkdir(parents=True)
            dependencies = (
                '\ndependencies = ["demo-core>=1.0.0"]' if name == "demo-app" else ""
            )
            (package / "pyproject.toml").write_text(
                f'[project]\nname = "{name}"\nversion = "1.0.0"{dependencies}\n'
            )
            (package / "CHANGELOG.md").write_text(
                "## v1.0.0 (2026-10-07)\n\nFixture release.\n"
            )
        assert cli(fixture, "init")["returncode"] == 0
        workflow_path = fixture / ".github/workflows/release_from_changelog.yml"
        workflow = yaml.load(workflow_path.read_text(), Loader=yaml.BaseLoader)
        last = workflow["jobs"]["publish-last"]
        assert set(last["needs"]) == {"detect", "publish"}
        assert (
            "always()" in last["if"]
            and "needs.detect.result == 'success'" in last["if"]
        )
        assert (
            "needs.publish.result == 'success' || needs.publish.result == 'skipped'"
            in last["if"]
        )
        assert cli(fixture, "sync", "--check")["returncode"] == 0
        # Git exists only inside this disposable fixture; no remote is configured.
        assert command(["git", "init", "-b", "main"], fixture)["returncode"] == 0
        assert (
            command(
                [
                    "git",
                    "-c",
                    "user.name=Tooling Fixture",
                    "-c",
                    "user.email=fixture@example.test",
                    "commit",
                    "--allow-empty",
                    "-m",
                    "Local fixture only",
                ],
                fixture,
            )["returncode"]
            == 0
        )

        def detect(label):
            """Read GitHub output files generated by a real detection command.

            Args:
                label: Unique retained output name.

            Returns:
                Exit status and decoded output lines.
            """
            output = fixture / f"{label}.out"
            output.touch()
            row = cli(
                fixture,
                "detect",
                "--ref-name",
                "main",
                extra={
                    "GITHUB_OUTPUT": str(output),
                    "GITHUB_STEP_SUMMARY": str(fixture / f"{label}.md"),
                },
            )
            fields = dict(
                line.split("=", 1)
                for line in output.read_text().splitlines()
                if "=" in line
            )
            return {
                "returncode": row["returncode"],
                "outputs": fields,
                "stderr": row["stderr"],
            }

        together = detect("together")
        assert (
            together["returncode"] == 0
            and together["outputs"]["any"] == "true"
            and together["outputs"]["any_last"] == "true"
        ), together
        assert command(["git", "tag", "demo-core-v1.0.0"], fixture)["returncode"] == 0
        only_last = detect("only-last")
        assert (
            only_last["returncode"] == 0
            and only_last["outputs"]["any"] == "false"
            and only_last["outputs"]["any_last"] == "true"
        ), only_last
        assert (
            json.loads(only_last["outputs"]["last_packages"])[0]["package"]
            == "demo-app"
        )
        assert (
            cli(fixture, "pin-lockstep", "--package", "demo-app", "--version", "1.0.0")[
                "returncode"
            ]
            == 0
        )
        pin = (fixture / "packages/demo-app/pyproject.toml").read_text()
        assert "demo-core==1.0.0" in pin.replace(" ", ""), pin
        (fixture / "packages/demo-core/CHANGELOG.md").write_text(
            "## v1.1.0 (2026-10-07)\n\nMismatched release.\n"
        )
        early_independent = detect("early-independent")
        assert early_independent["returncode"] == 0, early_independent
        (fixture / "packages/demo-app/CHANGELOG.md").write_text(
            "## v1.2.0 (2026-10-07)\n\nUnmet late dependency.\n"
        )
        mismatched = detect("mismatched-late")
        assert (
            mismatched["returncode"] != 0 and "lockstep" in mismatched["stderr"].lower()
        ), mismatched
        (fixture / "pyproject.toml").write_text(
            config.replace(
                'publish-last = ["demo-app"]',
                'publish-last = ["demo-core", "demo-app"]',
            )
        )
        invalid = cli(fixture, "sync", "--check")
        assert invalid["returncode"] != 0 and "publish-last" in invalid["stderr"], (
            invalid
        )
        return {
            "workflow_publish_last": last,
            "together": together,
            "only_last": only_last,
            "early_independent": early_independent,
            "mismatched_late": mismatched,
            "pin_exact": pin,
            "invalid_all_last_exit": invalid["returncode"],
            "github_actions_execution": "not run; generated condition and CLI matrices checked",
        }

    record("release-lockstep-publish-last", lockstep)

    for prefix, newline in (
        ("", "\n"),
        ("\ufeff", "\n"),
        (" \n\t", "\r\n"),
        ("\ufeff \r\n", "\r\n"),
        ("\ufeff\t \r\n\r\n", "\r\n"),
    ):

        def document(prefix=prefix, newline=newline):
            """Parse ordinary and editor-produced metadata prefixes.

            Args:
                prefix: BOM and leading whitespace.
                newline: LF or CRLF separators.

            Returns:
                Complete parsed document representation.
            """
            source = prefix + newline.join(
                (
                    "---",
                    'title: "Café metadata"',
                    "description: SEO description",
                    "image: /social.png",
                    "---",
                    "# Visible heading",
                    "",
                    "Body with --- inline.",
                    "",
                    "```yaml",
                    "title: Keep code content",
                    "```",
                )
            )
            parsed = parse_document(source)
            assert (
                parsed.frontmatter.title == "Café metadata"
                and parsed.frontmatter.description == "SEO description"
            )
            blocks = repr(parsed.blocks)
            assert (
                "Café metadata" not in blocks
                and "Visible heading" in blocks
                and "Keep code content" in blocks
            )
            return {
                "prefix": repr(prefix),
                "newline": repr(newline),
                "source": source,
                "parsed": repr(parsed),
            }

        record("docgen-" + repr(prefix) + "-" + repr(newline), document)

    def body_control():
        """Keep YAML-looking body text when no leading metadata block exists.

        Returns:
            Parsed negative-control document.
        """
        source = "# Body title\n\n---\ntitle: Body field\n---\n"
        document = parse_document(source)
        assert document.frontmatter is None
        assert "Body field" in repr(document.blocks)
        return {"source": source, "parsed": repr(document)}

    record("docgen-body-not-frontmatter", body_control)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    raise SystemExit(int(any(not case["pass"] for case in results["cases"])))


if __name__ == "__main__":
    main()
