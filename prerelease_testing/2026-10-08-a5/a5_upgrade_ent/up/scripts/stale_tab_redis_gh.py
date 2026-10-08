"""github-stats tab kept open across a 0.9.12 -> 0.10.0a1 backend swap sharing ONE Redis.

Usage: stale_tab_redis_gh.py <url> <outdir> <tag> <ctldir>
Phase A (old server): add alice + bob, type 'dave' into the username input WITHOUT
submitting (State.username lives only in the backend state = Redis pickle, not in
LocalStorage). Writes <ctldir>/ready, waits for `down` then `up` (operator files).
Phase C: what the stale tab shows / sends after reconnecting to the new backend.
Phase D: add 'carol' from the stale tab (event processed against the state the new
backend unpickled from Redis). Phase E: manual reload (new JS, same sessionStorage
token) -> hydrate_and_load from the Redis state. Phase F: second context with the
old token injected into sessionStorage.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, CTL = sys.argv[1:5]
CTL = Path(CTL)
CTL.mkdir(parents=True, exist_ok=True)
run = Run(TAG, OUT)


def chips(page):
    return page.evaluate("""() => Array.from(document.querySelectorAll('button'))
        .filter(b => b.textContent === 'X').map(b => b.parentElement.textContent.replace(/X$/, ''))""")


def logins(page):
    try:
        return sorted(u["login"] for u in json.loads(page.locator("textarea").first.input_value() or "[]"))
    except Exception:  # noqa: BLE001
        return None


def username(page):
    return page.locator("#username").input_value()


def wait_file(page, name, timeout=3600):
    end = time.time() + timeout
    while time.time() < end:
        if (CTL / name).exists():
            return True
        page.wait_for_timeout(500)
    return False


def snap(page, label):
    info = {"marker": page.evaluate("() => window.__qa_marker || null"), "chips": chips(page),
            "logins": logins(page), "username_input": username(page),
            "token": page.evaluate("() => window.sessionStorage.getItem('token')"),
            "toasts": page.locator("[data-sonner-toast]").all_inner_texts()}
    run.notes[label] = info
    run.shot(page, label)
    print(label, info, flush=True)
    return info


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context()
    page = ctx.new_page()
    run.attach(page)
    page.goto(URL, wait_until="load")
    page.get_by_role("heading", name="Github Stats").wait_for(timeout=60000)
    page.wait_for_timeout(1500)
    page.evaluate("() => { window.__qa_marker = 'old-tab'; }")
    for u in ("alice", "bob"):
        page.locator("#username").fill(u)
        page.get_by_role("button", name="Get Stats").click()
        wait_for(lambda: u in (logins(page) or []), 15)
    page.locator("#username").fill("dave")
    page.wait_for_timeout(1500)
    a = snap(page, "A_old_server")
    run.check("A: old server state (alice,bob + username input 'dave')",
              a["logins"] == ["alice", "bob"] and a["username_input"] == "dave", a)
    (CTL / "token").write_text(a["token"] or "")
    (CTL / "ready").write_text("1")
    wait_file(page, "down")
    page.wait_for_timeout(5000)
    snap(page, "B_down")
    wait_file(page, "up")
    run.notes["t_up"] = run._t()
    page.wait_for_timeout(15000)
    c = snap(page, "C_after_up")
    run.check("C: stale tab still shows pre-upgrade state", c["logins"] == ["alice", "bob"], c)
    page.locator("#username").fill("carol")
    page.get_by_role("button", name="Get Stats").click()
    ok = wait_for(lambda: logins(page) == ["alice", "bob", "carol"], 15)
    d = snap(page, "D_stale_add_carol")
    run.check("D: stale (0.9.12 JS) tab adds carol through new backend; old Redis state kept",
              bool(ok) and d["chips"] == ["alice", "bob", "carol"], d)
    page.locator("#username").fill("erin")
    page.wait_for_timeout(1500)
    page.reload(wait_until="load")
    page.get_by_role("heading", name="Github Stats").wait_for(timeout=30000)
    page.wait_for_timeout(3000)
    e = snap(page, "E_after_reload")
    run.check("E: after reload (new JS, same token): users + stats restored", e["logins"] == ["alice", "bob", "carol"]
              and e["chips"] == ["alice", "bob", "carol"], e)
    run.check("E: backend-only var State.username ('erin') restored from Redis after reload",
              e["username_input"] == "erin", e["username_input"])
    token = e["token"]
    # close the original tab first: a token still held by a live socket is treated as a
    # duplicated tab and the newcomer is issued a fresh token.
    page.close()
    time.sleep(2)
    ctx2 = browser.new_context()
    ctx2.add_init_script(f"window.sessionStorage.setItem('token', {json.dumps(token)});")
    p2 = ctx2.new_page()
    run.attach(p2, "ctx2")
    p2.goto(URL, wait_until="load")
    p2.get_by_role("heading", name="Github Stats").wait_for(timeout=30000)
    p2.wait_for_timeout(3000)
    f = {"username_input": username(p2), "chips": chips(p2), "logins": logins(p2),
         "token": p2.evaluate("() => window.sessionStorage.getItem('token')")}
    run.notes["F_injected_token"] = f
    run.check("F: second context with injected token sees Redis state (username input)",
              f["username_input"] == "erin", f)
    ctx2.close()
    browser.close()
(CTL / "done").write_text("1")
sys.exit(run.finish())
