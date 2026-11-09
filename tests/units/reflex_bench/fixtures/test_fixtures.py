"""Tests for reflex_bench.fixtures."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_bench import fixtures
from reflex_bench.drivers.editor import Edit, find_target
from reflex_bench.schema import FixtureDoc

from scripts import hash_examples
from tests.units.reflex_bench.factories import make_context

REPO = Path(__file__).parents[4]
PLAYGROUND = REPO / "examples" / "playground"


def _files(root: Path) -> set[str]:
    """List the files under a directory.

    Returns:
        POSIX paths relative to ``root``.
    """
    return {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }


def _tracked() -> set[str]:
    """List the playground files git tracks.

    Returns:
        POSIX paths relative to the playground.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PLAYGROUND,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {path for path in listing.split("\0") if path}


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


def test_the_hash_is_the_committed_line():
    committed = (PLAYGROUND / ".content-hash").read_text(encoding="utf-8").strip()
    assert committed.startswith("sha256:")
    assert fixtures.describe_playground() == {
        "name": "playground",
        "content_hash": committed,
        "params": {},
    }


def test_materialize_playground_copies_the_tracked_files(tmp_path: Path):
    doc = fixtures.materialize_playground(tmp_path / "app")
    assert doc == fixtures.describe_playground()
    copied = _files(tmp_path / "app")
    assert _tracked() - {".content-hash"} <= copied
    assert ".content-hash" not in copied


def test_materialize_playground_skips_build_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source"
    shutil.copytree(PLAYGROUND, source)
    junk = [
        ".web/package.json",
        ".states/state.pkl",
        "playground/__pycache__/state.cpython-314.pyc",
        "playground/stray.pyc",
        "reflex.db",
        "reflex.lock/bun.lock",
        "uv.lock",
        ".venv/bin/python",
        "uploaded_files/upload.txt",
        "assets/external/reflex/lib.js",
    ]
    # Only assets/external is ignored, not any directory named external.
    kept = ["playground/external/notes.txt", "assets/externals.css"]
    for name in (*junk, *kept):
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        (source / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(fixtures, "playground_dir", lambda: source)
    fixtures.materialize_playground(tmp_path / "app")
    assert _files(tmp_path / "app") == (_tracked() - {".content-hash"}) | set(kept)


def _counting_make(doc: FixtureDoc, made: list[Path]) -> Callable[[Path], None]:
    """Build a ``make`` that writes one file and counts its calls.

    Returns:
        The function.
    """

    def make(dest: Path) -> None:
        dest.mkdir()
        (dest / "rxconfig.py").write_text(doc["content_hash"], encoding="utf-8")
        made.append(dest)

    return make


DOC: FixtureDoc = {
    "name": "gen",
    "content_hash": "sha256:" + "1" * 64,
    "params": {"pages": 10},
}


def test_ensure_fixture_reuses_an_app_whose_stamp_matches(tmp_path: Path):
    made: list[Path] = []
    app = fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    assert app == tmp_path / "app"
    assert json.loads((tmp_path / fixtures.STAMP).read_text(encoding="utf-8")) == DOC
    # What priming added to the app survives the reuse.
    (app / ".web").mkdir()
    assert (
        fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made)) == app
    )
    assert made == [app]
    assert (app / ".web").is_dir()


def test_ensure_fixture_rebuilds_on_a_changed_stamp(tmp_path: Path):
    made: list[Path] = []
    app = fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    (app / ".web").mkdir()
    changed: FixtureDoc = {**DOC, "content_hash": "sha256:" + "2" * 64}
    assert (
        fixtures.ensure_fixture(
            tmp_path, lambda: changed, _counting_make(changed, made)
        )
        == app
    )
    assert made == [app, app]
    assert (
        json.loads((tmp_path / fixtures.STAMP).read_text(encoding="utf-8")) == changed
    )
    assert not (app / ".web").exists()
    assert (app / "rxconfig.py").read_text(encoding="utf-8") == changed["content_hash"]


def test_ensure_fixture_rebuilds_after_an_interrupted_make(tmp_path: Path):
    def broken(dest: Path) -> None:
        dest.mkdir()
        msg = "interrupted"
        raise KeyboardInterrupt(msg)

    fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, []))
    changed: FixtureDoc = {**DOC, "content_hash": "sha256:" + "2" * 64}
    with pytest.raises(KeyboardInterrupt):
        fixtures.ensure_fixture(tmp_path, lambda: changed, broken)
    # The half-made app carries no stamp, so it is never reused.
    assert not (tmp_path / fixtures.STAMP).exists()
    made: list[Path] = []
    fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    assert made == [tmp_path / "app"]


def test_ensure_fixture_rebuilds_a_missing_app(tmp_path: Path):
    made: list[Path] = []
    app = fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    shutil.rmtree(app)
    fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    assert made == [app, app]


MARKER = '''\
"""A module with two hot reload targets."""

LEAF_MARKER = "m-initial-leaf"  # bench:hmr-target leaf
LEAF_3_MARKER = "m-initial-leaf-3"  # bench:hmr-target leaf-3
OTHER = "m-initial-leaf"
'''


def test_bump_marker_rewrites_exactly_the_pragma_line(tmp_path: Path):
    path = tmp_path / "marker.py"
    path.write_text(MARKER, encoding="utf-8")
    assert fixtures.bump_marker(path, "leaf", 1) == "m-1-leaf"
    assert fixtures.bump_marker(path, "leaf-3", 1) == "m-1-leaf-3"
    assert fixtures.bump_marker(path, "leaf", 7) == "m-7-leaf"
    assert path.read_text(encoding="utf-8") == MARKER.replace(
        '"m-initial-leaf"  # bench:hmr-target leaf\n',
        '"m-7-leaf"  # bench:hmr-target leaf\n',
    ).replace('"m-initial-leaf-3"', '"m-1-leaf-3"')


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            'X = "m-initial-root"  # bench:hmr-target root\n',
            "0 hot reload target lines for leaf",
        ),
        (MARKER + MARKER, "2 hot reload target lines for leaf"),
    ],
)
def test_bump_marker_needs_exactly_one_target(tmp_path: Path, text: str, message: str):
    path = tmp_path / "marker.py"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        fixtures.bump_marker(path, "leaf", 1)
    assert path.read_text(encoding="utf-8") == text


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
    for output in (".venv", ".web", ".states", "reflex.lock", "uploaded_files"):
        (source / output).mkdir()
        (source / output / "junk").write_text("x")
    (source / "assets" / "external").mkdir(parents=True)
    (source / "assets" / "external" / "junk.js").write_text("x")
    (source / "assets" / "logo.svg").write_text("<svg/>")
    return source


def test_stage_skips_build_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = _fake_playground(tmp_path)
    monkeypatch.setattr(fixtures, "playground_dir", lambda: source)
    dst = tmp_path / "staged"
    fixtures.stage_playground(dst)
    staged = sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*"))
    assert staged == ["app", "app/app.py", "assets", "assets/logo.svg", "rxconfig.py"]


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
