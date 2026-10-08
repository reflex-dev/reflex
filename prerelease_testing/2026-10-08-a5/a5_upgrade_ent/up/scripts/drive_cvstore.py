"""Verifier driver for the cvstore app: client-storage values rewritten during hydration.

Usage: drive_cvstore.py <base_url> <out_dir> <label> [variant ...]
Variants: a b c d e_cookie e_session f g (default: all). Each variant runs in a fresh browser context.
Prints one SUMMARY line per variant and writes <out_dir>/<label>-<variant>.json (phases + ws frames).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

assert "/scratchpad/envs/driver/" in sys.executable, sys.executable

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
LABEL = sys.argv[3]
VARIANTS = sys.argv[4:] or ["a", "b", "c", "d", "e_cookie", "e_session", "f", "g"]
OUT.mkdir(parents=True, exist_ok=True)

# variant -> list of (kind, key) storage slots it uses
SLOTS = {
    "a": [("local", "v_a")],
    "b": [("local", "v_b")],
    "c": [("local", "v_c_ls"), ("cookie", "v_c_ck"), ("session", "v_c_ss")],
    "d": [("local", "v_d_ls"), ("cookie", "v_d_ck"), ("session", "v_d_ss")],
    "e_cookie": [("cookie", "v_e_ck")],
    "e_session": [("session", "v_e_ss")],
    "f": [("local", "v_f")],
    "g": [("local", "v_g")],
}
UI_IDS = {
    "c": ["ls", "ck", "ss", "loads", "seen"],
    "d": ["ls", "ck", "ss", "seen"],
}
CV_UI = ["var", "check", "seen", "noop_count"]


def storage(page: Page, slots) -> dict:
    return page.evaluate(
        """(slots) => {
            const ck = Object.fromEntries(document.cookie.split('; ').filter(Boolean).map(c => {
                const i = c.indexOf('='); return [c.slice(0, i), decodeURIComponent(c.slice(i + 1))]; }));
            const out = {};
            for (const [kind, key] of slots) {
                out[kind + ':' + key] = kind === 'local' ? localStorage.getItem(key)
                    : kind === 'session' ? sessionStorage.getItem(key) : (key in ck ? ck[key] : null);
            }
            return out;
        }""",
        slots,
    )


def set_bad(page: Page, slots) -> None:
    page.evaluate(
        """(slots) => { for (const [kind, key] of slots) {
            if (kind === 'local') localStorage.setItem(key, 'bad');
            else if (kind === 'session') sessionStorage.setItem(key, 'bad');
            else document.cookie = key + '=bad; path=/';
        } }""",
        slots,
    )


def ui(page: Page, ids) -> dict:
    out = {}
    for i in ids:
        loc = page.locator(f"#{i}")
        out[i] = loc.first.inner_text() if loc.count() else None
    return out


def wait_hydrated(page: Page, timeout: float = 25.0, settle_ms: int = 1500) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        loc = page.locator("#hyd")
        try:
            if loc.count() and loc.first.inner_text(timeout=500) == "hydrated":
                page.wait_for_timeout(settle_ms)
                return True
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(150)
    return False


def click_and_wait(page: Page, sel: str, ms: int = 1500) -> None:
    page.click(sel)
    page.wait_for_timeout(ms)


def run_variant(b, v: str) -> dict:
    slots = SLOTS[v]
    ids = UI_IDS.get(v, CV_UI + (["plain"] if v == "g" else []))
    ctx = b.new_context()
    page = ctx.new_page()
    rec = {"variant": v, "label": LABEL, "phases": [], "ws": [], "console": []}
    cur = {"phase": "initial"}
    t0 = time.time()

    def on_ws(ws):
        rec["ws"].append({"t": round(time.time() - t0, 3), "phase": cur["phase"], "dir": "open", "data": ws.url})
        ws.on("framesent", lambda p: rec["ws"].append({"t": round(time.time() - t0, 3), "phase": cur["phase"], "dir": "sent", "data": str(p)[:6000]}))
        ws.on("framereceived", lambda p: rec["ws"].append({"t": round(time.time() - t0, 3), "phase": cur["phase"], "dir": "recv", "data": str(p)[:6000]}))

    page.on("websocket", on_ws)
    page.on("console", lambda m: m.type in ("error", "warning") and rec["console"].append({"phase": cur["phase"], "type": m.type, "text": m.text[:500]}))
    page.on("pageerror", lambda e: rec["console"].append({"phase": cur["phase"], "type": "pageerror", "text": str(e)[:500]}))

    def snap(name: str, **extra):
        d = {"phase": name, "storage": storage(page, slots), "ui": ui(page, ids), "url": page.url, **extra}
        rec["phases"].append(d)
        return d

    page.goto(f"{BASE}/{v}", wait_until="networkidle")
    snap("initial", hydrated=wait_hydrated(page))
    set_bad(page, slots)
    snap("after-set-bad")
    cur["phase"] = "reload"
    page.reload(wait_until="networkidle")
    snap("reload", hydrated=wait_hydrated(page, settle_ms=2000))
    if v == "d":
        cur["phase"] = "fix-event"
        click_and_wait(page, "#fix")
        snap("fix-event")
    cur["phase"] = "probe"
    click_and_wait(page, "#probe")
    snap("probe")
    if "noop_count" in ids:
        cur["phase"] = "noop-event"
        click_and_wait(page, "#noop")
        snap("noop-event")
    cur["phase"] = "nav"
    page.click("#nav_home")
    page.wait_for_url(f"{BASE}/", timeout=10000)
    wait_hydrated(page, settle_ms=800)
    page.click(f"#nav_{v}")
    page.wait_for_url(f"{BASE}/{v}", timeout=10000)
    hyd = wait_hydrated(page, settle_ms=2000)
    cur["phase"] = "nav-probe"
    click_and_wait(page, "#probe")
    snap("after-client-nav", hydrated=hyd)
    cur["phase"] = "reload2"
    page.reload(wait_until="networkidle")
    hyd = wait_hydrated(page, settle_ms=2000)
    snap("reload2", hydrated=hyd)
    cur["phase"] = "reload2-probe"
    click_and_wait(page, "#probe")
    snap("reload2-probe")
    ctx.close()
    return rec


def short(d: dict) -> str:
    st = ",".join(f"{k.split(':')[0][0]}={val!r}" for k, val in d["storage"].items())
    u = " ".join(f"{k}={val!r}" for k, val in d["ui"].items() if val is not None)
    return f"[{st}] {u}"


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=True)
    try:
        for v in VARIANTS:
            try:
                rec = run_variant(b, v)
            except Exception as e:  # noqa: BLE001
                print(f"SUMMARY {LABEL} {v}: EXCEPTION {type(e).__name__}: {e}", flush=True)
                continue
            (OUT / f"{LABEL}-{v}.json").write_text(json.dumps(rec, indent=1))
            ph = {d["phase"]: d for d in rec["phases"]}
            print(f"SUMMARY {LABEL} {v}:", flush=True)
            for name in ["reload", "fix-event", "probe", "noop-event", "after-client-nav", "reload2", "reload2-probe"]:
                if name in ph:
                    print(f"   {name:17s} {short(ph[name])}", flush=True)
            errs = [c for c in rec["console"] if c["type"] in ("error", "pageerror")]
            if errs:
                print(f"   console errors: {errs[:3]}", flush=True)
    finally:
        b.close()
