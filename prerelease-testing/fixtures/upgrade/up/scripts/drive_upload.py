"""Drive the reflex-examples `upload` app (server started with QA_UPLOAD_EXTRAS=1).

Usage: drive_upload.py <url> <outdir> <tag> <upload_dir_on_disk> <fixtures_dir>
Flows: selected-files display (rx.selected_files), re-select replaces, Clear (rx.clear_selected_files),
drag & drop onto the dropzone (react-dropzone), upload of hostile names ("../x.txt", "..\\..\\win.txt",
"/abs/root.txt", unicode + spaces, "sub/dir/nested.txt"), 12 MB binary with sha256 roundtrip,
throttled 6 MB upload: progress bar + "Uploading..." + Ping events DURING the upload (#7357) + cancel,
upload after cancel, Files list (dependency-less cached var: stale for the session = app quirk) in the
same session / after reload / fresh context, served bytes via the rendered /_upload links.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, UPDIR, FIX = sys.argv[1:6]
UPDIR, FIX = Path(UPDIR), Path(FIX)
FIX.mkdir(parents=True, exist_ok=True)
run = Run(TAG, OUT)
# the cancel flow aborts the /_upload POST on purpose
run.expected_bad.append(lambda b: b["url"].endswith("/_upload") and "ERR_ABORTED" in str(b.get("failure")))

hello = FIX / "hello.txt"; hello.write_text("hello upload " + TAG)
uni_name = "héllo wörld 测试 файл (1).txt"
uni = FIX / uni_name; uni.write_text("unicode name " + TAG)
big = FIX / "big12mb.bin"
if not big.exists() or big.stat().st_size != 12 * 1024 * 1024:
    big.write_bytes(os.urandom(12 * 1024 * 1024))
slow = FIX / "slow6mb.bin"
if not slow.exists():
    slow.write_bytes(os.urandom(6 * 1024 * 1024))
after = FIX / "after cancel.txt"; after.write_text("after cancel " + TAG)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
HOSTILE = [("../x_traversal.txt", "x_traversal.txt"), ("..\\..\\win_traversal.txt", "win_traversal.txt"),
           ("/abs/root_abs.txt", "root_abs.txt"), ("sub/dir/nested.txt", "nested.txt")]  # app writes UploadFile.name = basename


def pump(page, cond, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        page.wait_for_timeout(200)
    return bool(cond())


def selected(page):
    """texts rendered by rx.foreach(rx.selected_files(...)) inside the dropzone."""
    return page.evaluate("""() => {
        const root = document.getElementById('upload1');
        if (!root) return null;
        return [...root.querySelectorAll('p')].map(p => p.innerText.trim())
            .filter(t => t && !t.startsWith('Drag and drop'));
    }""")


def listed(page):
    return page.evaluate("""() => {
        const h = [...document.querySelectorAll('h1,h2,h3')].find(e => e.innerText.trim() === 'Files:');
        if (!h) return null;
        return [...document.querySelectorAll('a')].filter(a => (a.getAttribute('href') || '').includes('/_upload/'))
            .map(a => [a.innerText.trim(), a.getAttribute('href')]);
    }""")


def on_disk():
    return sorted(str(p.relative_to(UPDIR)) for p in UPDIR.rglob("*") if p.is_file()) if UPDIR.exists() else []


def pings(page):
    t = page.locator("#qa-pings").inner_text() if page.locator("#qa-pings").count() else ""
    return int(t.split(":")[-1].strip() or -1) if t else None


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1100, "height": 1000})
    page = ctx.new_page()
    run.attach(page, "main")
    page.goto(URL, wait_until="load")
    page.get_by_role("button", name="Upload").wait_for(timeout=60000)
    pump(page, lambda: selected(page) == ["No files selected"], 15)
    disk0 = on_disk()
    run.notes["disk_at_start"] = disk0
    run.check("initial: 'No files selected', QA extras rendered", selected(page) == ["No files selected"] and page.locator("#qa-clear").count() == 1,
              f"selected={selected(page)} disk={disk0}")
    run.notes["files_list_initial"] = listed(page)
    run.shot(page, "01_initial")
    inp = page.locator("#upload1 input[type=file]")
    inp.set_input_files([str(hello), str(uni)])
    ok = pump(page, lambda: selected(page) == ["hello.txt", uni_name], 8)
    run.check("select 2 files -> names rendered (rx.selected_files)", ok, selected(page))
    inp.set_input_files([str(after)])
    ok = pump(page, lambda: selected(page) == ["after cancel.txt"], 8)
    run.check("re-select replaces the selection", ok, selected(page))
    page.locator("#qa-clear").click()
    ok = pump(page, lambda: selected(page) == ["No files selected"], 8)
    run.check("Clear (rx.clear_selected_files) empties the selection", ok, selected(page))
    # drag & drop (react-dropzone onDrop via a synthetic DataTransfer)
    page.evaluate("""(tag) => {
        const dt = new DataTransfer();
        dt.items.add(new File(['dropped one ' + tag], 'dropped_one.txt', {type: 'text/plain'}));
        dt.items.add(new File(['dropped two ' + tag], 'dropped two.txt', {type: 'text/plain'}));
        const el = document.getElementById('upload1');
        for (const t of ['dragenter', 'dragover', 'drop'])
            el.dispatchEvent(new DragEvent(t, {bubbles: true, cancelable: true, dataTransfer: dt}));
    }""", TAG)
    ok = pump(page, lambda: selected(page) == ["dropped_one.txt", "dropped two.txt"], 8)
    run.check("drag & drop onto the dropzone selects files", ok, selected(page))
    run.shot(page, "02_dropped")
    page.get_by_role("button", name="Upload").click()
    rd = lambda n: (UPDIR / n).read_text() if (UPDIR / n).exists() else None  # noqa: E731
    ok = pump(page, lambda: rd("dropped_one.txt") == f"dropped one {TAG}" and rd("dropped two.txt") == f"dropped two {TAG}", 15)
    run.check("dropped files upload and land on disk (this run's bytes)", ok, on_disk())
    obs_sel_after_upload = selected(page)
    run.notes["selected_after_upload"] = obs_sel_after_upload
    # hostile names via buffer payloads (names are passed through untouched by Playwright)
    payloads = [{"name": n, "mimeType": "text/plain", "buffer": f"hostile {n} {TAG}".encode()} for n, _ in HOSTILE]
    payloads.append({"name": uni_name, "mimeType": "text/plain", "buffer": uni.read_bytes()})
    inp.set_input_files(payloads)
    pump(page, lambda: len(selected(page) or []) == len(payloads), 8)
    run.notes["selected_hostile"] = selected(page)
    page.get_by_role("button", name="Upload").click()
    pump(page, lambda: all(rd(e) == f"hostile {n} {TAG}" for n, e in HOSTILE) and rd(uni_name) == uni.read_text(), 15)
    res = {n: (UPDIR / e).exists() and (UPDIR / e).read_text() == f"hostile {n} {TAG}" for n, e in HOSTILE}
    escaped = [str(q) for q in [UPDIR.parent / "x_traversal.txt", UPDIR.parent.parent / "win_traversal.txt", Path("/abs/root_abs.txt")] if q.exists()]
    run.check("hostile names sanitized into the upload dir (no traversal), content intact", all(res.values()) and not escaped,
              json.dumps({"saved": res, "escaped_outside": escaped, "disk": on_disk()}, ensure_ascii=False))
    run.check("unicode+spaces+parens filename roundtrip", (UPDIR / uni_name).exists() and (UPDIR / uni_name).read_bytes() == uni.read_bytes(), uni_name)
    # 12 MB upload, unthrottled, sha256 roundtrip
    inp.set_input_files([str(big)])
    pump(page, lambda: selected(page) == ["big12mb.bin"], 8)
    t0 = time.time()
    m0 = (UPDIR / "big12mb.bin").stat().st_mtime if (UPDIR / "big12mb.bin").exists() else 0
    page.get_by_role("button", name="Upload").click()
    pump(page, lambda: (UPDIR / "big12mb.bin").exists() and (UPDIR / "big12mb.bin").stat().st_mtime > m0 and (UPDIR / "big12mb.bin").stat().st_size == big.stat().st_size, 60)
    page.wait_for_timeout(500)
    okb = (UPDIR / "big12mb.bin").exists() and sha(UPDIR / "big12mb.bin") == sha(big)
    run.check("12 MB binary upload: sha256 matches", okb, f"{round(time.time() - t0, 2)}s size={(UPDIR / 'big12mb.bin').stat().st_size if (UPDIR / 'big12mb.bin').exists() else None}")
    prog_done = page.locator("[role=progressbar]").first.get_attribute("aria-valuenow") if page.locator("[role=progressbar]").count() else None
    run.notes["progress_after_big"] = prog_done
    run.check("progress bar at 100 after a completed upload", prog_done in ("100", None) and page.get_by_text("Uploading...").count() == 0,
              f"aria-valuenow={prog_done} uploading_text={page.get_by_text('Uploading...').count()}")
    # throttled upload: progress + ping during upload + cancel
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 20, "downloadThroughput": -1, "uploadThroughput": 400 * 1024})
    inp.set_input_files([str(slow)])
    pump(page, lambda: selected(page) == ["slow6mb.bin"], 8)
    page.get_by_role("button", name="Upload").click()
    upl = pump(page, lambda: page.get_by_text("Uploading...").count() > 0, 15)
    run.check("throttled upload shows 'Uploading... cancel'", upl, "")
    page.wait_for_timeout(1500)
    pv = [page.locator("[role=progressbar]").first.get_attribute("aria-valuenow")]
    page.wait_for_timeout(1500)
    pv.append(page.locator("[role=progressbar]").first.get_attribute("aria-valuenow"))
    run.check("progress advances during the throttled upload", pv[0] is not None and pv[1] is not None and 0 < int(pv[0]) < int(pv[1]) < 100, pv)
    run.shot(page, "03_uploading")
    p0 = pings(page)
    tp = time.time()
    page.locator("#qa-ping").click()
    got = pump(page, lambda: pings(page) == (p0 or 0) + 1, 8)
    lat = round(time.time() - tp, 2)
    still = page.get_by_text("Uploading...").count() > 0
    run.check("event sent DURING an in-flight upload is processed before the upload ends (#7357)", "pass" if got and still else "anomaly",
              f"pings {p0}->{pings(page)} latency={lat}s upload_still_in_flight={still}")
    run.notes["ping_latency_during_upload_s"] = lat
    page.get_by_text("cancel", exact=True).click()
    gone = pump(page, lambda: page.get_by_text("Uploading...").count() == 0, 8)
    page.wait_for_timeout(2000)
    run.check("cancel hides 'Uploading...' and no file is saved", gone and not (UPDIR / "slow6mb.bin").exists(),
              f"uploading_hidden={gone} slow6mb_on_disk={(UPDIR / 'slow6mb.bin').exists()} progress={page.locator('[role=progressbar]').first.get_attribute('aria-valuenow')}")
    run.shot(page, "04_cancelled")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
    inp.set_input_files([str(after)])
    pump(page, lambda: selected(page) == ["after cancel.txt"], 8)
    page.get_by_role("button", name="Upload").click()
    ok = pump(page, lambda: rd("after cancel.txt") == after.read_text(), 15)
    run.check("upload after cancel works", ok, on_disk())
    page.locator("#qa-ping").click()
    ok = pump(page, lambda: pings(page) == (p0 or 0) + 2, 8)
    run.check("events still processed after cancel", ok, pings(page))
    page.wait_for_timeout(1000)
    run.notes["files_list_same_session"] = listed(page)
    page.reload(wait_until="load")
    page.get_by_role("button", name="Upload").wait_for(timeout=30000)
    page.wait_for_timeout(2000)
    run.notes["files_list_after_reload"] = listed(page)
    run.notes["pings_after_reload"] = pings(page)
    run.check("reload: state kept (pings counter survives)", pings(page) == (p0 or 0) + 2, pings(page))
    run.shot(page, "05_reload")
    ctx2 = browser.new_context(viewport={"width": 1100, "height": 1000})
    page2 = ctx2.new_page()
    run.attach(page2, "fresh")
    page2.goto(URL, wait_until="load")
    page2.get_by_role("button", name="Upload").wait_for(timeout=30000)
    pump(page2, lambda: bool(listed(page2)), 10)
    fl = listed(page2)
    names = {t for t, _ in (fl or [])}
    want = {"hello.txt"} - {"hello.txt"} | {"dropped_one.txt", "dropped two.txt", "big12mb.bin", "after cancel.txt", uni_name, "x_traversal.txt", "nested.txt"}
    run.check("fresh context lists every uploaded file", want <= names, sorted(names))
    run.shot(page2, "06_fresh_list")
    served = {}
    for t, href in fl or []:
        if t in ("dropped two.txt", uni_name, "nested.txt", "big12mb.bin"):
            r = ctx2.request.get(href)
            body = r.body()
            served[t] = [r.status, href, body == (UPDIR / t).read_bytes()]
    run.check("rendered /_upload links serve the exact bytes (spaces, unicode, nested, 12 MB)", len(served) == 4 and all(v[0] == 200 and v[2] for v in served.values()),
              json.dumps(served, ensure_ascii=False))
    run.notes["disk_final"] = on_disk()
    browser.close()
sys.exit(run.finish())
