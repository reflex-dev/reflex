"""Multi-client upload probe for the upload app (server with QA_UPLOAD_EXTRAS=1): #7357 territory.

Usage: probe_upload_multiclient.py <url> <outdir> <tag> <upload_dir> <fixtures_dir>
C and D upload different 3 MB files concurrently (throttled 1 MB/s each) -> both must land intact;
A starts a throttled 6 MB upload and its context is CLOSED mid-upload (client disconnect);
B clicks Ping every ~0.5 s the whole time and records how long each ping takes to show up.
"""
import hashlib
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, UPDIR, FIX = sys.argv[1:6]
UPDIR, FIX = Path(UPDIR), Path(FIX)
FIX.mkdir(parents=True, exist_ok=True)
run = Run(TAG, OUT)
run.expected_bad.append(lambda b: b["url"].endswith("/_upload") and "ERR_ABORTED" in str(b.get("failure")))
files = {}
for n, size in (("mc_c.bin", 3), ("mc_d.bin", 3), ("mc_a_6mb.bin", 6)):
    f = FIX / n
    f.write_bytes(os.urandom(size * 1024 * 1024))
    files[n] = f
    (UPDIR / n).unlink(missing_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731


def open_client(browser, label, kbps=None):
    ctx = browser.new_context(viewport={"width": 1000, "height": 900})
    page = ctx.new_page()
    run.attach(page, label)
    page.goto(URL, wait_until="load")
    page.get_by_role("button", name="Upload").wait_for(timeout=60000)
    page.wait_for_timeout(800)
    if kbps:
        cdp = ctx.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 10, "downloadThroughput": -1, "uploadThroughput": kbps * 1024})
    return ctx, page


def pings(page):
    t = page.locator("#qa-pings").inner_text()
    return int(t.split(":")[-1].strip())


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctxB, b = open_client(browser, "B-pinger")
    ctxC, c = open_client(browser, "C-upl", 1024)
    ctxD, d = open_client(browser, "D-upl", 1024)
    ctxA, a = open_client(browser, "A-upl-disconnect", 300)
    for pg, n in ((c, "mc_c.bin"), (d, "mc_d.bin"), (a, "mc_a_6mb.bin")):
        pg.locator("#upload1 input[type=file]").set_input_files([str(files[n])])
        pg.wait_for_timeout(200)
    t0 = time.time()
    for pg in (c, d, a):
        pg.get_by_role("button", name="Upload").click()
    lat = []
    closed_at = None
    base = pings(b)
    for i in range(24):
        n0 = pings(b)
        ts = time.time()
        b.locator("#qa-ping").click()
        while pings(b) == n0 and time.time() - ts < 10:
            b.wait_for_timeout(50)
        lat.append(round(time.time() - ts, 3))
        b.wait_for_timeout(400)
        if i == 5 and closed_at is None:
            ctxA.close()
            closed_at = round(time.time() - t0, 2)
    done = {n: (UPDIR / n).exists() and sha(UPDIR / n) == sha(files[n]) for n in ("mc_c.bin", "mc_d.bin")}
    deadline = time.time() + 20
    while not all(done.values()) and time.time() < deadline:
        b.wait_for_timeout(500)
        done = {n: (UPDIR / n).exists() and sha(UPDIR / n) == sha(files[n]) for n in ("mc_c.bin", "mc_d.bin")}
    run.notes.update({"ping_latencies_s": lat, "a_closed_at_s": closed_at, "uploads_done_at_s": round(time.time() - t0, 2)})
    run.check("two concurrent throttled uploads (C, D) both land intact", all(done.values()), done)
    run.check("disconnected uploader A leaves no partial file", not (UPDIR / "mc_a_6mb.bin").exists(), (UPDIR / "mc_a_6mb.bin").exists())
    run.check("pinger B: every ping processed (none lost) while others upload / disconnect", pings(b) == base + len(lat) and max(lat) < 3,
              f"pings {base}->{pings(b)} max_latency={max(lat)}s latencies={lat}")
    for pg, lab in ((c, "C"), (d, "D")):
        run.check(f"uploader {lab} UI returns to idle (no 'Uploading...')", pg.get_by_text("Uploading...").count() == 0,
                  pg.locator("[role=progressbar]").first.get_attribute("aria-valuenow"))
        pg.locator("#qa-ping").click()
        ok = False
        ts = time.time()
        while time.time() - ts < 5:
            if pings(pg) >= 1:
                ok = True
                break
            pg.wait_for_timeout(100)
        run.check(f"uploader {lab} can still send events after its upload", ok, pings(pg))
    browser.close()
sys.exit(run.finish())
