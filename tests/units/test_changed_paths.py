"""Unit tests for scripts/changed_paths.py (the workflow path filter evaluator)."""

import pytest

from scripts import changed_paths

# The filters these tests pin are the ones lifted off the workflow triggers in
# .github/workflows; they have to keep selecting exactly what the triggers did.
MARKDOWN_IGNORE = ["**/*.md"]
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
    ("env", "value", "stdin", "expected"),
    [
        ("FILTER_PATHS_IGNORE", "**/*.md", "README.md\n", "false\n"),
        ("FILTER_PATHS_IGNORE", "**/*.md", "README.md\nreflex/app.py\n", "true\n"),
        ("FILTER_PATHS", "docs/**", "reflex/app.py\n", "false\n"),
        ("FILTER_PATHS", "docs/**\n\n", "docs/app/main.py\n", "true\n"),
    ],
)
def test_main_writes_the_verdict(monkeypatch, capsys, env, value, stdin, expected):
    monkeypatch.delenv("FILTER_PATHS", raising=False)
    monkeypatch.delenv("FILTER_PATHS_IGNORE", raising=False)
    monkeypatch.setenv(env, value)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(stdin))
    assert changed_paths.main() == 0
    assert capsys.readouterr().out == expected
