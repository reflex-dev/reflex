"""Playwright driver with websocket frame + console + network capture.

Usage: python wsdrive.py <scenario> <base_url> <outdir>
"""

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:3180"
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "./out")
OUT.mkdir(parents=True, exist_ok=True)

console_log: list[str] = []
errors: list[str] = []
net: list[str] = []
frames: list[dict] = []


def attach(page, ctx_name="c1"):
    page.on(
        "console",
        lambda m: console_log.append(f"[{ctx_name}][{m.type}] {m.text}"),
    )
    page.on("pageerror", lambda e: errors.append(f"[{ctx_name}] PAGEERROR {e}"))
    page.on(
        "requestfailed",
        lambda r: net.append(f"[{ctx_name}] FAILED {r.method} {r.url} {r.failure}"),
    )

    def on_resp(r):
        if r.status >= 400:
            net.append(f"[{ctx_name}] HTTP {r.status} {r.url}")

    page.on("response", on_resp)

    def on_ws(ws):
        def rec(payload, direction):
            frames.append(
                {
                    "t": time.time(),
                    "ctx": ctx_name,
                    "dir": direction,
                    "payload": payload
                    if isinstance(payload, str)
                    else f"<bin {len(payload)}>",
                }
            )

        ws.on("framesent", lambda p: rec(p, "out"))
        ws.on("framereceived", lambda p: rec(p, "in"))

    page.on("websocket", on_ws)


def deltas(since=0.0, ctx=None):
    """Parse socket.io 'event' frames received into (name, payload) tuples."""
    out = []
    for f in frames:
        if f["dir"] != "in" or f["t"] < since:
            continue
        if ctx and f["ctx"] != ctx:
            continue
        m = re.match(r"^\d+(?:/[^,]*,)?(\[.*)$", f["payload"])
        if not m:
            continue
        try:
            parsed = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(parsed, list) and len(parsed) >= 2:
            out.append((f["t"], f["ctx"], parsed[0], parsed[1]))
    return out


def delta_keys(update):
    """Extract {state: [varnames]} from a StateUpdate payload."""
    d = update.get("delta") if isinstance(update, dict) else None
    if not isinstance(d, dict):
        return None
    return {k: sorted(v.keys()) for k, v in d.items()}


def dump(name):
    (OUT / f"{name}.console.txt").write_text("\n".join(console_log))
    (OUT / f"{name}.errors.txt").write_text("\n".join(errors))
    (OUT / f"{name}.net.txt").write_text("\n".join(net))
    (OUT / f"{name}.frames.jsonl").write_text(
        "\n".join(json.dumps(f) for f in frames)
    )


def log(*a):
    print(*a, flush=True)


def txt(page, sel):
    try:
        return page.locator(sel).inner_text(timeout=2000)
    except Exception as e:  # noqa: BLE001
        return f"<ERR {e}>"
