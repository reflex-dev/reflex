"""Tests for reflex_bench.fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from reflex_bench import fixtures
from reflex_bench.drivers.editor import Edit, find_target

from scripts import hash_examples
from tests.units.reflex_bench.factories import make_context

REPO = Path(__file__).parents[4]


def _git_init(path: Path) -> None:
    """Make a directory a git work tree, as scripts/hash_examples.py needs.

    Args:
        path: The directory.
    """
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def test_playground_dir_is_the_checkouts_playground():
    assert fixtures.playground_dir() == REPO / "examples" / "playground"


def test_playground_dir_outside_a_checkout_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # An installed wheel: the package sits in site-packages, far from any checkout.
    fake = tmp_path / "lib" / "python3.14" / "site-packages" / "reflex_bench"
    monkeypatch.setattr(fixtures, "__file__", str(fake / "fixtures" / "__init__.py"))
    with pytest.raises(RuntimeError, match="examples/playground"):
        fixtures.playground_dir()


def test_fixture_hash_is_the_fixtures_content_hash():
    content_hash = (REPO / "examples" / "playground" / ".content-hash").read_text()
    assert fixtures.fixture_hash("playground") == content_hash.strip()
    assert fixtures.fixture_hash("playground").startswith("sha256:")
    with pytest.raises(RuntimeError, match="examples/missing"):
        fixtures.fixture_hash("missing")


def test_fixtures_offer_the_playground_only():
    assert dict(fixtures.FIXTURES) == {"playground": fixtures.stage_playground}


def _fake_playground(root: Path) -> Path:
    """Build a small playground carrying the output a local run leaves behind.

    Args:
        root: Where to create it.

    Returns:
        The playground directory.
    """
    source = root / "playground"
    (source / "app" / "__pycache__").mkdir(parents=True)
    (source / "app" / "app.py").write_text("import reflex as rx\n")
    (source / "app" / "__pycache__" / "app.cpython-314.pyc").write_bytes(b"\0")
    (source / "rxconfig.py").write_text("config = None\n")
    for output in (".venv", ".web", ".states", "reflex.lock"):
        (source / output).mkdir()
        (source / output / "junk").write_text("x")
    return source


def test_stage_skips_build_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = _fake_playground(tmp_path)
    monkeypatch.setattr(fixtures, "playground_dir", lambda: source)
    dst = tmp_path / "staged"
    fixtures.stage_playground(dst)
    staged = sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*"))
    assert staged == ["app", "app/app.py", "rxconfig.py"]


def test_stage_replaces_sources_and_keeps_the_staged_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = _fake_playground(tmp_path)
    monkeypatch.setattr(fixtures, "playground_dir", lambda: source)
    dst = tmp_path / "staged"
    fixtures.stage_playground(dst)
    # A stale source file, an edit that was never restored and the staged
    # app's own build output, as an interrupted run leaves them.
    (dst / "stale.py").write_text("x = 1\n")
    (dst / "app" / "app.py").write_text("edited\n")
    (dst / ".web").mkdir()
    (dst / ".web" / "node_modules").write_text("installed")
    (dst / "reflex.lock").mkdir()
    (dst / "reflex.lock" / "bun.lock").write_text("locked")
    fixtures.stage_playground(dst)
    assert not (dst / "stale.py").exists()
    assert (dst / "app" / "app.py").read_text() == "import reflex as rx\n"
    assert (dst / ".web" / "node_modules").read_text() == "installed"
    assert (dst / "reflex.lock" / "bun.lock").read_text() == "locked"


def test_staged_playground_keeps_its_content_hash_across_an_edit(tmp_path: Path):
    dst = tmp_path / "staged"
    fixtures.stage_playground(dst)
    _git_init(dst)
    expected = (REPO / "examples" / "playground" / ".content-hash").read_text().strip()
    assert hash_examples.content_hash(dst) == expected
    edit = Edit(find_target(dst, "leaf"))
    edit.prepare("m-0123456789ab")
    edit.write()
    assert hash_examples.content_hash(dst) != expected
    edit.restore()
    assert hash_examples.content_hash(dst) == expected


def test_app_dir_is_per_arm(tmp_path: Path):
    ctx = make_context(tmp_path)
    assert fixtures.app_dir(ctx) == tmp_path / "app" / "A"
    ctx.arm = "B"
    assert fixtures.app_dir(ctx) == tmp_path / "app" / "B"


def test_app_env_points_reflex_at_the_staged_app(tmp_path: Path):
    ctx = make_context(tmp_path)
    ctx.env = {"PATH": "/bin"}
    app = tmp_path / "app"
    assert fixtures.app_env(ctx, app) == {
        "PATH": "/bin",
        "REFLEX_WEB_WORKDIR": str(app / ".web"),
        "REFLEX_STATES_WORKDIR": str(app / ".states"),
    }


def test_prime_stages_and_compiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ctx = make_context(tmp_path, {"app": "playground"})
    calls: list[tuple[list[str], Path, dict[str, str]]] = []

    class Result:
        def check(self) -> Result:
            return self

    def run_cli(python, args, *, cwd, env, timeout):
        calls.append((list(args), cwd, env))
        return Result()

    staged: list[Path] = []
    monkeypatch.setattr(fixtures, "run_cli", run_cli)
    monkeypatch.setitem(fixtures.FIXTURES, "playground", staged.append)
    app = fixtures.prime(ctx, "playground")
    assert app == tmp_path / "app" / "A"
    assert staged == [app]
    assert calls == [(["compile"], app, fixtures.app_env(ctx, app))]
