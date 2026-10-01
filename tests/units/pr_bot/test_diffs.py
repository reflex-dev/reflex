"""Unit tests for scripts/pr_bot/diffs.py (cutting diffs down for Claude)."""

from __future__ import annotations

import pytest

from scripts.pr_bot import diffs


def section(path: str, body: str = "+x\n") -> str:
    """Build one file's section of a unified diff.

    Args:
        path: The file.
        body: The hunk lines.

    Returns:
        The section.
    """
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{body}"


@pytest.mark.parametrize(
    ("path", "generated"),
    [
        ("uv.lock", True),
        ("docs/app/uv.lock", True),
        ("pyi_hashes.json", True),
        ("reflex/components/el.pyi", True),
        ("reflex/state.py", False),
        ("uv.lock.md", False),
    ],
)
def test_is_generated(path: str, generated: bool):
    assert diffs.is_generated(path) is generated


def test_split_keeps_each_file_whole():
    diff = section("a.py") + section("b.py", "+y\n+z\n")
    assert diffs.split(diff) == [
        ("a.py", section("a.py")),
        ("b.py", section("b.py", "+y\n+z\n")),
    ]


def test_split_uses_the_new_name_of_a_rename():
    diff = "diff --git a/old.py b/new.py\nsimilarity index 100%\n"
    assert diffs.split(diff)[0][0] == "new.py"


def test_budget_drops_generated_files_then_whatever_does_not_fit():
    big = section("big.py", "+" + "x" * 100 + "\n")
    diff = section("uv.lock") + section("a.py") + big + section("c.py")
    kept, left_out = diffs.budget(diff, len(section("a.py")) + len(section("c.py")))
    assert kept == section("a.py") + section("c.py")
    assert left_out == ["uv.lock", "big.py"]


def test_file_list_counts_what_it_leaves_out():
    files = [
        {"filename": f"f{n}.py", "status": "modified", "additions": n, "deletions": 0}
        for n in range(3)
    ]
    assert diffs.file_list(files, limit=2) == (
        "- f0.py (modified, +0 -0)\n- f1.py (modified, +1 -0)\n- ...and 1 more files"
    )
