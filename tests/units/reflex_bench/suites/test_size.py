"""Tests for reflex_bench.suites.size."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import brotli
import pytest
from reflex_bench import registry
from reflex_bench.suites import size

from tests.units.reflex_bench.factories import make_context

FIXTURES = Path(__file__).parent.parent / "fixtures" / "size"

INDEX = (
    "<!DOCTYPE html><html><head>"
    '<link rel="preload" as="image" href="/logo.svg"/>'
    '<link rel="modulepreload" href="/assets/manifest-7ec94961.js"/>'
    '<link rel="modulepreload" href="/assets/entry.client-BspSxdqQ.js"/>'
    '<link rel="modulepreload" href="/assets/chunk-5KNZJZUH-q9CrfzJj.js"/>'
    '<link as="style" rel="preload" href="/assets/__reflex_global_styles-NccINl-w.css"/>'
    '<link href="https://fonts.example.com/inter.css" rel="stylesheet"/>'
    '<link href="/assets/__reflex_global_styles-NccINl-w.css" rel="stylesheet"/>'
    "</head><body>"
    '<script type="module" async="">import "/assets/manifest-7ec94961.js";</script>'
    '<script type="module" src="/assets/entry.client-BspSxdqQ.js"></script>'
    "</body></html>"
)
INITIAL = {
    "assets/manifest-7ec94961.js": b"window.__manifest={};" * 20,
    "assets/entry.client-BspSxdqQ.js": b"import{a}from'./chunk.js';a();" * 200,
    "assets/chunk-5KNZJZUH-q9CrfzJj.js": b"export const a=()=>1;" * 500,
    "assets/__reflex_global_styles-NccINl-w.css": b".rt-Button{color:red}" * 300,
}
OTHER = {
    "index.html": INDEX.encode(),
    "__spa-fallback.html": b"<!DOCTYPE html><html></html>",
    "logo.svg": b"<svg></svg>",
    "assets/_counter_._index-C9rBuGsa.js": b"export default 1;" * 40,
}
SIDECARS = {
    "index.html.gz": b"\x1f\x8b" * 30,
    "assets/entry.client-BspSxdqQ.js.gz": b"\x1f\x8b" * 100,
    "assets/entry.client-BspSxdqQ.js.br": b"\x0b" * 90,
}
WEB_FILES = {"app/routes/_index.jsx": b"export default () => null;", "bun.lock": b"{}"}
NODE_MODULES = {
    "react/index.js": b"module.exports={};" * 50,
    "react/package.json": b"{}",
}


def _write(root: Path, files: dict[str, bytes]) -> None:
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _gzip_size(data: bytes) -> int:
    # zlib's gzip container (wbits=31) at level 9, independent of the gzip module.
    compressor = zlib.compressobj(9, zlib.DEFLATED, 31)
    return len(compressor.compress(data) + compressor.flush())


def _export(root: Path) -> Path:
    """Write what `reflex export --frontend-only --no-zip` leaves behind, in small.

    Args:
        root: The directory to create the app in.

    Returns:
        The app directory.
    """
    app = root / "app"
    web = app / ".web"
    _write(web / "build" / "client", {**INITIAL, **OTHER, **SIDECARS})
    _write(web, WEB_FILES)
    _write(web / "node_modules", NODE_MODULES)
    (web / "node_modules" / ".bin").mkdir()
    (web / "node_modules" / ".bin" / "react").symlink_to("../react/index.js")
    (app / ".content-hash").write_text("sha256:abc123\n")
    return app


def _measure(root: Path) -> tuple[dict[str, float], dict[str, Any]]:
    result = size.measure_export(_export(root), reflex_version="0.9.12")
    assert result.extra is not None
    return dict(result.values), result.extra


def test_initial_and_total_bytes(tmp_path: Path):
    values, extra = _measure(tmp_path)
    everything = {**INITIAL, **OTHER}
    for field, compress in (
        ("raw", len),
        ("gzip", _gzip_size),
        ("brotli", lambda data: len(brotli.compress(data, quality=11))),
    ):
        assert values[f"initial_{field}"] == sum(map(compress, INITIAL.values()))
        assert values[f"total_{field}"] == sum(map(compress, everything.values()))
    assert values["initial_gzip"] < values["initial_raw"]
    assert extra["html"] == "index.html"


def test_initial_files_follow_the_page_order_once_each(tmp_path: Path):
    _, extra = _measure(tmp_path)
    # The external stylesheet is not part of the build; the preloads are not JS or CSS.
    assert extra["initial_files"] == [
        "assets/manifest-HASH.js",
        "assets/entry.client-HASH.js",
        "assets/chunk-5KNZJZUH-HASH.js",
        "assets/__reflex_global_styles-HASH.css",
    ]
    initial = {name for name, entry in extra["files"].items() if entry["initial"]}
    assert initial == set(extra["initial_files"])


def test_sidecars_are_excluded_and_summed(tmp_path: Path):
    values, extra = _measure(tmp_path)
    assert extra["sidecar_bytes"] == sum(map(len, SIDECARS.values()))
    assert not any(name.endswith((".gz", ".br", ".zst")) for name in extra["files"])
    assert values["total_raw"] == sum(map(len, {**INITIAL, **OTHER}.values()))


def test_chunks_count_the_javascript_assets(tmp_path: Path):
    values, _ = _measure(tmp_path)
    assert values["chunks"] == 4


def test_web_dir_and_node_modules_are_disjoint(tmp_path: Path):
    values, _ = _measure(tmp_path)
    client = {**INITIAL, **OTHER, **SIDECARS}
    assert values["web_dir"] == sum(map(len, {**client, **WEB_FILES}.values()))
    # Regular files only: the .bin symlink is not followed or counted.
    assert values["node_modules"] == sum(map(len, NODE_MODULES.values()))


def test_the_breakdown_strips_hashes(tmp_path: Path):
    _, extra = _measure(tmp_path)
    assert set(extra["files"]) == {
        "index.html",
        "__spa-fallback.html",
        "logo.svg",
        "assets/manifest-HASH.js",
        "assets/entry.client-HASH.js",
        "assets/chunk-5KNZJZUH-HASH.js",
        "assets/__reflex_global_styles-HASH.css",
        "assets/_counter_._index-HASH.js",
    }
    chunk = INITIAL["assets/chunk-5KNZJZUH-q9CrfzJj.js"]
    assert extra["files"]["assets/chunk-5KNZJZUH-HASH.js"] == {
        "raw": len(chunk),
        "gzip": _gzip_size(chunk),
        "brotli": len(brotli.compress(chunk, quality=11)),
        "initial": True,
    }
    assert extra["files"]["assets/_counter_._index-HASH.js"]["initial"] is False


@pytest.mark.parametrize(
    ("path", "stripped"),
    [
        ("assets/chunk-5KNZJZUH-q9CrfzJj.js", "assets/chunk-5KNZJZUH-HASH.js"),
        ("assets/manifest-7ec94961.js", "assets/manifest-HASH.js"),
        ("assets/entry.client-BspSxdqQ.js", "assets/entry.client-HASH.js"),
        (
            "assets/_item_.__item_id_._index-C-TMLTbt.js",
            "assets/_item_.__item_id_._index-HASH.js",
        ),
        ("assets/_404_._index-DEKlLv-N.js", "assets/_404_._index-HASH.js"),
        ("assets/link-D_rz9Rcp.js", "assets/link-HASH.js"),
        ("assets/code-Dzr0iVq-.js", "assets/code-HASH.js"),
        (
            "assets/emotion-react.browser.esm-BUuhssUM.js",
            "assets/emotion-react.browser.esm-HASH.js",
        ),
        ("assets/index-D1HOkqXd.js.map", "assets/index-HASH.js.map"),
        ("index.html", "index.html"),
        ("__spa-fallback.html", "__spa-fallback.html"),
        ("counter/index.html", "counter/index.html"),
        ("playground.css", "playground.css"),
        ("assets/react-dom.js", "assets/react-dom.js"),
        ("assets/nested/chunk-q9CrfzJj.js", "assets/nested/chunk-q9CrfzJj.js"),
    ],
)
def test_strip_hash(path: str, stripped: str):
    assert size.strip_hash(path) == stripped


def test_names_that_differ_only_in_their_hash_stay_apart(tmp_path: Path):
    app = _export(tmp_path)
    assets = app / ".web" / "build" / "client" / "assets"
    (assets / "index-AAAAAAAA.js").write_bytes(b"a" * 10)
    (assets / "index-BBBBBBBB.js").write_bytes(b"b" * 20)
    result = size.measure_export(app, reflex_version=None)
    assert result.extra is not None
    files = result.extra["files"]
    assert files["assets/index-HASH.js"]["raw"] == 10
    assert files["assets/index-HASH.js#2"]["raw"] == 20
    assert result.values["total_raw"] == sum(entry["raw"] for entry in files.values())


def test_a_missing_referenced_file_fails_with_its_name(tmp_path: Path):
    app = _export(tmp_path)
    (app / ".web/build/client/assets/chunk-5KNZJZUH-q9CrfzJj.js").unlink()
    with pytest.raises(FileNotFoundError, match=r"chunk-5KNZJZUH-q9CrfzJj\.js"):
        size.measure_export(app, reflex_version=None)


def test_a_missing_first_page_fails_clearly(tmp_path: Path):
    app = _export(tmp_path)
    (app / ".web/build/client/index.html").unlink()
    with pytest.raises(FileNotFoundError, match=r"index\.html"):
        size.measure_export(app, reflex_version=None)


def test_extra_is_json_and_repeatable(tmp_path: Path):
    app = _export(tmp_path)
    first = size.measure_export(app, reflex_version="0.8.23")
    second = size.measure_export(app, reflex_version="0.8.23")
    assert first == second
    assert first.extra is not None
    json.dumps(first.extra, allow_nan=False)
    assert first.extra["reflex_version"] == "0.8.23"
    assert first.extra["fixture_hash"] == "sha256:abc123"
    assert first.extra["bun_lock"] == f"sha256:{hashlib.sha256(b'{}').hexdigest()}"
    assert set(first.extra["compressors"]) == {"zlib", "brotli"}
    (app / ".web" / "bun.lock").unlink()
    without_lock = size.measure_export(app, reflex_version="0.8.23").extra
    assert without_lock is not None
    assert without_lock["bun_lock"] is None


@pytest.mark.parametrize(
    ("fixture", "count", "first", "last"),
    [
        (
            "head-index.html",
            13,
            "/assets/manifest-24546cb6.js",
            "/assets/__reflex_global_styles-Bja7d8zq.css",
        ),
        (
            "0.8.23-index.html",
            12,
            "/assets/manifest-23f351b0.js",
            "/assets/__reflex_global_styles-BOXGY6tA.css",
        ),
    ],
)
def test_real_first_pages(fixture: str, count: int, first: str, last: str):
    refs = size.initial_assets((FIXTURES / fixture).read_text(encoding="utf-8"))
    assert len(refs) == count
    assert (refs[0], refs[-1]) == (first, last)
    assert all(ref.startswith("/assets/") for ref in refs)
    assert [ref for ref in refs if ref.endswith(".css")] == [last]


def test_the_benchmark_declares_what_sample_returns(tmp_path: Path):
    bench = registry.discover()["size.export"]
    assert bench.exact
    assert bench.kind == "track"
    assert bench.suites == ("pr", "daily")
    assert bench.params == {"app": ("playground",)}
    assert {metric.direction for metric in bench.metrics.values()} == {"lower"}
    _export(tmp_path)
    ctx = make_context(tmp_path, {"app": "playground"})
    result = bench.normalize(size.ExportSize().sample(ctx))
    assert result.values["chunks"] == 4
    assert result.extra is not None
    assert result.extra["reflex_version"] == ctx.subject.reflex_version


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    demo = root / "examples" / "demo"
    tracked = {"rxconfig.py": b"config = 1\n", "demo/demo.py": b"app = 1\n"}
    _write(demo, {**tracked, "deleted.py": b""})
    _write(root, {".gitignore": b".web/\n"})
    _git(root, "init", "-q")
    _git(root, "add", ".")
    (demo / "deleted.py").unlink()
    _write(demo, {"untracked.py": b"", ".web/stale.js": b""})
    monkeypatch.chdir(root)
    return root


def test_copy_example_copies_tracked_files_only(repo: Path, tmp_path: Path):
    dest = tmp_path / "cache" / "app"
    _write(dest, {"old.py": b"", ".web/build/client/index.html": b""})
    size.copy_example("demo", dest)
    copied = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*"))
    assert copied == ["demo", "demo/demo.py", "rxconfig.py"]


def test_copy_example_fails_clearly_without_the_example(repo: Path, tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="examples/missing"):
        size.copy_example("missing", tmp_path / "app")


def test_setup_cache_exports_a_fresh_copy(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    calls = []

    def fake_run_cli(python: Path, args: list[str], **kwargs: Any) -> SimpleNamespace:
        calls.append((python, args, kwargs))
        return SimpleNamespace(check=lambda: None)

    monkeypatch.setattr(size, "run_cli", fake_run_cli)
    cache = tmp_path / "cache"
    cache.mkdir()
    ctx = make_context(cache, {"app": "demo"})
    size.ExportSize().setup_cache(ctx)
    ((python, args, kwargs),) = calls
    assert python == ctx.subject.python
    assert list(args) == ["export", "--frontend-only", "--no-zip", "--env", "prod"]
    assert kwargs["cwd"] == cache / "app"
    assert kwargs["env"]["REFLEX_DIR"] == str(cache / "reflex")
    assert (cache / "app" / "rxconfig.py").read_text() == "config = 1\n"
