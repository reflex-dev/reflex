"""Independent verification: does the tickets demo dispatch any event?

Usage: verify_tickets.py <base_url> <out.json> <shots_dir>
Loads the page, records console + websocket frames, clicks Seed, then New Ticket,
and reports row/badge counts plus every delta's substate keys.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE, OUT, SHOTS = sys.argv[1], sys.argv[2], sys.argv[3]
Path(SHOTS).mkdir(parents=True, exist_ok=True)
sent, recv, console, pageerrors = [], [], [], []
rep = {}

with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 1400, "height": 1000})
    page = ctx.new_page()
    page.on("console", lambda m: console.append([m.type, m.text[:400]]))
    page.on("pageerror", lambda e: pageerrors.append(str(e)[:400]))
    page.on("websocket", lambda ws: (
        ws.on("framesent", lambda pl: sent.append(str(pl)[:2000])),
        ws.on("framereceived", lambda pl: recv.append(str(pl)[:4000])),
    ))
    page.goto(BASE, wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(6000)
    page.screenshot(path=f"{SHOTS}/01_loaded.png")
    rep["after_load"] = {"sent": len(sent), "recv": len(recv)}
    rep["body_head"] = page.inner_text("body")[:400]
    rep["rows_before"] = page.locator("tbody tr").count()
    rep["badges_before"] = page.locator(".rt-Badge").all_inner_texts()[:4]
    rep["dispatch_keys"] = page.evaluate(
        "() => { try { return Object.keys(window.__reflex_dispatch || {}); } catch(e) { return ['n/a']; } }"
    )

    def burst(label, action):
        n_s, n_r = len(sent), len(recv)
        try:
            action()
            err = None
        except Exception as e:  # noqa: BLE001
            err = str(e)[:300]
        page.wait_for_timeout(3000)
        page.screenshot(path=f"{SHOTS}/{label}.png")
        rep[label] = {
            "error": err,
            "new_sent": sent[n_s:],
            "new_recv_count": len(recv) - n_r,
            "rows": page.locator("tbody tr").count(),
            "badges": page.locator(".rt-Badge").all_inner_texts()[:4],
            "dialog_open": page.locator("[role=dialog]").count(),
        }

    burst("02_click_seed", lambda: page.click("text=Seed"))
    burst("03_click_new_ticket", lambda: page.click("text=New Ticket"))
    burst("04_type_search", lambda: page.fill("input[placeholder*='earch' i]", "vpn"))
    rep["console"] = console
    rep["pageerrors"] = pageerrors
    rep["recv_delta_substates"] = []
    for f in recv:
        if '"delta"' in f or "delta" in f:
            keys = []
            for k in (
                "reflex___state____state",
                "generic_oidc_auth_state",
                "is_iframed_state",
                "ticket_state",
                "on_load_internal_state",
                "update_vars_internal_state",
                "frontend_event_exception_state",
                "shared_state_base_internal",
            ):
                if k in f:
                    keys.append(k)
            rep["recv_delta_substates"].append(keys)
    rep["sent_all"] = sent
    rep["recv_all"] = recv
    Path(OUT).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("sent_all", "recv_all")}, indent=1)[:6000])
    br.close()
