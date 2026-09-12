"""Audit a typical Reflex app for blocking calls on the backend event loop.

Runs a small app in-process via ``AppHarness`` (dev) or ``AppHarnessProd`` with
`blockbuster <https://github.com/cbornet/blockbuster>`_ patched into *recording*
mode, drives it with Playwright, and writes a report listing every blocking
call (file/socket/sqlite/lock/sleep) that ran on an asyncio loop, with the
Python stack that reached it.

Usage (blockbuster and aiosqlite are not project deps, so install them
ad hoc; ``uv run`` would re-sync them away, hence the direct interpreter)::

    uv pip install blockbuster aiosqlite
    REFLEX_STATE_MANAGER_MODE=memory .venv/bin/python scripts/blockbuster_audit.py
    REFLEX_STATE_MANAGER_MODE=disk .venv/bin/python scripts/blockbuster_audit.py
    REFLEX_STATE_MANAGER_MODE=redis REFLEX_REDIS_URL=redis://localhost:6379 \\
        .venv/bin/python scripts/blockbuster_audit.py
    .venv/bin/python scripts/blockbuster_audit.py --prod   # backend-served static frontend

The same recorder doubles as a pytest plugin that instruments the unit-test
loops::

    BB_REPORT=/tmp/bb_pytest.txt .venv/bin/python -m pytest \\
        -p scripts.blockbuster_audit tests/units/istate

Blockbuster only sees *syscall-shaped* blocking (stat/open/read/socket/
sqlite/contended threading.Lock/time.sleep). CPU-bound work on the loop such
as pickling, deepcopy or ``get_type_hints`` is invisible to it.
"""

# ruff: noqa: T201, ANN001, DOC201, N802, D301

from __future__ import annotations

import argparse
import asyncio
import inspect
import os
import sys
import threading
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_lock = threading.Lock()
_findings: dict[tuple, list[tuple[str, int, str]]] = {}
_counts: dict[tuple, int] = defaultdict(int)


def _record(func_name: str, frame) -> None:
    frames = []
    f = frame
    while f:
        frames.append((f.f_code.co_filename, f.f_lineno, f.f_code.co_name))
        f = f.f_back
    frames.reverse()
    sig = tuple((fn, name) for fn, _, name in frames if "blockbuster" not in fn)
    key = (func_name, sig)
    with _lock:
        _counts[key] += 1
        _findings.setdefault(key, frames)


def _wrap_blocking_recording(
    modules, excluded_modules, func, func_name, can_block_functions, can_block_predicate
):
    """Drop-in for ``blockbuster._wrap_blocking`` that records instead of raising."""
    import blockbuster.blockbuster as bbmod

    def wrapper(*args, **kwargs):
        if bbmod.blockbuster_skip.get(False):
            return func(*args, **kwargs)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return func(*args, **kwargs)
        skip_token = bbmod.blockbuster_skip.set(True)
        try:
            if can_block_predicate(*args, **kwargs):
                return func(*args, **kwargs)
            frame = inspect.currentframe().f_back  # pyright: ignore[reportOptionalMemberAccess]
            f = frame
            while f:
                fname = f.f_code.co_filename.replace("\\", "/")
                for filename, functions in can_block_functions:
                    if fname.endswith(filename) and f.f_code.co_name in functions:
                        return func(*args, **kwargs)
                f = f.f_back
            _record(func_name, frame)
            return func(*args, **kwargs)
        finally:
            bbmod.blockbuster_skip.reset(skip_token)

    return wrapper


def activate():
    """Patch blockbuster into recording mode and activate all its checks.

    Returns:
        The active BlockBuster instance.
    """
    import blockbuster.blockbuster as bbmod

    bbmod._wrap_blocking = _wrap_blocking_recording  # pyright: ignore[reportPrivateUsage]
    bb = bbmod.BlockBuster()
    bb.activate()
    return bb


def report(path: str | Path) -> int:
    """Write the recorded findings to ``path``.

    Args:
        path: Output file.

    Returns:
        Number of distinct findings written.
    """
    root = str(REPO_ROOT) + "/"
    venv = root + ".venv/"

    def short(fn: str) -> str:
        if fn.startswith(venv):
            return "venv:" + fn.split("site-packages/", 1)[-1]
        return fn.removeprefix(root)

    def is_repo(fn: str) -> bool:
        return fn.startswith(root) and not fn.startswith(venv)

    with _lock:
        items = sorted(_findings.items(), key=lambda kv: -_counts[kv[0]])
    out = []
    written = 0
    for (func_name, sig), frames in items:
        if any(Path(__file__).name in fn for fn, _, _ in frames):
            continue  # driver noise: playwright's sync API runs a loop in the main thread
        repo_frames = [fr for fr in frames if is_repo(fr[0])]
        innermost = repo_frames[-1] if repo_frames else frames[-1]
        if not repo_frames:
            origin = "3RDPARTY"
        elif "/tests/" in innermost[0]:
            origin = "TEST"
        else:
            origin = "REFLEX"
        n = _counts[func_name, sig]
        out.append(
            f"\n=== [{origin}] {func_name}  x{n}  innermost: "
            f"{short(innermost[0])}:{innermost[1]} {innermost[2]}"
        )
        out.extend(f"    {short(fn)}:{ln}  {name}" for fn, ln, name in frames[-25:])
        written += 1
    Path(path).write_text("\n".join(out))
    return written


def pytest_configure(config):
    """Pytest plugin hook: start recording for the whole session."""
    activate()


def pytest_sessionfinish(session, exitstatus):
    """Pytest plugin hook: dump the report."""
    n = report(os.environ.get("BB_REPORT", "/tmp/bb_pytest_report.txt"))
    print(f"\nblockbuster distinct findings: {n}")


def BbApp():
    """A small app touching the common event paths."""
    import asyncio

    import reflex as rx

    class Item(rx.Model, table=True):
        __table_args__ = {"extend_existing": True}
        name: str

    class State(rx.State):
        count: int = 0
        loaded: str = ""
        log: list[str] = []
        bg_progress: int = 0
        upload_done: bool = False
        cookie_val: str = rx.Cookie("")
        ls_val: str = rx.LocalStorage("")
        db_rows: int = 0
        script_result: str = ""

        @rx.var
        def doubled(self) -> int:
            return self.count * 2

        @rx.event
        def on_load(self):
            self.loaded = "loaded"

        @rx.event
        def increment(self):
            self.count += 1

        @rx.event
        async def stream(self):
            for i in range(3):
                self.log.append(f"step {i}")
                yield
                await asyncio.sleep(0.01)

        @rx.event(background=True)
        async def bg_task(self):
            for i in range(3):
                await asyncio.sleep(0.01)
                async with self:
                    self.bg_progress = i + 1

        @rx.event
        async def handle_upload(self, files: list[rx.UploadFile]):
            for file in files:
                data = await file.read()
                if not file.name:
                    continue
                local = rx.get_upload_dir() / file.name
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(data)
            self.upload_done = True

        @rx.event
        def set_storage(self):
            self.cookie_val = "c1"
            self.ls_val = "l1"

        @rx.event
        def db_sync(self):
            with rx.session() as session:
                session.add(Item(name="x"))
                session.commit()
                self.db_rows = len(session.exec(Item.select()).all())

        @rx.event
        async def db_async(self):
            async with rx.asession() as session:
                session.add(Item(name="y"))
                await session.commit()
                self.db_rows = len((await session.exec(Item.select())).all())

        @rx.event
        def call_js(self):
            return rx.call_script("1+1", callback=State.set_script_result)

        @rx.event
        def set_script_result(self, value):
            self.script_result = str(value)

        @rx.event
        def go_other(self):
            return rx.redirect("/other")

        @rx.event
        def boom(self):
            msg = "boom"
            raise ValueError(msg)

    def index():
        return rx.vstack(
            rx.text(State.loaded, id="loaded"),
            rx.text(State.count, id="count"),
            rx.text(State.doubled, id="doubled"),
            rx.button("inc", id="inc", on_click=State.increment),
            rx.button("stream", id="stream", on_click=State.stream),
            rx.foreach(State.log, lambda s: rx.text(s)),
            rx.text(State.log.length(), id="loglen"),
            rx.button("bg", id="bg", on_click=State.bg_task),
            rx.text(State.bg_progress, id="bgp"),
            rx.upload.root(rx.button("select"), id="upload_root"),
            rx.button(
                "upload",
                id="upload",
                on_click=State.handle_upload(rx.upload_files(upload_id="upload_root")),
            ),
            rx.text(State.upload_done.to_string(), id="updone"),
            rx.button("storage", id="storage", on_click=State.set_storage),
            rx.text(State.cookie_val, id="cookie"),
            rx.text(State.ls_val, id="ls"),
            rx.button("dbsync", id="dbsync", on_click=State.db_sync),
            rx.button("dbasync", id="dbasync", on_click=State.db_async),
            rx.text(State.db_rows, id="dbrows"),
            rx.button("js", id="js", on_click=State.call_js),
            rx.text(State.script_result, id="jsres"),
            rx.button("boom", id="boom", on_click=State.boom),
            rx.button("other", id="other", on_click=State.go_other),
            rx.image(src="/_upload/hello.txt", id="img"),
        )

    def other():
        return rx.vstack(
            rx.text("other", id="otherpage"), rx.text(State.count, id="count2")
        )

    app = rx.App()
    app.add_page(index, on_load=State.on_load)
    app.add_page(other)


def _drive_dev(harness, page, expect, hello: Path) -> None:
    url = harness.frontend_url
    page.goto(url)
    expect(page.locator("#loaded")).to_have_text("loaded", timeout=60000)
    page.click("#inc")
    expect(page.locator("#count")).to_have_text("1")
    expect(page.locator("#doubled")).to_have_text("2")
    page.click("#stream")
    expect(page.locator("#loglen")).to_have_text("3")
    page.click("#bg")
    expect(page.locator("#bgp")).to_have_text("3")
    page.locator("#upload_root input[type=file]").set_input_files(str(hello))
    page.click("#upload")
    expect(page.locator("#updone")).to_have_text("true")
    page.click("#storage")
    expect(page.locator("#cookie")).to_have_text("c1")
    expect(page.locator("#ls")).to_have_text("l1")
    page.click("#dbsync")
    expect(page.locator("#dbrows")).to_have_text("1")
    page.click("#dbasync")
    expect(page.locator("#dbrows")).to_have_text("2")
    page.click("#js")
    expect(page.locator("#jsres")).to_have_text("2")
    page.click("#boom")
    time.sleep(1)
    host, port = harness._poll_for_servers().getsockname()[:2]  # pyright: ignore[reportPrivateUsage]
    base = f"http://{host}:{port}"
    print(
        "GET /_upload/hello.txt ->",
        urllib.request.urlopen(base + "/_upload/hello.txt").status,
    )
    print("GET /ping ->", urllib.request.urlopen(base + "/ping").status)
    page.click("#other")
    expect(page.locator("#otherpage")).to_have_text("other")
    expect(page.locator("#count2")).to_have_text("1")
    page.goto(url)  # re-hydrate an existing token
    expect(page.locator("#count")).to_have_text("1")
    page2 = page.context.browser.new_page()  # a second client with a fresh token
    page2.goto(url)
    expect(page2.locator("#loaded")).to_have_text("loaded")
    page2.click("#inc")
    expect(page2.locator("#count")).to_have_text("1")


def _drive_prod(harness, page, expect) -> None:
    url = harness.frontend_url
    page.goto(url)
    expect(page.locator("#loaded")).to_have_text("loaded", timeout=60000)
    page.click("#inc")
    expect(page.locator("#count")).to_have_text("1")
    page.click("#other")
    expect(page.locator("#otherpage")).to_have_text("other")
    for enc in ("gzip", "br", "identity"):
        req = urllib.request.Request(url + "/", headers={"Accept-Encoding": enc})
        r = urllib.request.urlopen(req)
        print("GET / enc", enc, "->", r.status, r.headers.get("Content-Encoding"))


def main() -> None:
    """Run the audit."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true", help="use AppHarnessProd")
    parser.add_argument("--root", type=Path, default=Path("/tmp/bb_audit"))
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    mode = os.environ.get("REFLEX_STATE_MANAGER_MODE", "memory")
    tag = "prod" if args.prod else mode
    report_path = args.report or args.root / f"report_{tag}.txt"
    args.root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("REFLEX_DB_URL", "sqlite:///reflex.db")
    os.environ.setdefault("REFLEX_ASYNC_DB_URL", "sqlite+aiosqlite:///reflex.db")
    Path("reflex.db").unlink(missing_ok=True)

    activate()
    from playwright.sync_api import expect, sync_playwright

    from reflex.testing import AppHarness, AppHarnessProd

    harness_cls = AppHarnessProd if args.prod else AppHarness
    with harness_cls.create(root=args.root / f"app_{tag}", app_source=BbApp) as harness:
        import reflex as rx

        rx.Model.create_all()
        hello = args.root / "hello.txt"
        hello.write_text("hello")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=os.environ.get("BB_CHROMIUM") or None
            )
            page = browser.new_page()
            if args.prod:
                _drive_prod(harness, page, expect)
            else:
                _drive_dev(harness, page, expect, hello)
            time.sleep(3)  # let debounced state writes and expiration tasks run
            browser.close()
        n = report(report_path)
        print(f"distinct findings: {n} -> {report_path}")


if __name__ == "__main__":
    sys.exit(main())
