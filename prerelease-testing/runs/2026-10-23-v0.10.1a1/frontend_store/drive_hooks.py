"""Drive /hooks and /dyn/[pid] of fs_app: hook order (#7586), ComponentState, client_state,
memo with object props, call_script, clipboard, window_event_listener, custom code.

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_hooks.py --url http://localhost:3220 --out hooks.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=20000)
    ap.add_argument("--positioned", default="1")
    args = ap.parse_args()
    base = args.url.rstrip("/")
    checks: list[dict] = []
    console, errors = [], []

    def chk(name, got, want=None, pred=None):
        ok = (pred(got) if pred else got == want)
        checks.append({"name": name, "ok": bool(ok), "got": got, "want": want})
        print(f"[{'ok ' if ok else 'FAIL'}] {name}: got={got!r} want={want!r}")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        ctx = browser.new_context(viewport={"width": 1000, "height": 800})
        page = ctx.new_page()
        page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: errors.append(str(e)))
        T = args.timeout
        page.goto(f"{base}/hooks", wait_until="load", timeout=T)
        page.wait_for_function("() => document.querySelector('#hydrated')?.textContent === 'true'", timeout=T)

        def attr(sel, name):
            return page.get_attribute(sel, name)

        def text(sel):
            return page.text_content(sel)

        # hook order: derived hook values follow the state hook
        chk("reader.doubled initial", attr("#reader", "data-doubled"), "2")
        chk("reader.plain initial", attr("#reader", "data-plain"), "3")
        if args.positioned == "1":
            chk("reader-pos.pos initial", attr("#reader-pos", "data-pos"), "101")
        if args.positioned == "1":
            chk("reader-pos.pre initial", attr("#reader-pos", "data-pos-pre"), "100")
        chk("custom code ran once", page.evaluate("window.__custom_code_ran"), 1)
        page.click("#inc")
        page.wait_for_function("() => document.querySelector('#count')?.textContent === '2'", timeout=T)
        chk("reader.doubled after inc", attr("#reader", "data-doubled"), "4")
        chk("reader.plain after inc", attr("#reader", "data-plain"), "5")
        chk("window.__hr_plain", page.evaluate("window.__hr_plain"), 5)
        if args.positioned == "1":
            chk("reader-pos.pos after inc", attr("#reader-pos", "data-pos"), "102")
        if args.positioned == "1":
            chk("reader-pos.pre after inc", attr("#reader-pos", "data-pos-pre"), "101")

        # window_event_listener: resize + keydown
        page.set_viewport_size({"width": 777, "height": 555})
        page.wait_for_function("() => document.querySelector('#size')?.textContent === '777x555'", timeout=T)
        chk("resize", text("#size"), "777x555")
        page.keyboard.press("Escape")
        page.wait_for_function("() => document.querySelector('#key')?.textContent === 'Escape'", timeout=T)
        chk("keydown", text("#key"), "Escape")

        # clipboard: synthetic paste event with DataTransfer
        page.evaluate(
            """() => { const dt = new DataTransfer(); dt.setData('text/plain', 'pasted-text');
                      document.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true})); }"""
        )
        try:
            page.wait_for_function("() => (document.querySelector('#pasted')?.textContent || '').includes('pasted-text')", timeout=T)
        except Exception:  # noqa: BLE001
            pass
        chk("clipboard paste", text("#pasted"), None, pred=lambda v: "pasted-text" in (v or ""))

        # call_script with callback
        page.click("#call-script")
        page.wait_for_function("() => document.querySelector('#cs-val')?.textContent === '42'", timeout=T)
        chk("call_script callback", text("#cs-val"), "42")

        # ComponentState instances are independent
        page.click("#c1 .cs-inc")
        page.click("#c1 .cs-inc")
        page.click("#c2 .cs-inc")
        page.wait_for_function("() => document.querySelector('#c1 .cs-count')?.textContent === '2' && document.querySelector('#c2 .cs-count')?.textContent === '1'", timeout=T)
        chk("component state c1", text("#c1 .cs-count"), "2")
        chk("component state c2", text("#c2 .cs-count"), "1")

        # client_state global: set, late reader behind cond, push from backend, set back to default
        page.click("#cs-inc")
        page.click("#cs-inc")
        page.wait_for_function("() => document.querySelector('#cs-main')?.textContent === '2'", timeout=T)
        page.click("#toggle-reader")
        page.wait_for_selector("#cs-late", timeout=T)
        chk("client_state late reader sees 2", text("#cs-late"), "2")
        page.click("#cs-zero")
        page.wait_for_function("() => document.querySelector('#cs-main')?.textContent === '0'", timeout=T)
        chk("client_state late reader follows set back to default", text("#cs-late"), "0")
        page.click("#cs-push")
        page.wait_for_function("() => document.querySelector('#cs-main')?.textContent === '7'", timeout=T)
        chk("client_state push 7 (main)", text("#cs-main"), "7")
        chk("client_state push 7 (late)", text("#cs-late"), "7")
        page.fill("#cs-local-in", "typed")
        try:
            page.wait_for_function("() => document.querySelector('#cs-local')?.textContent === 'typed'", timeout=5000)
        except Exception:  # noqa: BLE001
            pass
        # Informational: a non-global client_state whose reader and writer land in different
        # auto-memoized components has separate useState hooks (same on 0.10.0?).
        checks.append({"name": "client_state local (info)", "ok": True, "got": text("#cs-local"), "want": "typed?"})
        print(f"[info] client_state local reader after typing: {text('#cs-local')!r}")

        # memo with object prop + internal state read
        r0 = int(attr(".memo-reader span[data-renders]", "data-renders"))
        chk("memo reader name", text(".mr-name"), "memo-item")
        chk("memo reader count", text(".mr-count"), "2")
        page.click("#unrelated")
        page.wait_for_function("() => document.querySelector('#unrelated-val')?.textContent === '1'", timeout=T)
        r1 = int(attr(".memo-reader span[data-renders]", "data-renders"))
        checks.append({"name": "memo renders after unrelated MemoHost var", "ok": True, "got": r1 - r0, "want": "info"})
        print(f"[info] memo re-renders after unrelated MemoHost update: {r1 - r0}")
        page.click("#inc")
        page.wait_for_function("() => document.querySelector('.mr-count')?.textContent === '3'", timeout=T)
        chk("memo reader sees HookState.count", text(".mr-count"), "3")
        page.click("#rename-thing")
        page.wait_for_function("() => document.querySelector('.mr-name')?.textContent === 'memo-item.'", timeout=T)
        chk("memo reader sees renamed object prop", text(".mr-name"), "memo-item.")

        # dynamic route reads root state + other substates through the shared store
        page.click("#to-hooks") if page.query_selector("#to-hooks") else None
        page.goto(f"{base}/dyn/42", wait_until="load", timeout=T)
        page.wait_for_function("() => document.querySelector('#hydrated')?.textContent === 'true'", timeout=T)
        chk("dyn pid", text("#pid"), "42")
        chk("dyn where", text("#where"), "path=/dyn/42")
        chk("dyn HookState.count persisted", text("#count"), "3")
        # client-side navigation back to the index: state read on another page
        page.click("#to-index")
        page.wait_for_selector("#op-append", timeout=T)
        page.click("#op-append")
        page.wait_for_function("() => document.querySelector('#step')?.textContent === '1'", timeout=T)
        chk("index after client nav", text("#step"), "1")
        page.wait_for_timeout(300)
        browser.close()

    noisy = [c for c in console if not any(b.search(c["text"]) for b in BENIGN)]
    report = {"checks": checks, "n_fail": sum(1 for c in checks if not c["ok"]), "console": noisy, "pageerrors": errors}
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(f"fails={report['n_fail']} console(non-benign)={len(noisy)} pageerrors={len(errors)}")
    for c in noisy[:20]:
        print("  console:", c["type"], c["text"][:300])
    for e in errors[:10]:
        print("  pageerror:", e[:300])
    return 0 if report["n_fail"] == 0 and not errors else 1


if __name__ == "__main__":
    sys.exit(main())
