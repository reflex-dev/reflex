"""Unit tests for scripts/changed_paths.py (the workflow path filter evaluator)."""

import io
import json
from pathlib import Path

import pytest
import yaml

from scripts import changed_paths

WORKFLOW_DIR = Path(__file__).parents[2] / ".github" / "workflows"


def load_workflow(name: str) -> dict:
    """Parse one workflow file.

    Args:
        name: The workflow's file name.

    Returns:
        The parsed workflow.
    """
    return yaml.safe_load((WORKFLOW_DIR / name).read_text(encoding="utf-8"))


def changes_filter(name: str, step_id: str) -> list[str]:
    """Read the `paths` filter one step of a workflow's `changes` job evaluates.

    Args:
        name: The workflow's file name.
        step_id: The id of the changed_paths step.

    Returns:
        The filter's patterns, in order.
    """
    steps = load_workflow(name)["jobs"]["changes"]["steps"]
    step = next(step for step in steps if step.get("id") == step_id)
    return changed_paths.lines(step["with"]["paths"])


MARKDOWN_IGNORE = ["**/*.md"]
# The live filters, so the cases below pin what the workflows actually select.
DOCS_PATHS = changes_filter("docs_tests.yml", "filter")
DOCS_PAGES_PATHS = changes_filter("integration_tests.yml", "docs")


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["README.md"], False),
        (["docs/guide.md"], False),
        (["docs/a/b/c.md"], False),
        (["README.md", "docs/guide.md"], False),
        (["reflex/app.py"], True),
        (["README.md", "reflex/app.py"], True),
        # Only the .md suffix is ignored; a similarly named file still runs.
        (["docs/guide.mdx"], True),
        (["notes.md.py"], True),
    ],
)
def test_markdown_ignore(changed, expected):
    assert changed_paths.triggers(changed, paths_ignore=MARKDOWN_IGNORE) is expected


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["docs/app/main.py"], True),
        (["docs/README.md"], True),
        # The docs app imports the framework and the packages it documents.
        (["reflex/app.py"], True),
        (["packages/reflex-base/src/reflex_base/vars/base.py"], True),
        (["packages/reflex-frontend/src/state.js"], True),
        (["packages/reflex-components-core/src/reflex_components_core/x.py"], True),
        (["packages/reflex-components-internal/pyproject.toml"], True),
        (["packages/reflex-docgen/src/reflex_docgen/x.py"], True),
        (["packages/reflex-hosting-cli/src/reflex_cli/v2/deploy.py"], True),
        (["packages/reflex-build-sdk/src/reflex_build_sdk/x.py"], True),
        (["packages/hatch-reflex-pyi/src/x.py"], True),
        (["packages/reflex-site-shared/src/x.py"], True),
        (["packages/integrations-docs/pyproject.toml"], True),
        # The changelog pages render every package's changelog.
        (["CHANGELOG.md"], True),
        (["packages/reflex-otel/CHANGELOG.md"], True),
        (["pyproject.toml"], True),
        (["uv.lock"], True),
        ([".github/workflows/docs_tests.yml"], True),
        ([".github/actions/setup_build_env/action.yml"], True),
        # Packages the docs environment never installs.
        (["packages/reflex-otel/src/x.py"], False),
        (["packages/reflex-workflow/src/x.py"], False),
        (["packages/reflex-release/src/x.py"], False),
        # The frontend package's own tests are not shipped.
        (["packages/reflex-frontend/tests/state.test.js"], False),
        (["tests/units/test_app.py"], False),
        (["README.md"], False),
        ([".github/workflows/unit_tests.yml"], False),
        # A prefix of a filtered directory is not inside it.
        (["docsite/index.py"], False),
        (["reflexion/app.py"], False),
        (["tests/units/test_app.py", "docs/app/main.py"], True),
    ],
)
def test_docs_paths(changed, expected):
    assert changed_paths.triggers(changed, paths=DOCS_PATHS) is expected


def test_docs_push_filter_matches_the_changes_filter():
    """A main push runs the docs tests on exactly the paths a pull request does."""
    push = load_workflow("docs_tests.yml")[True]["push"]["paths"]
    assert push == DOCS_PATHS


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["docs/library/forms/form.md"], True),
        (["docs/app/reflex_docs/pages/docs/__init__.py"], True),
        (["packages/integrations-docs/src/integrations_docs/x.md"], True),
        (["CHANGELOG.md"], True),
        (["packages/reflex-base/CHANGELOG.md"], True),
        (["README.md"], False),
        (["packages/reflex-base/README.md"], False),
        (["reflex/app.py"], False),
    ],
)
def test_docs_pages_paths(changed, expected):
    """Markdown the docs site builds into pages runs the built-site checks."""
    assert changed_paths.triggers(changed, paths=DOCS_PAGES_PATHS) is expected


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
    assert changed_paths.triggers([], paths_ignore=MARKDOWN_IGNORE) is True
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
            {"paths_ignore": MARKDOWN_IGNORE},
            True,
        ),
        # Moving a file out of docs/ changes docs/ as much as editing it does.
        (("reflex/example.py", "docs/example.py"), {"paths": DOCS_PATHS}, True),
        # A rename that stays within ignored paths is still ignored.
        (("docs/new.md", "docs/old.md"), {"paths_ignore": MARKDOWN_IGNORE}, False),
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
