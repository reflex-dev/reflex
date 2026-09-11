"""Unit tests for scripts/check_outdated_deps.py (the outdated-dependency checker)."""

import sys

import pytest

# The script relies on ``tomllib`` (stdlib only on 3.11+); on 3.10 it falls back to the
# ``tomli`` backport. Skip the whole module when neither is available, so the tests still
# run on 3.10 whenever ``tomli`` happens to be installed.
if sys.version_info < (3, 11):
    pytest.importorskip(
        "tomli", reason="check_outdated_deps requires tomli on Python < 3.11"
    )

from scripts import check_outdated_deps


@pytest.mark.parametrize(
    ("pattern", "package", "expected"),
    [
        ("tailwindcss", "tailwindcss", True),
        # The bug the old grep-based filter had to be anchored against: a bare name must
        # not swallow the packages that merely share its prefix.
        ("tailwindcss", "tailwindcss-animated", False),
        ("tailwindcss", "@tailwindcss/postcss", False),
        ("plotly.js", "plotly.js", True),
        ("plotly.js", "plotly.js-locales", False),
        ("plotly.js", "react-plotly.js", False),
        ("ag-grid*", "ag-grid-community", True),
        ("ag-grid*", "ag-grid-enterprise", True),
        ("ag-grid*", "ag-grid-react", True),
        ("ag-grid*", "ag-charts-react", False),
        ("@chakra-ui/*", "@chakra-ui/react", True),
        ("@chakra-ui/*", "@chakra-ui-fork/react", False),
    ],
)
def test_matches(pattern: str, package: str, expected: bool):
    assert check_outdated_deps.matches(pattern, package) is expected


def test_partition_suppresses_only_held_packages():
    reportable, suppressed, stale = check_outdated_deps.partition(
        outdated=["tailwindcss", "tailwindcss-animated", "recharts"],
        installed=["tailwindcss", "tailwindcss-animated", "recharts"],
        held=["tailwindcss"],
    )
    assert reportable == ["tailwindcss-animated", "recharts"]
    assert suppressed == ["tailwindcss"]
    assert stale == []


def test_partition_flags_hold_already_at_latest():
    """A held package that is installed but not outdated no longer needs its hold."""
    reportable, suppressed, stale = check_outdated_deps.partition(
        outdated=["recharts"],
        installed=["recharts", "redis"],
        held=["redis"],
    )
    assert reportable == ["recharts"]
    assert suppressed == []
    assert stale == ["redis (already at latest: redis)"]


def test_partition_flags_hold_matching_nothing():
    _, _, stale = check_outdated_deps.partition(
        outdated=["recharts"], installed=["recharts"], held=["removed-package"]
    )
    assert stale == ["removed-package (matches no installed package)"]


def test_partition_prefix_hold_stays_live_while_any_member_is_outdated():
    """A lockstep family keeps its hold as long as one of its packages is behind."""
    _, suppressed, stale = check_outdated_deps.partition(
        outdated=["ag-grid-react"],
        installed=["ag-grid-community", "ag-grid-enterprise", "ag-grid-react"],
        held=["ag-grid*"],
    )
    assert suppressed == ["ag-grid-react"]
    assert stale == []


def test_parse_bun_outdated_handles_padded_columns():
    """Bun right-pads the package column and interleaves `|---|` rules between rows."""
    output = """bun outdated v1.4.0 (34cbb9a40)
|--------------------------------------------------|
| Package              | Current | Update | Latest |
|----------------------|---------|--------|--------|
| @tailwindcss/postcss | 4.3.0   | 4.3.0  | 4.3.3  |
|----------------------|---------|--------|--------|
| tailwindcss          | 4.3.0   | 4.3.0  | 4.3.3  |
|--------------------------------------------------|
"""
    assert check_outdated_deps.parse_bun_outdated(output) == [
        "@tailwindcss/postcss",
        "tailwindcss",
    ]


def test_parse_bun_outdated_strips_behavior_annotations():
    """Bun tags rows outside `dependencies` with `(dev)`, `(peer)` or `(optional)`.

    The docs app declares tailwindcss under devDependencies, so leaving the annotation on
    would stop it matching its `frontend_held` entry and fail the job it is meant to pass.
    """
    output = """bun outdated v1.4.0 (34cbb9a40)
|--------------------------------------------------------|
| Package                    | Current | Update | Latest |
|----------------------------|---------|--------|--------|
| @tailwindcss/postcss (dev) | 4.3.0   | 4.3.0  | 4.3.3  |
|----------------------------|---------|--------|--------|
| tailwindcss (dev)          | 4.3.0   | 4.3.0  | 4.3.3  |
|----------------------------|---------|--------|--------|
| react (peer)               | 19.2.0  | 19.2.0 | 19.2.8 |
|----------------------------|---------|--------|--------|
| clsx (optional)            | 2.1.0   | 2.1.0  | 2.1.1  |
|--------------------------------------------------------|
"""
    assert check_outdated_deps.parse_bun_outdated(output) == [
        "@tailwindcss/postcss",
        "tailwindcss",
        "react",
        "clsx",
    ]


def test_annotated_dev_row_is_suppressed_by_its_hold():
    """End to end for the regression: a `(dev)` row still matches its exact hold entry."""
    outdated = check_outdated_deps.parse_bun_outdated(
        "| Package           | Current | Update | Latest |\n"
        "| tailwindcss (dev) | 4.3.0   | 4.3.0  | 4.3.3  |\n"
    )
    reportable, suppressed, stale = check_outdated_deps.partition(
        outdated=outdated, installed=["tailwindcss"], held=["tailwindcss"]
    )
    assert reportable == []
    assert suppressed == ["tailwindcss"]
    assert stale == []


def test_bun_dependency_fields_cover_every_reported_section():
    """Bun reports peer and optional deps too, so the declared set must include them."""
    assert check_outdated_deps.BUN_DEPENDENCY_FIELDS == (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    )


def test_parse_bun_outdated_empty_when_nothing_outdated():
    assert (
        check_outdated_deps.parse_bun_outdated("bun outdated v1.4.0 (34cbb9a40)\n")
        == []
    )


def test_pinned_packages_are_suppressed_but_never_stale():
    """A package we do not drive stays suppressed even once it reaches latest.

    `pyright` and `ruff` are pinned by policy rather than blocked on anything, so being at
    their latest version does not mean the entry can be removed.
    """
    reportable, suppressed, stale = check_outdated_deps.partition(
        outdated=["ruff"],
        installed=["ruff", "pyright"],
        held=[],
        pinned=["ruff", "pyright"],
    )
    assert reportable == []
    assert suppressed == ["ruff"]
    assert stale == []


def test_load_config_reads_the_repo_config():
    """The real pyproject.toml must expose all four lists, since CI relies on them."""
    for kind in ("backend", "frontend"):
        held, pinned = check_outdated_deps._load_config(kind)
        assert isinstance(held, list)
        assert isinstance(pinned, list)
        assert all(isinstance(entry, str) for entry in [*held, *pinned])

    # The linters are pinned rather than held: they are at their latest most of the time,
    # and the hold is policy, not a blocker.
    assert "ruff" in check_outdated_deps._load_config("backend")[1]
    assert "ag-grid*" in check_outdated_deps._load_config("frontend")[1]
