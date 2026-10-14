"""Unit tests for scripts/changed_paths.py (the workflow path filter evaluator).

Also covers .github/actions/changed_paths, the action that feeds it each event's
changed files.
"""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts import changed_paths

REPO_ROOT = Path(__file__).parents[2]
ACTION = REPO_ROOT / ".github" / "actions" / "changed_paths" / "action.yml"

# Fixtures copied from the filters the workflows' `changes` jobs carry (unit_tests
# and docs_tests). They pin the matching semantics; test_workflow_gates.py checks
# that the live filters compile.
DOCS_ONLY_IGNORE = [
    "**/*.md",
    "docs/**",
    "docker-example/**",
    ".github/**",
    ".devcontainer/**",
    ".claude/**",
    "!.github/workflows/**",
    "!.github/actions/**",
    "!.github/rulesets/**",
]
DOCS_PATHS = [
    "docs/**",
    "packages/reflex-components-core/src/reflex_components_core/core/upload.py",
    "packages/reflex-site-shared/**",
    "packages/integrations-docs/**",
    ".github/workflows/docs_tests.yml",
]


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["README.md"], False),
        (["docs/guide.md"], False),
        (["docs/a/b/c.md"], False),
        (["README.md", "docs/guide.md"], False),
        (["packages/reflex-base/news/+fix.bugfix.md"], False),
        (["docs/app/reflex_docs/whitelist.py"], False),
        (["docker-example/production/Dockerfile"], False),
        (["docs/app/app.py", ".github/ISSUE_TEMPLATE/bug_report.yml"], False),
        ([".github/dependabot.yml"], False),
        ([".devcontainer/devcontainer.json"], False),
        ([".claude/settings.json"], False),
        (["reflex/app.py"], True),
        (["README.md", "reflex/app.py"], True),
        (["docs/app/app.py", "pyproject.toml"], True),
        # A negation puts the files the unit tests cover back under test.
        ([".github/workflows/integration_tests.yml"], True),
        ([".github/actions/changed_paths/action.yml"], True),
        ([".github/actions/ci_gate/action.yml"], True),
        ([".github/rulesets/main-required-checks.json"], True),
        (["docs/guide.md", ".github/workflows/unit_tests.yml"], True),
        # Only the .md suffix is ignored; a similarly named file still runs.
        (["reflex/guide.mdx"], True),
        (["notes.md.py"], True),
        # The directories are anchored at the repo root.
        (["packages/reflex-base/docs/api.py"], True),
        (["tests/.github/fixture.yml"], True),
        (["docs.py"], True),
    ],
)
def test_docs_only_ignore(changed, expected):
    assert changed_paths.triggers(changed, paths_ignore=DOCS_ONLY_IGNORE) is expected


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["docs/app/main.py"], True),
        (["docs/README.md"], True),
        (["packages/reflex-site-shared/src/x.py"], True),
        (["packages/integrations-docs/pyproject.toml"], True),
        (
            [
                "packages/reflex-components-core/src/reflex_components_core/core/upload.py"
            ],
            True,
        ),
        ([".github/workflows/docs_tests.yml"], True),
        (["reflex/app.py"], False),
        ([".github/workflows/unit_tests.yml"], False),
        # A prefix of a filtered directory is not inside it.
        (["docsite/index.py"], False),
        (
            ["packages/reflex-components-core/src/reflex_components_core/core/x.py"],
            False,
        ),
        (["reflex/app.py", "docs/app/main.py"], True),
    ],
)
def test_docs_paths(changed, expected):
    assert changed_paths.triggers(changed, paths=DOCS_PATHS) is expected


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("*.md", "README.md", True),
        # A single star never crosses a path separator.
        ("*.md", "docs/README.md", False),
        ("docs/*.md", "docs/README.md", True),
        ("docs/*.md", "docs/a/README.md", False),
        ("docs/**", "docs/a/b.py", True),
        ("**", "anything/at/all.py", True),
        ("**/*.md", "README.md", True),
        ("a/**/b.py", "a/b.py", True),
        ("a/**/b.py", "a/x/y/b.py", True),
        # Only a `**/` that starts a segment spans whole directories; embedded,
        # it is `**` followed by a literal slash.
        ("foo**/bar", "foobar", False),
        ("foo**/bar", "foo/bar", True),
        ("foo**/bar", "foox/y/bar", True),
        # Escapes and ranges.
        (r"reflex/\*.py", "reflex/*.py", True),
        (r"reflex/\*.py", "reflex/app.py", False),
        ("v[0-9]/x.py", "v3/x.py", True),
        ("v[0-9]/x.py", "va/x.py", False),
        # Anchored at both ends.
        ("reflex/app.py", "docs/reflex/app.py", False),
        ("reflex/app.py", "reflex/app.pyi", False),
    ],
)
def test_translate(pattern, path, expected):
    assert bool(changed_paths.translate(pattern).fullmatch(path)) is expected


def test_negation_subtracts_from_earlier_patterns():
    patterns = ["docs/**", "!docs/**/*.md"]
    assert changed_paths.triggers(["docs/app/main.py"], paths=patterns) is True
    assert changed_paths.triggers(["docs/guide.md"], paths=patterns) is False
    # A later positive pattern wins again for the paths it matches.
    assert (
        changed_paths.triggers(["docs/guide.md"], paths=[*patterns, "docs/guide.md"])
        is True
    )


def test_unsupported_character_range_is_rejected():
    with pytest.raises(ValueError, match="unsupported character range"):
        changed_paths.translate("v[0-9/x.py")
    with pytest.raises(ValueError, match="unsupported character range"):
        changed_paths.translate("v[a.b]/x.py")


def test_empty_change_set_runs_the_jobs():
    assert changed_paths.triggers([], paths_ignore=DOCS_ONLY_IGNORE) is True
    assert changed_paths.triggers([], paths=DOCS_PATHS) is True


def entry(filename, previous_filename=None):
    """Return one changed file as the action feeds it to the script."""
    return json.dumps({"filename": filename, "previous_filename": previous_filename})


def test_changed_files_counts_both_names_of_a_rename():
    assert changed_paths.changed_files([
        entry("docs/example.md", "scripts/example.py"),
        entry("README.md"),
    ]) == ["docs/example.md", "scripts/example.py", "README.md"]


@pytest.mark.parametrize(
    ("renamed", "filter_kwargs", "expected"),
    [
        # A code file renamed to Markdown still removes code: the jobs must run.
        (
            ("docs/example.md", "scripts/example.py"),
            {"paths_ignore": DOCS_ONLY_IGNORE},
            True,
        ),
        # Moving a file out of docs/ changes docs/ as much as editing it does.
        (("reflex/example.py", "docs/example.py"), {"paths": DOCS_PATHS}, True),
        # Moving code into docs/ removes it from where it was: the jobs must run.
        (
            ("docs/app/example.py", "reflex/example.py"),
            {"paths_ignore": DOCS_ONLY_IGNORE},
            True,
        ),
        # A rename that stays within ignored paths is still ignored.
        (("docs/new.md", "docs/old.md"), {"paths_ignore": DOCS_ONLY_IGNORE}, False),
    ],
)
def test_renames_are_filtered_on_both_names(renamed, filter_kwargs, expected):
    changed = changed_paths.changed_files([entry(*renamed)])
    assert changed_paths.triggers(changed, **filter_kwargs) is expected


def test_changed_files_rejects_malformed_input():
    # A malformed entry fails the `changes` job, and so the gate, rather than
    # quietly skipping everything.
    with pytest.raises(json.JSONDecodeError):
        changed_paths.changed_files(["docs/example.md"])


def test_lines_drops_blanks_and_strips():
    assert changed_paths.lines(" a.py \n\n\tb.py\n \n") == ["a.py", "b.py"]
    assert changed_paths.lines("") == []


def test_main_requires_exactly_one_filter(monkeypatch, capsys):
    monkeypatch.delenv("FILTER_PATHS", raising=False)
    monkeypatch.delenv("FILTER_PATHS_IGNORE", raising=False)
    assert changed_paths.main() == 2
    monkeypatch.setenv("FILTER_PATHS", "docs/**")
    monkeypatch.setenv("FILTER_PATHS_IGNORE", "**/*.md")
    assert changed_paths.main() == 2
    assert "exactly one" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("env", "value", "files", "expected"),
    [
        ("FILTER_PATHS_IGNORE", "**/*.md", [entry("README.md")], "false\n"),
        (
            "FILTER_PATHS_IGNORE",
            "**/*.md",
            [entry("README.md"), entry("reflex/app.py")],
            "true\n",
        ),
        (
            "FILTER_PATHS_IGNORE",
            "**/*.md",
            [entry("docs/example.md", "scripts/example.py")],
            "true\n",
        ),
        ("FILTER_PATHS", "docs/**", [entry("reflex/app.py")], "false\n"),
        ("FILTER_PATHS", "docs/**\n\n", [entry("docs/app/main.py")], "true\n"),
    ],
)
def test_main_writes_the_verdict(monkeypatch, capsys, env, value, files, expected):
    monkeypatch.delenv("FILTER_PATHS", raising=False)
    monkeypatch.delenv("FILTER_PATHS_IGNORE", raising=False)
    monkeypatch.setenv(env, value)
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{f}\n" for f in files)))
    assert changed_paths.main() == 0
    assert capsys.readouterr().out == expected


def run_action(tmp_path, gh_lines=(), gh_fails=False, **event):
    """Run the changed_paths action's script against a stubbed `gh`.

    Args:
        tmp_path: A scratch directory for the stub and the step's output file.
        gh_lines: The lines the stub prints, as `gh --jq` would emit them.
        gh_fails: Whether the stub exits with an error instead.
        **event: The step's event environment (EVENT_NAME, PR_NUMBER, BEFORE,
            AFTER).

    Returns:
        The `changed` output the step wrote, and the arguments of each gh call.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in {
        "gh": '[ -n "$GH_LOG" ] && echo "$*" >> "$GH_LOG"\n'
        '[ -z "$GH_FAIL" ] || exit 1\n'
        'printf "%s" "$GH_OUTPUT"',
        "python3": f'exec "{sys.executable}" "$@"',
    }.items():
        (bin_dir / name).write_text(f"#!/bin/sh\n{body}\n")
        (bin_dir / name).chmod(0o755)
    log, output = tmp_path / "gh.log", tmp_path / "output"
    script = yaml.safe_load(ACTION.read_text(encoding="utf-8"))["runs"]["steps"][0][
        "run"
    ]
    subprocess.run(
        ["bash", "-c", script],
        check=True,
        capture_output=True,
        env={
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GITHUB_WORKSPACE": str(REPO_ROOT),
            "GITHUB_OUTPUT": str(output),
            "GH_LOG": str(log),
            "GH_OUTPUT": "".join(f"{line}\n" for line in gh_lines),
            "GH_FAIL": "1" if gh_fails else "",
            "REPO": "owner/repo",
            "FILTER_PATHS_IGNORE": "**/*.md\ndocs/**",
            **event,
        },
    )
    changed = output.read_text().strip().removeprefix("changed=")
    calls = log.read_text().splitlines() if log.exists() else []
    return changed, calls


def files(*names):
    """Format changed files the way the action's `gh --jq` filter emits them.

    Args:
        *names: Changed paths, or (filename, previous_filename) pairs for renames.

    Returns:
        One JSON object per line.
    """
    return [entry(*name) if isinstance(name, tuple) else entry(name) for name in names]


PUSH = {"EVENT_NAME": "push", "BEFORE": "a1b2", "AFTER": "c3d4"}

windows_has_no_bash = pytest.mark.skipif(
    sys.platform == "win32", reason="the action runs under bash on Linux runners"
)


@windows_has_no_bash
@pytest.mark.parametrize(
    ("event", "gh_lines", "gh_fails", "expected", "endpoint"),
    [
        (
            {"EVENT_NAME": "pull_request", "PR_NUMBER": "5"},
            files("docs/guide.md", "README.md"),
            False,
            "false",
            "repos/owner/repo/pulls/5/files",
        ),
        (
            {"EVENT_NAME": "pull_request", "PR_NUMBER": "5"},
            files("README.md", "reflex/app.py"),
            False,
            "true",
            "repos/owner/repo/pulls/5/files",
        ),
        (PUSH, files("docs/app/app.py"), False, "false", "compare/a1b2...c3d4"),
        (
            PUSH,
            files(("docs/app/app.py", "reflex/app.py")),
            False,
            "true",
            "compare/a1b2...c3d4",
        ),
        # The compare API stops at 300 files, so the rest may be code.
        (
            PUSH,
            files(*(f"docs/{n}.md" for n in range(300))),
            False,
            "true",
            "compare/a1b2...c3d4",
        ),
        # A force push can leave the previous commit unreachable.
        (PUSH, (), True, "true", "compare/a1b2...c3d4"),
        # A push that creates a branch has nothing to compare against.
        ({**PUSH, "BEFORE": "0" * 40}, (), False, "true", None),
        ({"EVENT_NAME": "workflow_dispatch"}, (), False, "true", None),
    ],
    ids=[
        "pr-docs-only",
        "pr-code",
        "push-docs-only",
        "push-rename-out-of-code",
        "push-truncated-compare",
        "push-compare-fails",
        "push-new-branch",
        "workflow-dispatch",
    ],
)
def test_action_evaluates_each_event(
    tmp_path, event, gh_lines, gh_fails, expected, endpoint
):
    changed, calls = run_action(tmp_path, gh_lines, gh_fails, **event)
    assert changed == expected
    if endpoint is None:
        assert calls == []
    else:
        assert len(calls) == 1
        assert endpoint in calls[0]


@windows_has_no_bash
def test_action_fails_when_the_pull_request_files_are_unreadable(tmp_path):
    # Pull requests gate merges, so an API failure fails the gate rather than
    # guessing either way.
    with pytest.raises(subprocess.CalledProcessError):
        run_action(tmp_path, gh_fails=True, EVENT_NAME="pull_request", PR_NUMBER="5")
