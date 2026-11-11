"""Hot-reload probe for the shared store (#7441) and the schema-mismatch warning (#7553) in dev.

Opens /hooks, increments the counter, then appends a NEW substate used by the page to the
app source, waits for the new element, records console warnings / page errors, then reverts.

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_hmr.py --url http://localhost:3220 --app fs_app/fs_app/fs_app.py --out hmr.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]

NEW_STATE = '''

class HmrState(rx.State):
    label: str = "hmr-v1"
    n: int = 0

    @rx.event
    def bump(self):
        self.n += 1


def hooks_page_hmr() -> rx.Component:
    return rx.el.div(
        hooks_page(),
        rx.el.span(HmrState.label, id="hmr-label"),
        rx.el.span(HmrState.n, id="hmr-n"),
        rx.el.button("hmr", id="hmr-bump", on_click=HmrState.bump),
    )


app.add_page(hooks_page_hmr, route="/hooks", title="hooks-hmr")
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--app", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=60000)
    args = ap.parse_args()
    app_path = Path(args.app)
    original = app_path.read_text()
    base = args.url.rstrip("/")
    console, errors = [], []
    checks = []

    def chk(name, got, want):
        ok = got == want
        checks.append({"name": name, "ok": ok, "got": got, "want": want})
        print(f"[{'ok ' if ok else 'FAIL'}] {name}: got={got!r} want={want!r}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_context().new_page()
        page.on("console", lambda m: console.append({"type": m.type, "text": m.text, "t": time.time()}))
        page.on("pageerror", lambda e: errors.append(str(e)))
        T = args.timeout
        page.goto(f"{base}/hooks", wait_until="load", timeout=T)
        page.wait_for_function("() => document.querySelector('#hydrated')?.textContent === 'true'", timeout=T)
        page.click("#inc")
        page.wait_for_function("() => document.querySelector('#count')?.textContent === '2'", timeout=T)
        page.fill("#cs-local-in", "kept?")
        n_console_before = len(console)
        try:
            # 1) add a brand-new substate read by the page
            t0 = time.time()
            app_path.write_text(original.replace('app.add_page(hooks_page, route="/hooks")\n', "") + NEW_STATE)
            try:
                page.wait_for_function("() => document.querySelector('#hmr-label')?.textContent === 'hmr-v1'", timeout=T)
            except Exception as e:  # noqa: BLE001
                print("[info] wait for new element failed:", str(e)[:120])
                print("[info] body:", (page.evaluate("document.body.innerText") or "")[:400].replace("\n", " | "))
            chk("new substate rendered after hot reload", page.text_content("#hmr-label") if page.query_selector("#hmr-label") else None, "hmr-v1")
            print(f"[info] new substate visible after {time.time() - t0:.1f}s")
            page.wait_for_timeout(1500)
            page.wait_for_function("() => document.querySelector('#hydrated')?.textContent === 'true'", timeout=T)
            if page.query_selector("#hmr-bump"):
                page.click("#hmr-bump")
                page.wait_for_function("() => document.querySelector('#hmr-n')?.textContent === '1'", timeout=T)
                chk("event on new substate works", page.text_content("#hmr-n"), "1")
            page.click("#inc")
            page.wait_for_timeout(800)
            chk("old substate still updates", page.text_content("#count"), str(int(page.text_content("#count"))))
            c1 = int(page.text_content("#c1 .cs-count"))
            page.click("#c1 .cs-inc")
            try:
                page.wait_for_function(f"() => document.querySelector('#c1 .cs-count')?.textContent === '{c1 + 1}'", timeout=8000)
            except Exception:  # noqa: BLE001
                pass
            chk("ComponentState instance still works after hot reload", page.text_content("#c1 .cs-count"), str(c1 + 1))
            chk("no full reload (uncontrolled input kept)", page.input_value("#cs-local-in"), "kept?")
            # 2) change the default of the new state (default-only change)
            t1 = time.time()
            app_path.write_text(app_path.read_text().replace('label: str = "hmr-v1"', 'label: str = "hmr-v2"'))
            try:
                page.wait_for_function("() => document.querySelector('#hmr-label')?.textContent === 'hmr-v2'", timeout=T)
            except Exception:  # noqa: BLE001
                pass
            print(f"[info] default change visible after {time.time() - t1:.1f}s -> {page.text_content('#hmr-label')!r}")
            page.wait_for_timeout(1500)
        finally:
            app_path.write_text(original)
        try:
            page.wait_for_function("() => !document.querySelector('#hmr-label')", timeout=T)
            print("[ok ] revert: new element gone")
        except Exception:  # noqa: BLE001
            print("[FAIL] revert: element still present")
        page.wait_for_timeout(2000)
        page.click("#inc")
        page.wait_for_timeout(800)
        chk("after revert the page still handles events", page.text_content("#count").isdigit(), True)
        browser.close()

    noisy = [c for c in console[n_console_before:] if not any(b.search(c["text"]) for b in BENIGN)]
    mismatch = [c for c in noisy if "state schema" in c["text"] or "another version" in c["text"]]
    report = {"checks": checks, "console_during_hmr": noisy, "mismatch_warnings": mismatch, "pageerrors": errors}
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"fails={sum(1 for c in checks if not c['ok'])} console(non-benign during hmr)={len(noisy)} mismatch_warnings={len(mismatch)} pageerrors={len(errors)}")
    for c in noisy[:40]:
        print("  console:", c["type"], c["text"][:240])
    for e in errors[:10]:
        print("  pageerror:", e[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
