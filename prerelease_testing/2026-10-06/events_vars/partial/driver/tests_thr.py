"""Throttle/debounce + supersedes, and temporal events while the backend is stopped."""

from __future__ import annotations

import os
import signal
import subprocess
import time

TEXT = "abcdefghijklmnopqrst"


def backend_pids() -> list[int]:
    port = os.environ["EV_BACKEND_PORT"]
    out = subprocess.run(["lsof", "-t", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
    return sorted({int(x) for x in out.split()})


def t_throttle_supersedes(h):
    ctx, page = h.new_context_page("thr")
    h.goto(page, "/throttle")
    page.click("#thr-clear")
    h.wait_text(page, "thr-received", "")
    page.click("#thr-input")
    t0 = time.time()
    page.keyboard.type(TEXT, delay=30)
    typing_s = round(time.time() - t0, 2)
    tl = h.timeline(page, ["thr-received", "thr-applied"], 2.5)
    rec = [x for x in h.text(page, "thr-received").split("|") if x]
    app = [x for x in h.text(page, "thr-applied").split("|") if x]
    ok = len(app) == 1 and rec and app[-1] == rec[-1]
    h.record("throttle.throttle200_supersedes_typing", "pass" if ok else "fail", {
        "typing_seconds": typing_s, "received": rec, "applied": app,
        "final_value_reached_backend": bool(rec) and rec[-1] == TEXT, "input_value": page.input_value("#thr-input"),
        "timeline": tl})
    if rec and rec[-1] != TEXT:
        h.record("throttle.leading_edge_drops_final_value", "anomaly", {
            "note": "throttle has no trailing call: the last keystrokes never reach the backend",
            "last_received": rec[-1], "input_value": page.input_value("#thr-input")})
    page.click("#deb-input")
    page.keyboard.type(TEXT, delay=30)
    page.wait_for_timeout(1500)
    deb = [x for x in h.text(page, "deb-received").split("|") if x]
    h.record("throttle.debounce300_supersedes_typing", "pass" if deb == [TEXT] else "fail", {"received": deb})
    ctx.close()


def t_temporal_sigstop(h):
    ctx, page = h.new_context_page("temporal")
    h.goto(page, "/throttle")
    page.click("#thr-clear")
    h.wait_text(page, "temp-hits", "")
    pids = backend_pids()
    for p in pids:
        os.kill(p, signal.SIGSTOP)
    try:
        for b in ("temp-t1", "temp-n1", "temp-t2", "temp-n2"):
            page.click(f"#{b}")
            page.wait_for_timeout(200)
        page.wait_for_timeout(2200)
    finally:
        for p in pids:
            os.kill(p, signal.SIGCONT)
    val = h.wait_pred(page, "temp-hits", lambda v: v.count(",") >= 3, 8)
    h.record("temporal.sigstop_3s_socket_still_open", "pass" if val == "T1,N1,T2,N2" else "fail",
             {"hits": val, "expected": "T1,N1,T2,N2", "stopped_pids": pids,
              "note": "socket.io client still reports connected during a 3s stop, so temporal events are sent and delivered late"})
    ctx.close()


def t_temporal_offline(h):
    """Force a real client-side disconnect (network offline), then send temporal + normal events."""
    ctx, page = h.new_context_page("temporal-offline")
    h.goto(page, "/throttle")
    page.click("#thr-clear")
    h.wait_text(page, "temp-hits", "")
    closes0 = sum(1 for f in h.ws_frames if f["dir"] == "close" and f["tag"] == "temporal-offline")
    ctx.set_offline(True)
    page.wait_for_timeout(1500)
    closes1 = sum(1 for f in h.ws_frames if f["dir"] == "close" and f["tag"] == "temporal-offline")
    for b in ("temp-t3", "temp-n3", "temp-t4", "temp-n4"):
        page.click(f"#{b}")
        page.wait_for_timeout(200)
    page.wait_for_timeout(500)
    ctx.set_offline(False)
    val = h.wait_pred(page, "temp-hits", lambda v: "N4" in v, 15)
    page.wait_for_timeout(1000)
    val = h.text(page, "temp-hits")
    h.record("temporal.offline_disconnect", "pass" if val == "N3,N4" else "fail",
             {"hits": val, "expected": "N3,N4 (temporal dropped, normal delivered in order after reconnect)",
              "ws_closed_while_offline": closes1 > closes0})
    ctx.close()


ALL = [t_throttle_supersedes, t_temporal_sigstop]
OFFLINE = [t_temporal_offline]


def t_temporal_disconnect(h):
    """Needs the server started with REFLEX_SOCKET_INTERVAL=1s REFLEX_SOCKET_TIMEOUT=1s so a
    SIGSTOP makes the client hit a ping timeout and really disconnect."""
    ctx, page = h.new_context_page("temporal-disc")
    h.goto(page, "/throttle")
    page.click("#thr-clear")
    h.wait_text(page, "temp-hits", "")
    pids = backend_pids()
    n_close0 = sum(1 for f in h.ws_frames if f["dir"] == "close" and f["tag"] == "temporal-disc")
    for p in pids:
        os.kill(p, signal.SIGSTOP)
    try:
        deadline = time.time() + 10
        while time.time() < deadline and sum(1 for f in h.ws_frames if f["dir"] == "close" and f["tag"] == "temporal-disc") == n_close0:
            page.wait_for_timeout(200)
        closed = sum(1 for f in h.ws_frames if f["dir"] == "close" and f["tag"] == "temporal-disc") > n_close0
        page.wait_for_timeout(300)
        for b in ("temp-t3", "temp-n3", "temp-t4", "temp-n4"):
            page.click(f"#{b}")
            page.wait_for_timeout(200)
        page.wait_for_timeout(800)
        shot = h.shot(page, "temporal_disconnected")
    finally:
        for p in pids:
            os.kill(p, signal.SIGCONT)
    val = h.wait_pred(page, "temp-hits", lambda v: "N4" in v, 20)
    page.wait_for_timeout(1500)
    val = h.text(page, "temp-hits")
    h.record("temporal.ping_timeout_disconnect", "pass" if val == "N3,N4" else "fail",
             {"hits": val, "expected": "N3,N4", "client_ws_closed_before_clicks": closed, "screenshot": shot})
    ctx.close()


DISCONNECT = [t_temporal_disconnect]
