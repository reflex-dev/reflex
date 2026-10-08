"""reverify_hydration: user chooses a theme (event) -> storage must persist it.
Usage: mini_choose.py URL STATE_OUT"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hydcommon import CHROMIUM, storage_dump, text, wait_hydrated  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

assert "/envs/driver/" in sys.executable, sys.executable
url, state_out = sys.argv[1], sys.argv[2]
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = b.new_context()
    p = ctx.new_page()
    p.goto(url)
    hyd = wait_hydrated(p)
    p.click("#choose-blue")
    p.wait_for_timeout(1000)
    st = storage_dump(p)
    print(json.dumps({"hydrated": hyd, "theme_shown": text(p, "#theme"), "consent_shown": text(p, "#consent"),
                      "localStorage": {k: v for k, v in st["local"].items() if k.startswith("mini")},
                      "cookies": st["cookie"]}))
    ctx.storage_state(path=state_out)
    b.close()
