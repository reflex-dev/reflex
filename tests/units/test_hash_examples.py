"""Unit tests for scripts/hash_examples.py (the examples/playground content hash gate)."""

import re
import subprocess
from pathlib import Path

import pytest

from scripts import hash_examples


def _git(repo: Path, *args: str) -> None:
    """Run a git command in ``repo``.

    Args:
        repo: The repository working directory.
        args: The git arguments.
    """
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def playground(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a git repository holding a small playground and point the script at it.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The playground directory inside the repository.
    """
    repo = tmp_path / "repo"
    root = repo / "examples" / "playground"
    (root / "app").mkdir(parents=True)
    (root / "app" / "app.py").write_text("import reflex as rx\n")
    (root / "rxconfig.py").write_text("config = None\n")
    (root / ".gitignore").write_text("*.log\n")
    (repo / "outside.py").write_text("x = 1\n")
    _git(repo, "init")
    _git(repo, "add", ".")
    monkeypatch.setattr(hash_examples, "PLAYGROUND_DIR", root)
    return root


def test_content_hash_is_stable(playground: Path):
    first = hash_examples.content_hash(playground)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", first)
    assert hash_examples.content_hash(playground) == first


def test_content_hash_changes_with_file_content(playground: Path):
    before = hash_examples.content_hash(playground)
    (playground / "app" / "app.py").write_text("import reflex as rx  # changed\n")
    assert hash_examples.content_hash(playground) != before


def test_content_hash_changes_with_file_path(playground: Path):
    before = hash_examples.content_hash(playground)
    _git(playground, "mv", "app/app.py", "app/renamed.py")
    assert hash_examples.content_hash(playground) != before


def test_content_hash_includes_untracked_files(playground: Path):
    before = hash_examples.content_hash(playground)
    (playground / "app" / "new_page.py").write_text("")
    assert "app/new_page.py" in hash_examples.hashed_files(playground)
    assert hash_examples.content_hash(playground) != before


@pytest.mark.parametrize(
    "path",
    [
        ".web/app/routes/index.jsx",
        ".states/state.pkl",
        "__pycache__/rxconfig.cpython-312.pyc",
        "app/__pycache__/app.cpython-312.pyc",
        "app/stale.pyc",
        "reflex.db",
        "app/data.db",
        "uploaded_files/upload.txt",
        ".content-hash",
    ],
)
def test_content_hash_skips_build_output(playground: Path, path: str):
    before = hash_examples.content_hash(playground)
    file = playground / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("local output\n")
    assert hash_examples.content_hash(playground) == before
    # Build output stays out of the hash even when it is tracked.
    _git(playground, "add", "--force", path)
    assert hash_examples.content_hash(playground) == before


def test_content_hash_skips_gitignored_files(playground: Path):
    before = hash_examples.content_hash(playground)
    (playground / "reflex.log").write_text("local output\n")
    assert hash_examples.content_hash(playground) == before


def test_content_hash_ignores_files_outside_the_playground(playground: Path):
    before = hash_examples.content_hash(playground)
    (playground.parents[1] / "outside.py").write_text("x = 2\n")
    (playground.parent / "README.md").write_text("# examples\n")
    assert hash_examples.content_hash(playground) == before


def test_content_hash_skips_tracked_files_deleted_from_the_tree(playground: Path):
    before = hash_examples.content_hash(playground)
    (playground / "app" / "extra.py").write_text("y = 1\n")
    _git(playground, "add", "app/extra.py")
    (playground / "app" / "extra.py").unlink()
    assert hash_examples.content_hash(playground) == before


def test_hashed_files_lists_a_conflicted_path_once(playground: Path):
    commit = ["-c", "user.name=Tester", "-c", "user.email=t@example.com"]
    commit += ["-c", "commit.gpgsign=false", "commit", "-q", "-a", "-m"]
    _git(playground, *commit, "base")
    _git(playground, "checkout", "-q", "-b", "other")
    (playground / "rxconfig.py").write_text("config = 1\n")
    _git(playground, *commit, "other")
    _git(playground, "checkout", "-q", "-")
    (playground / "rxconfig.py").write_text("config = 2\n")
    _git(playground, *commit, "main")
    merge = subprocess.run(
        ["git", "merge", "other"], cwd=playground, capture_output=True
    )
    assert merge.returncode != 0, "the merge should stop on a conflict"
    assert hash_examples.hashed_files(playground).count("rxconfig.py") == 1


def test_content_hash_ignores_line_endings(playground: Path):
    before = hash_examples.content_hash(playground)
    (playground / "app" / "app.py").write_bytes(b"import reflex as rx\r\n")
    assert hash_examples.content_hash(playground) == before


def test_main_writes_the_hash_file(playground: Path):
    assert hash_examples.main([]) == 0
    hash_file = playground / hash_examples.HASH_FILE_NAME
    assert hash_file.read_text() == f"{hash_examples.content_hash(playground)}\n"


def test_check_passes_when_the_hash_is_current(
    playground: Path, capsys: pytest.CaptureFixture[str]
):
    hash_examples.main([])
    assert hash_examples.main(["--check"]) == 0
    assert capsys.readouterr().err == ""


def test_check_fails_when_the_playground_changed(
    playground: Path, capsys: pytest.CaptureFixture[str]
):
    hash_examples.main([])
    hash_file = playground / hash_examples.HASH_FILE_NAME
    committed = hash_file.read_text()
    (playground / "app" / "app.py").write_text("import reflex as rx  # changed\n")

    assert hash_examples.main(["--check"]) == 1
    assert capsys.readouterr().err == (
        "examples/playground changed: benchmark baselines reset by this PR "
        "(update with: uv run python scripts/hash_examples.py)\n"
    )
    # --check reports the stale hash without rewriting it.
    assert hash_file.read_text() == committed


def test_check_fails_without_a_hash_file(playground: Path):
    assert hash_examples.main(["--check"]) == 1
    assert not (playground / hash_examples.HASH_FILE_NAME).exists()
