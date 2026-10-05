"""StateManagerDisk (#7159) end-to-end: persistence, debounce-latest, API-route writes.

Usage: python drive_disk2.py <frontend_url> <backend_url> <outdir> <label>
Leaves the browser closed; prints a JSON step log and writes <label>_result.json.
"""

import json
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

FE, BE, OUT, LABEL = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/"), Path(sys.argv[3]), sys.argv[4]
OUT.mkdir(parents=True, exist_ok=True)
R = {"label": LABEL, "steps": []}
console, page_errors, bad = [], [], []
HC = httpx.Client(timeout=20.0, trust_env=False)


def api(path, **params):
    r = HC.get(f"{BE}{path}", params=params)
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "text": r.text[:300]}


def step(name, **kw):
    kw = {"name": name, **kw}
    R["steps"].append(kw)
    print(json.dumps(kw)[:1400], flush=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.on("console", lambda m: console.append({"type": m.type, "text": m.text[:400]}))
    pg.on("pageerror", lambda e: page_errors.append(str(e)[:600]))
    pg.on("response", lambda r: bad.append({"url": r.url, "status": r.status}) if r.status >= 400 else None)
    pg.goto(FE + "/", wait_until="load")
    pg.wait_for_selector("#token", timeout=90000)
    pg.wait_for_function("() => document.querySelector('#token').textContent.length > 8", timeout=60000)
    tok = pg.inner_text("#token")
    R["token"] = tok
    step("D0_loaded", token=tok, ui_counter=pg.inner_text("#counter"), ui_value=pg.inner_text("#value"),
         dump=api("/api/dump", token=tok))

    # D1: websocket writes land on disk after the 2s debounce
    for _ in range(5):
        pg.click("#bump")
    pg.wait_for_function("() => document.querySelector('#counter').textContent !== '0'", timeout=20000)
    ui = pg.inner_text("#counter")
    mid = api("/api/disk_read", token=tok)
    time.sleep(3.0)
    step("D1_ws_bump_x5", ui_counter=ui, mid_debounce=mid, after_3s=api("/api/disk_read", token=tok),
         dump=api("/api/dump", token=tok))

    # D2: two set_state calls, DIFFERENT instances, inside one debounce window.
    #     #7159 says the flushed write must carry the SECOND value.
    ds = api("/api/double_set", token=tok)
    ra = api("/api/disk_read", token=tok)
    time.sleep(3.5)
    step("D2_debounce_latest_wins", double_set=ds, right_after=ra, after_3_5s=api("/api/disk_read", token=tok))

    # D3: set_state with an instance never obtained from get_state (#7159 persistence)
    sf = api("/api/set_fresh", token=tok, value="fresh-persisted")
    time.sleep(3.5)
    step("D3_set_fresh_persists", set_fresh=sf, after_3_5s=api("/api/disk_read", token=tok))

    # D4: app.modify_state(BaseStateToken) from a custom Starlette route
    poke = api("/api/poke", token=tok, value="via-modify-state")
    time.sleep(0.8)
    ui_live = pg.inner_text("#value")
    time.sleep(3.0)
    disk = api("/api/disk_read", token=tok)
    pg.reload(wait_until="load")
    pg.wait_for_selector("#value", timeout=90000)
    time.sleep(2.5)
    step("D4_modify_state_api_route", poke=poke, ui_value_pushed_live=ui_live, disk=disk,
         ui_value_after_reload=pg.inner_text("#value"),
         ui_api_writes_after_reload=pg.inner_text("#api-writes"),
         ui_counter_after_reload=pg.inner_text("#counter"))
    pg.screenshot(path=str(OUT / f"{LABEL}_after_api_writes.png"))

    # D5: the deprecated bare-client-token form of app.modify_state
    step("D5_legacy_bare_token_modify_state", response=api("/api/poke", token=tok, value="legacy", legacy="1"))

    # D6: 20 rapid sets in <1s -> last value must survive the debounce
    tok2 = pg.inner_text("#token")
    pg.click("#rapid")
    pg.wait_for_function("() => document.querySelector('#counter').textContent === '20'", timeout=30000)
    mid = api("/api/disk_read", token=tok2)
    time.sleep(3.0)
    step("D6_rapid_20_sets", token=tok2, ui=pg.inner_text("#counter"), mid_debounce=mid,
         after_3s=api("/api/disk_read", token=tok2))

    # D7: hot reload (touch the app module) must not lose state under the disk manager
    Path(sys.argv[5]).touch() if len(sys.argv) > 5 else None
    if len(sys.argv) > 5:
        time.sleep(12.0)
        pg.reload(wait_until="load")
        pg.wait_for_selector("#value", timeout=90000)
        time.sleep(3.0)
        step("D7_survives_hot_reload", token_after=pg.inner_text("#token"),
             ui_counter=pg.inner_text("#counter"), ui_value=pg.inner_text("#value"),
             dump=api("/api/dump", token=tok2))

    # D8: 20 sets in <1s then a distinct final value, all inside one debounce window;
    #     the driver SIGTERMs the server right after this step returns.
    pg.click("#rapid")
    pg.wait_for_function("() => document.querySelector('#counter').textContent === '20'", timeout=30000)
    pg.fill("#value-input", "LAST-VALUE-BEFORE-KILL")
    pg.wait_for_function("() => document.querySelector('#value').textContent === 'LAST-VALUE-BEFORE-KILL'", timeout=20000)
    step("D8_primed_for_kill", token=tok2, ui_counter=pg.inner_text("#counter"), ui_value=pg.inner_text("#value"),
         queue=api("/api/dump", token=tok2).get("queue_keys"),
         disk_now=api("/api/disk_read", token=tok2))
    R["kill_token"] = tok2

    R["console"] = console
    R["page_errors"] = page_errors
    R["bad_responses"] = bad
    b.close()

(OUT / f"{LABEL}_result.json").write_text(json.dumps(R, indent=2))
print("KILL_TOKEN", R["kill_token"])
print("CONSOLE ERR/WARN", json.dumps([c for c in console if c["type"] in ("error", "warning")])[:1200])
print("PAGE ERRORS", json.dumps(page_errors)[:800])
print("BAD", json.dumps(bad)[:600])
