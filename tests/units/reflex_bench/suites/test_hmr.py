"""Tests for reflex_bench.suites.hmr, with a fake app and browser."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil
import pytest
from reflex_bench import fixtures, registry
from reflex_bench.context import Context
from reflex_bench.registry import SampleResult
from reflex_bench.suites import hmr

from tests.units.reflex_bench.factories import make_context

from .fakes import FakeApp, FakeBrowser, FakeTab

ORIGINAL = {
    "#bench-marker-leaf": "m-initial-leaf",
    "#bench-marker-root": "m-initial-root",
    "#bench-handler-value": "",
    ".bench-hooks": "12px",
    'img[alt="Playground logo"]': "300",
    "#count": "0",
}


@pytest.fixture
def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Context:
    """Stage the playground where the hooks look for it and swap in the fakes.

    Returns:
        The benchmark context.
    """
    ctx = make_context(tmp_path, {"app": "playground"})
    shutil.copytree(
        fixtures.playground_dir(),
        fixtures.app_dir(ctx),
        ignore=shutil.ignore_patterns("__pycache__", ".web", ".states"),
    )
    monkeypatch.setattr(hmr, "AppProcess", FakeApp)
    monkeypatch.setattr(hmr, "Browser", FakeBrowser)
    monkeypatch.setattr(FakeBrowser, "values", ORIGINAL)
    monkeypatch.setattr(FakeBrowser, "configure", None)
    monkeypatch.setattr(FakeApp, "created", [])
    monkeypatch.setattr(FakeBrowser, "created", [])
    return ctx


def _tab(bench: Any) -> FakeTab:
    return bench.tab


def _file(ctx: Context, relative: str) -> bytes:
    return (fixtures.app_dir(ctx) / relative).read_bytes()


LEAF = "playground/components/marker.py"


def test_registrations():
    found = registry.discover()
    dev = {
        "hmr.render.leaf": ("pr", "daily"),
        "hmr.render.root": ("pr", "daily"),
        "hmr.handler": ("pr", "daily"),
        "hmr.css": ("daily",),
        "hmr.asset": ("daily",),
        "hmr.reconnect": ("daily",),
        "hmr.watcher": ("daily",),
    }
    preview = {f"{id}.preview" for id in dev} - {"hmr.watcher.preview"}
    assert {id for id in found if id.startswith("hmr.")} == {*dev, *preview}
    for id in (*dev, *preview):
        bench = found[id]
        assert bench.suites == dev.get(id, ("daily",))
        assert bench.min_version == (None if id in dev else "0.9.8")
        assert bench.kind == "latency"
        assert bench.params == {"app": ("playground",)}
        assert set(bench.metrics) == {"latency", "full_reloads"}
        assert (bench.metrics["latency"].unit, bench.metrics["full_reloads"].unit) == (
            "s",
            "1",
        )
        assert (bench.warmup, bench.timeout) == (3, 120)


def test_hook_sequence(ctx: Context):
    bench = hmr.RenderLeaf()
    original = _file(ctx, LEAF)
    bench.setup(ctx)
    app = FakeApp.created[0]
    assert (app.mode, app.phases) == ("dev", True)
    assert app.calls == ["start", "http", "interactive /"]
    tab = _tab(bench)
    # setup reads the original value once the page is quiet.
    assert tab.calls == [("wait_quiet", hmr.QUIET_S)]
    assert bench.original == "m-initial-leaf"

    tab.calls.clear()
    bench.prepare(ctx)
    # prepare waits for a quiet page, then arms the watch; the file is untouched.
    assert [call[0] for call in tab.calls] == ["wait_quiet", "set_alive", "watch"]
    _, id, kind, selector, marker = tab.calls[-1]
    assert (id, kind, selector) == ("edit", "text", "#bench-marker-leaf")
    assert marker.startswith("m-")
    assert _file(ctx, LEAF) == original

    tab.calls.clear()
    result = bench.sample(ctx)
    assert isinstance(result, SampleResult)
    # The edit was on disk before the wait, and the sample ends at the mark.
    assert f'"{marker}"'.encode() in _file(ctx, LEAF)
    assert tab.calls == [("poll_mark", "edit")]
    assert result.values["full_reloads"] == 0
    assert 0 < result.values["latency"] < 1
    extra = result.extra
    assert extra is not None
    assert extra["marker"] == marker
    assert extra["fixture_hash"] == fixtures.fixture_hash("playground")
    assert extra["console"] == {"warning": 1}
    hops = extra["hops"]
    assert 0 < hops["watcher_seen_s"] <= hops["compile_done_s"] <= hops["dom_updated_s"]
    assert hops["dom_updated_s"] == result.values["latency"]
    assert extra["watcher_line"] == "Changes detected, reloading workers.."

    tab.calls.clear()
    bench.conclude(ctx)
    assert _file(ctx, LEAF) == original
    # A reload right after the hot update must not pass for one: the tag is
    # read again once the page is quiet, before the restore.
    assert tab.calls == [
        ("unwatch", "edit"),
        ("wait_quiet", hmr.QUIET_S),
        ("alive",),
        ("watch", "restore", "text", "#bench-marker-leaf", "m-initial-leaf"),
        ("poll_mark", "restore"),
        ("wait_quiet", hmr.QUIET_S),
    ]
    bench.cleanup(ctx)
    assert app.calls[-1] == "stop"
    assert FakeBrowser.created[0].closed


def test_markers_are_unique_per_edit(ctx: Context):
    bench = hmr.RenderLeaf()
    bench.setup(ctx)
    markers = []
    for _ in range(5):
        bench.prepare(ctx)
        markers.append(_tab(bench).watches["edit"][2])
        bench.sample(ctx)
        bench.conclude(ctx)
    assert len(set(markers)) == 5
    assert "m-initial-leaf" not in markers
    bench.cleanup(ctx)


def test_conclude_restores_after_a_failed_sample(ctx: Context):
    bench = hmr.RenderRoot()
    original = _file(ctx, "playground/layout.py")
    bench.setup(ctx)
    bench.prepare(ctx)
    _tab(bench).fail = TimeoutError("the page never showed the marker")
    with pytest.raises(TimeoutError):
        bench.sample(ctx)
    assert _file(ctx, "playground/layout.py") != original
    _tab(bench).fail = None
    bench.conclude(ctx)
    assert _file(ctx, "playground/layout.py") == original
    # The watch the page never satisfied does not stay pending.
    assert ("unwatch", "edit") in _tab(bench).calls
    assert "edit" not in _tab(bench).watches
    bench.cleanup(ctx)


def test_a_change_the_page_never_shows_fails_clearly(ctx: Context):
    # hmr.css and hmr.asset in dev: no hot update, no reload.
    bench = hmr.Asset()
    original = _file(ctx, "assets/logo.svg")
    bench.setup(ctx)
    bench.prepare(ctx)
    tab = _tab(bench)
    tab.misses = 1
    with pytest.raises(TimeoutError) as info:
        bench.sample(ctx)
    assert str(info.value) == (
        'the page did not show the edit (naturalWidth of img[alt="Playground logo"])'
        " within the hook's 90 s: granian printed no reload line, no [timing]"
        " line followed, the page did not reload"
    )
    bench.conclude(ctx)
    assert _file(ctx, "assets/logo.svg") == original
    bench.cleanup(ctx)


def test_describe_miss_tells_which_side_dropped_the_change():
    steps = {"watcher_seen_s": 0.154, "compile_done_s": 1.188, "dom_updated_s": None}
    assert hmr.describe_miss(steps, False) == (
        "granian saw it after 0.15 s, the last [timing] line came after 1.19 s,"
        " the page did not reload"
    )
    # Preview twins reload the page themselves: nothing to say about reloads.
    assert hmr.describe_miss(steps, None).endswith("1.19 s")
    assert hmr.describe_miss(steps, True).endswith("the page reloaded")


def test_conclude_on_a_foreign_thread_kills_the_browser(ctx: Context):
    bench = hmr.RenderLeaf()
    original = _file(ctx, LEAF)
    bench.setup(ctx)
    bench.prepare(ctx)
    _tab(bench).fail = TimeoutError("stuck")
    with pytest.raises(TimeoutError):
        bench.sample(ctx)
    # After a timeout the teardown runs on a fresh thread that must not touch
    # Playwright: the file is restored and the browser killed, which ends the
    # abandoned wait.
    browser = FakeBrowser.created[0]
    browser.owner = False
    tab = _tab(bench)
    tab.calls.clear()
    bench.conclude(ctx)
    assert _file(ctx, LEAF) == original
    assert browser.killed
    assert tab.calls == []
    bench.cleanup(ctx)
    assert FakeApp.created[0].calls[-1] == "stop"


def test_a_full_reload_is_counted_and_fails_the_sample_in_conclude(ctx: Context):
    bench = hmr.Handler()
    original = _file(ctx, "playground/state.py")
    bench.setup(ctx)
    _tab(bench).reloads = 1
    bench.prepare(ctx)
    # The mark came from a reloaded document: the sample says so and returns.
    result = bench.sample(ctx)
    assert result.values["full_reloads"] == 1
    with pytest.raises(hmr.FullReloadError, match="reloaded"):
        bench.conclude(ctx)
    # The file was restored before the failure.
    assert _file(ctx, "playground/state.py") == original
    bench.cleanup(ctx)


def test_a_reload_right_after_the_hot_update_fails_the_sample(ctx: Context):
    bench = hmr.RenderLeaf()
    bench.setup(ctx)
    bench.prepare(ctx)
    result = bench.sample(ctx)
    assert result.values["full_reloads"] == 0
    # The page reloads before it is quiet again.
    _tab(bench).token = None
    with pytest.raises(hmr.FullReloadError, match="reloaded"):
        bench.conclude(ctx)
    bench.cleanup(ctx)


def test_conclude_does_not_check_the_tag_after_a_failed_sample(ctx: Context):
    bench = hmr.RenderLeaf()
    bench.setup(ctx)
    bench.prepare(ctx)
    _tab(bench).fail = TimeoutError("the page never showed the marker")
    with pytest.raises(TimeoutError):
        bench.sample(ctx)
    _tab(bench).fail = None
    _tab(bench).token = None
    bench.conclude(ctx)  # no FullReloadError on top of the sample's failure
    bench.cleanup(ctx)


def test_every_wait_of_a_hook_shares_one_deadline(
    ctx: Context, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(hmr, "WAIT_S", 1.0)
    timeouts: list[tuple[str, float]] = []

    class SlowTab(FakeTab):
        def wait_quiet(self, seconds: float, timeout: float) -> None:
            timeouts.append(("wait_quiet", timeout))
            time.sleep(0.3)

        def poll_mark(self, id: str, timeout: float) -> dict[str, Any] | None:
            timeouts.append(("poll_mark", timeout))
            time.sleep(0.3)
            return super().poll_mark(id, timeout)

    monkeypatch.setattr(FakeBrowser, "tab_class", SlowTab)
    bench = hmr.RenderLeaf()
    bench.setup(ctx)
    bench.prepare(ctx)
    bench.sample(ctx)
    timeouts.clear()
    bench.conclude(ctx)
    assert [name for name, _ in timeouts] == ["wait_quiet", "poll_mark", "wait_quiet"]
    first, second, third = (timeout for _, timeout in timeouts)
    assert first <= 1.0
    assert second <= first - 0.3
    assert third <= second - 0.3
    bench.cleanup(ctx)


def test_a_passed_deadline_fails_the_wait(
    ctx: Context, monkeypatch: pytest.MonkeyPatch
):
    class SlowTab(FakeTab):
        def wait_quiet(self, seconds: float, timeout: float) -> None:
            time.sleep(0.15)

    monkeypatch.setattr(FakeBrowser, "tab_class", SlowTab)
    bench = hmr.RenderLeaf()
    bench.setup(ctx)
    bench.prepare(ctx)
    bench.sample(ctx)
    monkeypatch.setattr(hmr, "WAIT_S", 0.1)
    with pytest.raises(TimeoutError, match=r"0\.1 s"):
        bench.conclude(ctx)
    bench.cleanup(ctx)


def test_style_and_asset_changes_count_a_reload_without_failing(ctx: Context):
    for cls, path in (
        (hmr.Css, "assets/playground.css"),
        (hmr.Asset, "assets/logo.svg"),
    ):
        bench = cls()
        original = _file(ctx, path)
        bench.setup(ctx)
        _tab(bench).reloads = 1
        bench.prepare(ctx)
        result = bench.sample(ctx)
        assert result.values["full_reloads"] == 1
        assert result.values["latency"] > 0
        assert _file(ctx, path) != original
        bench.conclude(ctx)
        assert _file(ctx, path) == original
        bench.cleanup(ctx)


def test_css_edit_changes_the_font_size_of_the_hooks(ctx: Context):
    bench = hmr.Css()
    bench.setup(ctx)
    bench.prepare(ctx)
    _, _, kind, selector, size = _tab(bench).calls[-1]
    assert (kind, selector) == ("style:font-size", ".bench-hooks")
    assert size.endswith("px")
    assert size != ORIGINAL[".bench-hooks"]
    bench.sample(ctx)
    css = _file(ctx, "assets/playground.css").decode()
    assert f"font-size: {size};" in css
    bench.conclude(ctx)
    bench.cleanup(ctx)


def test_asset_edit_sizes_the_logo_with_the_cache_off(ctx: Context):
    bench = hmr.Asset()
    bench.setup(ctx)
    tab = _tab(bench)
    assert ("cdp", "Network.setCacheDisabled", {"cacheDisabled": True}) in tab.calls
    bench.prepare(ctx)
    _, _, kind, selector, width = tab.calls[-1]
    assert (kind, selector) == ("naturalWidth", 'img[alt="Playground logo"]')
    assert width != ORIGINAL[selector]
    result = bench.sample(ctx)
    svg = _file(ctx, "assets/logo.svg").decode()
    assert svg.startswith(f'<svg width="{width}" height="{width}"')
    assert result.extra is not None
    assert result.extra["cache_disabled"] is True
    bench.conclude(ctx)
    bench.cleanup(ctx)


def test_style_and_asset_edits_skip_the_original_value(
    ctx: Context, monkeypatch: pytest.MonkeyPatch
):
    # The first edit's value is the page's original one: its watch would hold
    # before the edit is written.
    for cls, selector, original, planned in (
        (hmr.Css, ".bench-hooks", "20.25px", "61.25px"),
        (hmr.Asset, 'img[alt="Playground logo"]', "42", "442"),
    ):
        monkeypatch.setattr(FakeBrowser, "values", {**ORIGINAL, selector: original})
        bench = cls()
        bench.setup(ctx)
        bench.prepare(ctx)
        assert _tab(bench).calls[-1] == ("watch", "edit", bench.kind, selector, planned)
        bench.cleanup(ctx)


def test_handler_clicks_until_the_new_value_shows(ctx: Context):
    bench = hmr.Handler()
    bench.setup(ctx)
    bench.prepare(ctx)
    tab = _tab(bench)
    tab.misses = 2
    tab.calls.clear()
    result = bench.sample(ctx)
    clicks = [call for call in tab.calls if call[0] == "click"]
    assert clicks == [("click", "#bench-handler")] * 3
    assert result.extra is not None
    assert result.extra["clicks"] == 3
    assert result.values["full_reloads"] == 0
    bench.conclude(ctx)
    bench.cleanup(ctx)


def test_preview_reloads_the_page_itself(ctx: Context):
    bench = hmr.RenderLeafPreview()
    bench.setup(ctx)
    assert FakeApp.created[0].mode == "preview"
    bench.prepare(ctx)
    tab = _tab(bench)
    tab.misses = 1
    tab.calls.clear()
    result = bench.sample(ctx)
    assert [call[0] for call in tab.calls[:4]] == [
        "reload",
        "poll_mark",
        "reload",
        "poll_mark",
    ]
    # Preview has no live reload: the harness's own reloads are the method.
    assert result.values["full_reloads"] == 0
    assert result.extra is not None
    assert result.extra["reloads"] == 2
    tab.calls.clear()
    bench.conclude(ctx)
    assert ("reload",) in tab.calls
    bench.cleanup(ctx)


def test_watcher_latency_is_the_watcher_line(ctx: Context):
    bench = hmr.Watcher()
    bench.setup(ctx)
    bench.prepare(ctx)
    result = bench.sample(ctx)
    assert result.extra is not None
    assert result.values["latency"] == result.extra["hops"]["watcher_seen_s"]
    bench.conclude(ctx)
    bench.cleanup(ctx)


def test_reconnect_kills_the_worker_and_clicks_on_the_counter(
    ctx: Context, monkeypatch: pytest.MonkeyPatch
):
    signalled: list[tuple[str, int]] = []

    class Proc:
        def __init__(self, name: str) -> None:
            self.name = name

        def send_signal(self, sig: int) -> None:
            signalled.append((self.name, sig))

    monkeypatch.setattr(
        hmr, "granian_processes", lambda app: (Proc("supervisor"), Proc("worker"))
    )
    bench = hmr.Reconnect()
    bench.setup(ctx)
    assert FakeApp.created[0].calls[-1] == "interactive /counter"
    bench.prepare(ctx)
    tab = _tab(bench)
    assert tab.calls[-1] == ("watch", "edit", "changed", "#count", "0")
    assert signalled == []  # the processes are looked up before the timed region
    result = bench.sample(ctx)
    # A crash, then the respawn granian's reloader leaves to a SIGHUP.
    assert signalled == [("worker", signal.SIGKILL), ("supervisor", signal.SIGHUP)]
    assert [call for call in tab.calls if call[0] == "click"] == [
        ("click", "#increment")
    ]
    assert result.values["full_reloads"] == 0
    tab.calls.clear()
    bench.conclude(ctx)
    # Nothing to restore: the page only has to settle, and keep its document.
    assert tab.calls == [
        ("unwatch", "edit"),
        ("wait_quiet", hmr.QUIET_S),
        ("alive",),
        ("wait_quiet", hmr.QUIET_S),
    ]
    bench.cleanup(ctx)


def test_cleanup_restores_an_edit_left_behind(ctx: Context):
    bench = hmr.RenderLeaf()
    original = _file(ctx, LEAF)
    bench.setup(ctx)
    bench.prepare(ctx)
    bench.sample(ctx)
    bench.cleanup(ctx)
    assert _file(ctx, LEAF) == original
    assert FakeApp.created[0].calls[-1] == "stop"


def test_hops_follow_the_edit():
    lines = [
        (0.5, "Changes detected, reloading workers.."),  # an earlier reload
        (0.6, "[timing] Compile pages: 0.20s"),
        (2.02, "Changes detected, reloading workers.."),
        (2.03, "Modified: /app/playground/components/marker.py"),
        (2.5, "[timing] Evaluate Pages (Backend): 0.20s"),
        (2.7, "[timing] Write to Disk: 0.01s"),
        (2.8, "Compiling: 100%"),
    ]
    watcher = hmr.watcher_line(lines, edit_at=2.0)
    assert watcher == (2.02, "Changes detected, reloading workers..")
    assert hmr.hops(lines, 2.0, 0.9, watcher) == {
        "watcher_seen_s": pytest.approx(0.02),
        "compile_done_s": pytest.approx(0.7),
        "dom_updated_s": 0.9,
    }
    # A restart without an edit (hmr.reconnect): the compile after the kill.
    assert hmr.hops(lines[4:], 2.0, 0.9, None) == {
        "watcher_seen_s": None,
        "compile_done_s": pytest.approx(0.7),
        "dom_updated_s": 0.9,
    }
    assert hmr.watcher_line([], edit_at=2.0) is None
    assert hmr.hops([], 2.0, 0.9, None) == {
        "watcher_seen_s": None,
        "compile_done_s": None,
        "dom_updated_s": 0.9,
    }


def test_granian_worker_is_the_other_listener_of_the_backend_port():
    # A root with two Python children, like reflex's dev tree (multiprocessing's
    # resource tracker and granian's worker): the worker is the one listening on
    # the backend port.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    listener = (
        "import socket, time; s = socket.socket();"
        f"s.bind(('127.0.0.1', {port})); s.listen(); print('up', flush=True);"
        "time.sleep(60)"
    )
    code = (
        "import subprocess, sys, time;"
        "idle = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
        f"worker = subprocess.Popen([sys.executable, '-c', {listener!r}], stdout=subprocess.PIPE);"
        "worker.stdout.readline(); print(worker.pid, flush=True); time.sleep(60)"
    )
    root = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True
    )
    tree = psutil.Process(root.pid)
    try:
        assert root.stdout is not None
        worker_pid = int(root.stdout.readline())
        app = FakeApp(Path(), Path(), mode="dev", reflex_version=None, env={})
        app.pid, app.backend_url = root.pid, f"http://localhost:{port}"
        supervisor, worker = hmr.granian_processes(app)  # pyright: ignore[reportArgumentType]
        assert (supervisor.pid, worker.pid) == (root.pid, worker_pid)
    finally:
        for proc in [*tree.children(recursive=True), tree]:
            with contextlib.suppress(psutil.NoSuchProcess):
                proc.kill()
        root.wait()


def test_granian_processes_need_a_listening_worker():
    app = FakeApp(Path(), Path(), mode="dev", reflex_version=None, env={})
    app.pid = os.getpid()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        app.backend_url = f"http://localhost:{probe.getsockname()[1]}"
    with pytest.raises(LookupError, match="no process of the app listens"):
        hmr.granian_processes(app)  # pyright: ignore[reportArgumentType]
