"""Drive diskapp: StateManagerDisk set_state / debounce / API-route persistence (#7159).

Usage: python drive_disk.py <frontend_url> <backend_url> <outdir> <label>
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
        return {"status": r.status_code, "text": r.text[:400]}


def step(name, **kw):
    kw["name"] = name
    R["steps"].append(kw)
    print(json.dumps(kw)[:900], flush=True)


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
    token = pg.inner_text("#token")
    R["token"] = token
    step("loaded", token=token, manager=api("/api/disk_read", token=token).get("manager"))

    # --- S1: websocket writes reach disk after the debounce window
    for _ in range(5):
        pg.click("#bump")
    pg.wait_for_function("() => document.querySelector('#counter').textContent === '5'", timeout=20000)
    immediate = api("/api/disk_read", token=token)
    time.sleep(3.0)
    settled = api("/api/disk_read", token=token)
    step("S1_ws_bump_x5", ui_counter=pg.inner_text("#counter"), immediate=immediate, after_3s=settled)

    # --- S2: two set_state calls with DIFFERENT instances in one debounce window
    #         -> the flushed value must be the SECOND one supplied (#7159 debounce-latest)
    ds = api("/api/double_set", token=token)
    right_after = api("/api/disk_read", token=token)
    time.sleep(3.5)
    ds_settled = api("/api/disk_read", token=token)
    step("S2_double_set_latest_wins", double_set=ds, right_after=right_after, after_3_5s=ds_settled)

    # --- S3: set_state with a fresh instance never obtained from get_state (#7159 persist)
    sf = api("/api/set_fresh", token=token, value="fresh-persisted")
    time.sleep(3.5)
    sf_disk = api("/api/disk_read", token=token)
    step("S3_set_fresh_persists", set_fresh=sf, after_3_5s=sf_disk)

    # --- S4: app.modify_state() from a custom Starlette route
    poke = api("/api/poke", token=token, value="via-modify-state")
    time.sleep(3.5)
    poke_disk = api("/api/disk_read", token=token)
    pg.reload(wait_until="load")
    pg.wait_for_selector("#value", timeout=90000)
    time.sleep(2.5)
    step(
        "S4_modify_state_from_api_route",
        poke=poke,
        disk=poke_disk,
        ui_value_after_reload=pg.inner_text("#value"),
        ui_api_writes_after_reload=pg.inner_text("#api-writes"),
        ui_counter_after_reload=pg.inner_text("#counter"),
    )
    pg.screenshot(path=str(OUT / f"{LABEL}_after_api_writes.png"))

    # --- S5: 20 rapid sets in ~0.8s, then read disk mid-debounce and after
    pg.click("#rapid")
    pg.wait_for_function("() => document.querySelector('#counter').textContent === '20'", timeout=30000)
    mid = api("/api/disk_read", token=token)
    time.sleep(3.0)
    after = api("/api/disk_read", token=token)
    step("S5_rapid_20_sets", ui=pg.inner_text("#counter"), mid_debounce=mid, after_3s=after)

    R["console"] = console
    R["page_errors"] = page_errors
    R["bad_responses"] = bad
    b.close()

(OUT / f"{LABEL}_result.json").write_text(json.dumps(R, indent=2))
print("TOKEN", R["token"])
print("CONSOLE ERR/WARN", json.dumps([c for c in console if c["type"] in ("error", "warning")])[:1500])
print("PAGE ERRORS", json.dumps(page_errors)[:1000])
print("BAD", json.dumps(bad)[:800])
