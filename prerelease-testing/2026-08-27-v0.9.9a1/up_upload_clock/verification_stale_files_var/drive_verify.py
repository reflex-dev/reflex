"""Adversarial verification driver for the up_upload_clock claim:

'Files list never refreshes for an existing session (dependency-less cached @rx.var)'.

Usage: python drive_verify.py <frontend_url> <artifacts_dir> <upload_dir> <label>

Checks, in one Chromium browser:
  1. ctx A: initial render -> Files list empty (upload dir starts empty).
  2. ctx A: upload hello_verify.txt -> file lands on disk; Files list STILL empty
     after event round-trip (claim: cached var never recomputes).
  3. ctx A: reload page (sessionStorage token survives) -> list still empty.
  4. ctx A: upload second file (new event/delta in same session) -> list still empty.
  5. ctx B (fresh context = fresh token): list shows BOTH files.
  6. ctx A again: still empty (proves it is per-session caching, not timing).
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

frontend_url, artifacts_dir, upload_dir, label = sys.argv[1:5]
art = Path(artifacts_dir)
art.mkdir(parents=True, exist_ok=True)
updir = Path(upload_dir)

results = []
console_msgs = []
bad_responses = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS" if ok else "FAIL"), name, detail)


def file_links(page):
    """Return the texts of the file links in the Files: section."""
    return page.evaluate(
        """() => Array.from(document.querySelectorAll("a"))
            .filter(a => a.getAttribute("href") && a.getAttribute("href").includes("_upload"))
            .map(a => a.textContent)"""
    )


def wait_hydrated(page):
    page.wait_for_selector("text=Files:", timeout=30000)
    # wait for websocket state hydration: token present in sessionStorage
    page.wait_for_function(
        "() => { try { return !!window.sessionStorage.getItem('token'); } catch (e) { return false; } }",
        timeout=30000,
    )
    time.sleep(1.0)


srcdir = art / "srcfiles"
srcdir.mkdir(exist_ok=True)
f1 = srcdir / "verify_one.txt"
f1.write_text("verify one contents\n")
f2 = srcdir / "verify_two.txt"
f2.write_text("verify two contents\n")


def do_upload(page, path):
    page.set_input_files("input[type=file]", str(path))
    page.wait_for_selector(f"text={path.name}", timeout=10000)
    page.click("button:has-text('Upload')")
    deadline = time.time() + 20
    target = updir / path.name
    while time.time() < deadline and not target.exists():
        time.sleep(0.25)
    return target.exists()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx_a = browser.new_context()
    page = ctx_a.new_page()
    page.on(
        "console",
        lambda m: console_msgs.append({"type": m.type, "text": m.text}),
    )
    page.on(
        "response",
        lambda r: bad_responses.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )

    page.goto(frontend_url)
    wait_hydrated(page)
    token_a = page.evaluate("() => window.sessionStorage.getItem('token')")
    initial = file_links(page)
    page.screenshot(path=str(art / "01_initial.png"))
    check("initial_list_empty", initial == [], f"links={initial}")

    ok = do_upload(page, f1)
    check("upload1_on_disk", ok, str(updir / f1.name))
    time.sleep(3.0)  # generous window for any delta to arrive
    after1 = file_links(page)
    page.screenshot(path=str(art / "02_after_upload1.png"))
    check(
        "list_stale_after_upload_same_session",
        after1 == [],
        f"links={after1} (claim says stays empty)",
    )

    page.reload()
    wait_hydrated(page)
    token_a2 = page.evaluate("() => window.sessionStorage.getItem('token')")
    check("token_survives_reload", token_a == token_a2, f"{token_a} vs {token_a2}")
    after_reload = file_links(page)
    page.screenshot(path=str(art / "03_after_reload.png"))
    check(
        "list_stale_after_reload_same_token",
        after_reload == [],
        f"links={after_reload}",
    )

    ok = do_upload(page, f2)
    check("upload2_on_disk", ok, str(updir / f2.name))
    time.sleep(3.0)
    after2 = file_links(page)
    page.screenshot(path=str(art / "04_after_upload2.png"))
    check(
        "list_still_stale_after_second_event",
        after2 == [],
        f"links={after2}",
    )

    ctx_b = browser.new_context()
    page_b = ctx_b.new_page()
    page_b.goto(frontend_url)
    wait_hydrated(page_b)
    token_b = page_b.evaluate("() => window.sessionStorage.getItem('token')")
    fresh = file_links(page_b)
    page_b.screenshot(path=str(art / "05_fresh_context.png"))
    check("fresh_context_new_token", token_b != token_a, f"{token_b}")
    check(
        "fresh_context_sees_both_files",
        sorted(fresh) == sorted([f1.name, f2.name]),
        f"links={fresh}",
    )

    # back to ctx A: still stale even though another session saw the files
    again = file_links(page)
    page.screenshot(path=str(art / "06_ctx_a_still_stale.png"))
    check("ctx_a_still_stale_at_end", again == [], f"links={again}")

    ctx_b.close()
    ctx_a.close()
    browser.close()

(art / f"results_{label}.json").write_text(json.dumps(results, indent=2))
(art / f"console_{label}.json").write_text(json.dumps(console_msgs, indent=2))
(art / f"bad_responses_{label}.json").write_text(json.dumps(bad_responses, indent=2))
print("DONE", label, "failures:", sum(1 for r in results if not r["ok"]))
