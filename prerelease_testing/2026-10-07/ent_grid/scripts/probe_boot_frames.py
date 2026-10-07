"""Record the full boot websocket frames of a page and report which substates each received frame carries.

Usage: probe_boot_frames.py <url> <expected_venv> <substring> [<substring> ...]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import assert_driver_and_server  # noqa: E402
from playwright.sync_api import sync_playwright

url, venv, *subs = sys.argv[1:]
info = assert_driver_and_server(venv)
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_page()
    recv, sent = [], []

    def on_ws(ws):
        ws.on("framereceived", lambda f: recv.append(f if isinstance(f, str) else f.decode("utf-8", "replace")))
        ws.on("framesent", lambda f: sent.append(f if isinstance(f, str) else f.decode("utf-8", "replace")))

    p.on("websocket", on_ws)
    p.goto(url, wait_until="networkidle")
    p.wait_for_timeout(2500)
    print("sent events:", [re.search(r'"name":"([^"]+)"', f).group(1) for f in sent if '"name"' in f])
    for i, f in enumerate(recv):
        if "delta" not in f:
            continue
        m = re.search(r"(\[.*\])$", f)
        keys = []
        try:
            payload = json.loads(m.group(1))[1]
            keys = list(payload.get("delta", {}).keys())
        except Exception:
            pass
        print(f"frame {i}: len={len(f)} delta substates={keys} " + " ".join(f"{s}={'yes' if s in f else 'no'}" for s in subs))
    b.close()
