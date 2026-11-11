"""#7721: streamed upload updates + progress with a big file. Usage: upload_stream.py <fe>"""
import sys, time, json
from playwright.sync_api import sync_playwright
fe = sys.argv[1].rstrip("/")
out = {"errors": [], "stream_samples": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("pageerror", lambda e: out["errors"].append(str(e)[:200]))
    pg.goto(fe + "/upload"); pg.wait_for_selector("#page-upload"); time.sleep(2)
    big = b"x" * (20 * 1024 * 1024)
    pg.locator("#up1 input[type=file]").set_input_files([{"name": "big.bin", "mimeType": "application/octet-stream", "buffer": big}])
    time.sleep(0.5)
    pg.click("#b-up-stream")
    t0 = time.time()
    while time.time() - t0 < 30:
        s = pg.inner_text("#stream")
        if not out["stream_samples"] or out["stream_samples"][-1] != s:
            out["stream_samples"].append(s)
        if "7 /" in s:
            break
        time.sleep(0.02)
    time.sleep(2)
    out["final"] = pg.inner_text("#stream")
    out["progress"] = pg.inner_text("#progress")[:400]
    # repeat a second time without reset to see the list grows consistently
    pg.click("#b-up-stream"); time.sleep(6)
    out["final2"] = pg.inner_text("#stream")
    b.close()
print(json.dumps(out, indent=1))
