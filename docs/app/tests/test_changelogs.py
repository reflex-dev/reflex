"""Tests for package changelog discovery and normalization."""

from pathlib import Path, PurePosixPath

from reflex_docs.changelogs import (
    ENTERPRISE_PACKAGE,
    changelog_page_title,
    discover_changelogs,
    discover_repo_changelogs,
    find_distribution_changelog,
    normalize_changelog,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


class _FakeDist:
    """Minimal stand-in for importlib.metadata.Distribution."""

    def __init__(self, files, root):
        self._files = files
        self._root = root

    @property
    def files(self):
        return self._files

    def locate_file(self, file):
        return self._root / file


def test_discover_repo_changelogs(tmp_path):
    """Repo discovery picks up the root changelog and one per subpackage."""
    (tmp_path / "CHANGELOG.md").write_text("## v1.0.0\n")
    foo = tmp_path / "packages" / "foo"
    foo.mkdir(parents=True)
    (foo / "CHANGELOG.md").write_text("## v0.1.0\n")
    (tmp_path / "packages" / "bar").mkdir()

    changelogs = discover_repo_changelogs(tmp_path)

    assert changelogs == {
        "reflex": tmp_path / "CHANGELOG.md",
        "foo": foo / "CHANGELOG.md",
    }


def test_discover_repo_changelogs_real_repo():
    """The docs app reaches up to the actual repo root for changelogs."""
    changelogs = discover_repo_changelogs(REPO_ROOT)

    assert changelogs["reflex"] == REPO_ROOT / "CHANGELOG.md"
    assert "reflex-base" in changelogs
    assert all(path.is_file() for path in changelogs.values())


def test_discover_changelogs_orders_reflex_first(tmp_path, monkeypatch):
    """The reflex changelog sorts first; the rest are alphabetical."""
    (tmp_path / "CHANGELOG.md").write_text("## v1.0.0\n")
    for pkg in ("reflex-zeta", "reflex-alpha"):
        pkg_dir = tmp_path / "packages" / pkg
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "CHANGELOG.md").write_text("## v0.1.0\n")
    enterprise = tmp_path / "enterprise-changelog.md"
    enterprise.write_text("# Changelog\n")
    monkeypatch.setattr(
        "reflex_docs.changelogs.find_distribution_changelog",
        lambda package: enterprise,
    )

    changelogs = discover_changelogs(tmp_path)

    assert list(changelogs) == [
        "reflex",
        "reflex-alpha",
        ENTERPRISE_PACKAGE,
        "reflex-zeta",
    ]
    assert changelogs[ENTERPRISE_PACKAGE] == enterprise


def test_discover_changelogs_skips_missing_enterprise(tmp_path, monkeypatch):
    """No enterprise entry when the installed distribution has no changelog."""
    (tmp_path / "CHANGELOG.md").write_text("## v1.0.0\n")
    monkeypatch.setattr(
        "reflex_docs.changelogs.find_distribution_changelog",
        lambda package: None,
    )

    assert ENTERPRISE_PACKAGE not in discover_changelogs(tmp_path)


def test_find_distribution_changelog_not_installed():
    assert find_distribution_changelog("definitely-not-a-real-package-xyz") is None


def test_find_distribution_changelog_found(tmp_path, monkeypatch):
    """The changelog is located through the distribution's file records."""
    changelog = tmp_path / "reflex_enterprise" / "CHANGELOG.md"
    changelog.parent.mkdir()
    changelog.write_text("# Changelog\n")
    files = [
        PurePosixPath("reflex_enterprise/__init__.py"),
        PurePosixPath("reflex_enterprise/CHANGELOG.md"),
    ]
    monkeypatch.setattr(
        "reflex_docs.changelogs.distribution",
        lambda package: _FakeDist(files, tmp_path),
    )

    assert find_distribution_changelog(ENTERPRISE_PACKAGE) == changelog


def test_find_distribution_changelog_prefers_shallowest_record(tmp_path, monkeypatch):
    """Vendored changelogs deeper in the tree don't shadow the package one."""
    vendored = tmp_path / "reflex_enterprise" / "vendor" / "lib" / "CHANGELOG.md"
    vendored.parent.mkdir(parents=True)
    vendored.write_text("# Vendored\n")
    changelog = tmp_path / "reflex_enterprise" / "CHANGELOG.md"
    changelog.write_text("# Changelog\n")
    files = [
        PurePosixPath("reflex_enterprise/vendor/lib/CHANGELOG.md"),
        PurePosixPath("reflex_enterprise/CHANGELOG.md"),
    ]
    monkeypatch.setattr(
        "reflex_docs.changelogs.distribution",
        lambda package: _FakeDist(files, tmp_path),
    )

    assert find_distribution_changelog(ENTERPRISE_PACKAGE) == changelog


def test_find_distribution_changelog_no_file_records(monkeypatch):
    """Distributions without file records (files is None) are skipped."""
    monkeypatch.setattr(
        "reflex_docs.changelogs.distribution",
        lambda package: _FakeDist(None, Path("/nonexistent")),
    )

    assert find_distribution_changelog(ENTERPRISE_PACKAGE) is None


def test_find_distribution_changelog_stale_record(tmp_path, monkeypatch):
    """A recorded changelog that is missing on disk is ignored."""
    files = [PurePosixPath("reflex_enterprise/CHANGELOG.md")]
    monkeypatch.setattr(
        "reflex_docs.changelogs.distribution",
        lambda package: _FakeDist(files, tmp_path),
    )

    assert find_distribution_changelog(ENTERPRISE_PACKAGE) is None


def test_changelog_page_title():
    assert changelog_page_title("reflex") == "Reflex Changelog"
    assert changelog_page_title("reflex-base") == "reflex-base Changelog"


def test_normalize_changelog_towncrier():
    """Towncrier changelogs (no H1) get the canonical title prepended."""
    source = "## v0.9.4 (2026-06-03)\n\n### Features\n\n- A change.\n"

    assert normalize_changelog(source, "Reflex Changelog") == (
        "# Reflex Changelog\n\n## v0.9.4 (2026-06-03)\n\n### Features\n\n- A change.\n"
    )


def test_normalize_changelog_replaces_existing_h1():
    """Keep-a-Changelog files have their generic H1 replaced."""
    source = "# Changelog\n\n## [0.9.0] - 2026-06-09\n\n### Changed\n\n- A change.\n"

    assert normalize_changelog(source, "reflex-enterprise Changelog") == (
        "# reflex-enterprise Changelog\n\n"
        "## [0.9.0] - 2026-06-09\n\n### Changed\n\n- A change.\n"
    )
