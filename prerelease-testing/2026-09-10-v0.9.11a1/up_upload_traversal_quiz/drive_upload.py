"""Playwright driver for the reflex-examples `upload` app (0.9.10.post2 -> 0.9.11a1 upgrade test).

Usage:
    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_upload.py <frontend_url> <artifacts_dir> <upload_dir_on_disk> <label>

Flows (all driven for real in headless Chromium):
  * placeholder text, file chooser (click "Select File(s)" -> native chooser), multi-select,
    re-select replaces the selection
  * drag & drop via a synthetic DataTransfer `drop` event on the react-dropzone root
  * real uploads (ascii / png / unicode+spaces), bytes on disk, listing, `/_upload/<name>` serving
  * sanitizer path: dropped files carrying odd `path`s (`./x`, `../../x`, `..`, `.. `, `a/b/c.txt`,
    backslashes, drive letters, punctuation, dotfile, 200-char name) — expected on-disk location
    follows `_sanitize_upload_filename` + `UploadFile.name` (basename) + the app's own `lstrip("/")`
  * throttled 5MB upload -> progress bar / "Uploading..." -> `rx.cancel_upload` -> no partial file
  * upload after cancel still works; fresh browser context lists everything and serves it
  * `/_upload/../rxconfig.py` traversal probe against the backend static mount
Captures console messages, page errors, failed / 4xx-5xx responses, screenshots, results.json.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

FRONTEND = sys.argv[1].rstrip("/")
ART = Path(sys.argv[2])
UPLOAD_DIR = Path(sys.argv[3])
LABEL = sys.argv[4]
ART.mkdir(parents=True, exist_ok=True)
APP_DIR = UPLOAD_DIR.parent

results = []
console_msgs = []
bad_responses = []
page_errors = []
upload_responses = []


def record(name, status, details=""):
    results.append({"name": name, "status": status, "details": details})
    print(f"[{status.upper()}] {name}: {details}", flush=True)


def wait_for(pred, timeout=15.0, step=0.25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(step)
    return pred()


FIX = ART / "fixtures"
FIX.mkdir(exist_ok=True)
txt_file = FIX / "hello.txt"
txt_file.write_text("hello from the upload test - " + LABEL)
png_file = FIX / "tiny.png"
png_file.write_bytes(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63f8cfc0f01f0005050202b03f14ad0000000049454e44ae426082"
    )
)
uni_file = FIX / "héllo wörld 测试 файл.txt"
uni_file.write_text("unicode filename content - " + LABEL)
big_file = FIX / "bigfile.bin"
big_file.write_bytes(b"\xab" * (5 * 1024 * 1024))

DROP_JS = """
async ({ files }) => {
  const dt = new DataTransfer();
  for (const spec of files) {
    const f = new File([spec.content], spec.name, { type: spec.type || "text/plain" });
    if (spec.path !== undefined) {
      // file-selector keeps an existing string `path` (electron compat) -> reaches the
      // multipart filename verbatim via `formdata.append("files", file, file.path || file.name)`.
      Object.defineProperty(f, "path", { value: spec.path, writable: false, enumerable: true });
    }
    dt.items.add(f);
  }
  return dt;
}
"""


def upload_status_snapshot():
    return len(upload_responses)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    context = browser.new_context()
    page = context.new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: page_errors.append(str(e)))

    def on_response(r):
        if r.status >= 400:
            bad_responses.append({"url": r.url, "status": r.status})
        if "/_upload" in r.url and r.request.method == "POST":
            body = ""
            try:
                body = r.text()[:500]
            except Exception as e:  # noqa: BLE001
                body = f"<unreadable: {e}>"
            upload_responses.append({"url": r.url, "status": r.status, "body": body})

    page.on("response", on_response)
    page.on(
        "requestfailed",
        lambda r: bad_responses.append({"url": r.url, "status": "FAILED:" + str(r.failure)}),
    )

    page.goto(FRONTEND, wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(ART / "01_initial.png"))

    record(
        "initial_no_files_selected",
        "pass" if page.get_by_text("No files selected").count() > 0 else "fail",
        "placeholder text visible",
    )

    # File chooser flow: clicking the button inside the dropzone opens a native chooser.
    with page.expect_file_chooser() as fc_info:
        page.get_by_role("button", name="Select File(s)").click()
    chooser = fc_info.value
    record(
        "file_chooser_opens_multiple",
        "pass" if chooser.is_multiple() else "anomaly",
        f"chooser.is_multiple={chooser.is_multiple()}",
    )
    chooser.set_files([str(txt_file), str(png_file)])
    page.wait_for_timeout(800)
    sel_ok = (
        page.get_by_text("hello.txt", exact=True).count() > 0
        and page.get_by_text("tiny.png", exact=True).count() > 0
    )
    page.screenshot(path=str(ART / "02_selected.png"))
    record("chooser_selected_files_displayed", "pass" if sel_ok else "fail",
           "hello.txt + tiny.png shown after chooser selection")

    file_input = page.locator("input[type=file]")
    file_input.set_input_files([str(uni_file)])
    page.wait_for_timeout(800)
    uni_shown = page.get_by_text(uni_file.name, exact=True).count() > 0
    old_gone = page.get_by_text("hello.txt", exact=True).count() == 0
    record("reselect_replaces_selection", "pass" if (uni_shown and old_gone) else "fail",
           f"unicode name shown={uni_shown}, old selection cleared={old_gone}")

    # Drag & drop onto the dropzone root (the element carrying the file input's parent).
    dropzone = page.locator("input[type=file]").locator("xpath=..")
    dt = page.evaluate_handle(
        DROP_JS,
        {"files": [{"name": "dropped.txt", "content": "dropped via DataTransfer - " + LABEL}]},
    )
    dropzone.dispatch_event("drop", {"dataTransfer": dt})
    page.wait_for_timeout(1000)
    dropped_shown = page.get_by_text("dropped.txt", exact=True).count() > 0
    page.screenshot(path=str(ART / "03_dropped.png"))
    record("drag_drop_selects_file", "pass" if dropped_shown else "fail",
           f"dropped.txt shown in selected list after synthetic drop={dropped_shown}")
    if dropped_shown:
        n0 = upload_status_snapshot()
        page.get_by_role("button", name="Upload").click()
        landed = wait_for(lambda: (UPLOAD_DIR / "dropped.txt").exists(), 15)
        wait_for(lambda: upload_status_snapshot() > n0, 5)
        content_ok = landed and (UPLOAD_DIR / "dropped.txt").read_text() == (
            "dropped via DataTransfer - " + LABEL
        )
        record("drag_drop_upload_lands", "pass" if content_ok else "fail",
               f"dropped.txt on disk={landed}, content ok={content_ok}, "
               f"upload responses={upload_responses[n0:]}")

    # Upload three files selected through the chooser.
    with page.expect_file_chooser() as fc_info:
        page.get_by_text("Drag and drop files here").click()
    fc_info.value.set_files([str(txt_file), str(png_file), str(uni_file)])
    page.wait_for_timeout(500)
    n0 = upload_status_snapshot()
    page.get_by_role("button", name="Upload").click()
    expected = ["hello.txt", "tiny.png", uni_file.name]
    wait_for(lambda: all((UPLOAD_DIR / n).exists() for n in expected), 20)
    wait_for(lambda: upload_status_snapshot() > n0, 5)
    on_disk = {n: (UPLOAD_DIR / n).exists() for n in expected}
    record("files_land_on_disk", "pass" if all(on_disk.values()) else "fail",
           json.dumps(on_disk, ensure_ascii=False) + f" responses={upload_responses[n0:]}")
    if (UPLOAD_DIR / "hello.txt").exists():
        record("uploaded_content_matches",
               "pass" if (UPLOAD_DIR / "hello.txt").read_text() == txt_file.read_text() else "fail",
               "hello.txt content roundtrip")
    if (UPLOAD_DIR / "tiny.png").exists():
        record("png_bytes_match",
               "pass" if (UPLOAD_DIR / "tiny.png").read_bytes() == png_file.read_bytes() else "fail",
               "tiny.png byte roundtrip")
    if (UPLOAD_DIR / uni_file.name).exists():
        record("unicode_filename_content_matches",
               "pass" if (UPLOAD_DIR / uni_file.name).read_text() == uni_file.read_text() else "fail",
               f"{uni_file.name} content roundtrip")

    page.wait_for_timeout(1500)

    def links_present():
        return all(page.locator(f'a:has-text("{n}")').count() > 0 for n in ["hello.txt", "tiny.png"])

    listed_without_reload = links_present()
    if not listed_without_reload:
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1500)
    listed = links_present()
    page.screenshot(path=str(ART / "04_after_upload.png"))
    record("uploaded_files_listed_in_ui", "pass" if listed else "anomaly",
           f"listed_without_reload={listed_without_reload}, listed_after_reload={listed} "
           "(cached dependency-less @rx.var never recomputes in-session: known app quirk)")

    # Sanitizer path: odd multipart filenames via the `path` attribute react-dropzone forwards.
    # (name, path, expected relative on-disk path under uploaded_files/ or None if unknown)
    odd_cases = [
        ("plain_dot_slash.txt", "./plain_dot_slash.txt", "plain_dot_slash.txt"),
        ("escape_traversal.txt", "../../escape_traversal.txt", "escape_traversal.txt"),
        ("nested.txt", "sub/dir/nested.txt", "nested.txt"),  # UploadFile.name is the basename
        ("abs_path.txt", "/etc/abs_path.txt", "abs_path.txt"),
        ("backslash_traversal.txt", "..\\..\\backslash_traversal.txt", "backslash_traversal.txt"),
        ("drive_letter.txt", "C:\\Users\\victim\\drive_letter.txt", "drive_letter.txt"),
        ("dotdot", "..", "upload"),
        ("dotdot_space", ".. ", "upload"),
        ("dots_and_spaces", "./../. ", "upload"),
        (".hidden_dotfile", ".hidden_dotfile", ".hidden_dotfile"),
        # Chromium percent-encodes a double quote in the multipart filename (HTML spec) -> %22 on disk.
        ("punct #1 (copy) [x] &=+;,'\"!.txt", "punct #1 (copy) [x] &=+;,'\"!.txt",
         "punct #1 (copy) [x] &=+;,'%22!.txt"),
        ("colon:semi;pipe|q?.txt", "colon:semi;pipe|q?.txt", "colon:semi;pipe|q?.txt"),
        ("x" * 200 + ".txt", "x" * 200 + ".txt", "x" * 200 + ".txt"),
    ]
    for name, path, expected_rel in odd_cases:
        content = f"odd[{path}] - {LABEL}"
        dt = page.evaluate_handle(DROP_JS, {"files": [{"name": name, "content": content, "path": path}]})
        # stale entries: remove any prior file with the expected name so this check is fresh
        target = (UPLOAD_DIR / expected_rel) if expected_rel else None
        if target and target.exists():
            target.unlink()
        n0 = upload_status_snapshot()
        dropzone.dispatch_event("drop", {"dataTransfer": dt})
        page.wait_for_timeout(600)
        page.get_by_role("button", name="Upload").click()
        got_resp = wait_for(lambda: upload_status_snapshot() > n0, 15)
        resp = upload_responses[n0:] if got_resp else []
        # find what actually landed anywhere under the app dir tree that is new
        landed = target is not None and wait_for(lambda: target.exists(), 5) and target.read_text() == content
        escaped = [
            str(q) for q in [APP_DIR / Path(expected_rel or name).name, APP_DIR.parent / Path(expected_rel or name).name]
            if q.is_file()
        ]
        status = "pass" if (landed and not escaped and all(r["status"] == 200 for r in resp)) else "fail"
        record(
            f"odd_filename[{path!r}]",
            status,
            f"expected={expected_rel!r} landed={landed} escaped_outside_upload_dir={escaped} "
            f"responses={[(r['status'], r['body'][:120]) for r in resp]}",
        )
    page.screenshot(path=str(ART / "05_after_odd_names.png"))
    # anything that landed outside uploaded_files? (candidate locations a traversal could reach)
    candidates = []
    for base_dir in (APP_DIR, APP_DIR.parent, APP_DIR.parent.parent, Path("/etc"), Path("/")):
        for n in ("escape_traversal.txt", "backslash_traversal.txt", "abs_path.txt", "drive_letter.txt",
                  "upload", "nested.txt", "plain_dot_slash.txt"):
            q = base_dir / n
            if q.is_file():
                candidates.append(str(q))
    for q in (APP_DIR / "sub" / "dir" / "nested.txt", UPLOAD_DIR / "sub" / "dir" / "nested.txt"):
        if q.is_file():
            candidates.append(str(q))
    record("no_file_escaped_upload_dir", "pass" if not candidates else "fail", f"found_outside_or_nested={candidates}")

    # Throttled upload + cancel.
    cdp = context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions",
             {"offline": False, "latency": 20, "downloadThroughput": -1, "uploadThroughput": 300 * 1024})
    file_input.set_input_files([str(big_file)])
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Upload").click()
    try:
        page.get_by_text("Uploading...").wait_for(state="visible", timeout=10000)
        record("uploading_indicator_shown", "pass", "Uploading... text + cancel link appeared")
        page.wait_for_timeout(1200)
        prog = page.locator("[role=progressbar]").first.get_attribute("aria-valuenow")
        page.screenshot(path=str(ART / "06_uploading_progress.png"))
        record("upload_progress_updates", "pass" if prog not in (None, "0") else "anomaly",
               f"aria-valuenow={prog} during throttled upload")
        page.get_by_text("cancel", exact=True).click()
        page.get_by_text("Uploading...").wait_for(state="hidden", timeout=5000)
        time.sleep(2)
        landed = (UPLOAD_DIR / "bigfile.bin").exists()
        record("cancel_upload_aborts", "pass" if not landed else "fail",
               f"bigfile.bin on disk after cancel: {landed}")
    except Exception as e:  # noqa: BLE001
        page.screenshot(path=str(ART / "06_cancel_flow_error.png"))
        record("cancel_upload_flow", "fail", f"exception: {e}")
    cdp.send("Network.emulateNetworkConditions",
             {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})

    extra = FIX / "after cancel ok.txt"
    extra.write_text("post-cancel upload - " + LABEL)
    file_input.set_input_files([str(extra)])
    page.wait_for_timeout(400)
    page.get_by_role("button", name="Upload").click()
    ok = wait_for(lambda: (UPLOAD_DIR / extra.name).exists(), 15)
    record("upload_after_cancel_works", "pass" if ok else "fail",
           f"'{extra.name}' (space in name) landed={ok}")
    page.screenshot(path=str(ART / "07_final.png"))

    # Fresh browser context (new token): list + serving.
    ctx2 = browser.new_context()
    page2 = ctx2.new_page()
    page2.on("console", lambda m: console_msgs.append({"type": m.type, "text": "[ctx2] " + m.text}))
    page2.on("pageerror", lambda e: page_errors.append("[ctx2] " + str(e)))
    page2.goto(FRONTEND, wait_until="networkidle")
    page2.wait_for_timeout(2000)
    names = ["hello.txt", "tiny.png", uni_file.name, "dropped.txt", "escape_traversal.txt", "upload"]
    fresh = {n: page2.locator(f'a:text-is("{n}")').count() > 0 for n in names}
    page2.screenshot(path=str(ART / "08_fresh_context_list.png"), full_page=True)
    record("files_listed_fresh_session", "pass" if all(fresh.values()) else "fail",
           json.dumps(fresh, ensure_ascii=False))

    def fetch_link(pg, ctx, name, expect_text=None, expect_bytes=None):
        loc = pg.locator(f'a:text-is("{name}")')
        if loc.count() == 0:
            return "fail", f"no link for {name}"
        href = loc.first.get_attribute("href")
        url = href if href.startswith("http") else FRONTEND + href
        resp = ctx.request.get(url)
        if expect_text is not None:
            ok = resp.ok and resp.text() == expect_text
        else:
            ok = resp.ok and resp.body() == expect_bytes
        return ("pass" if ok else "fail"), f"href={href} status={resp.status} match={ok}"

    for name, args in [
        ("hello.txt", {"expect_text": txt_file.read_text()}),
        (uni_file.name, {"expect_text": uni_file.read_text()}),
        ("tiny.png", {"expect_bytes": png_file.read_bytes()}),
        ("after cancel ok.txt", {"expect_text": extra.read_text()}),
    ]:
        st, det = fetch_link(page2, ctx2, name, **args)
        record(f"upload_url_serves[{name}]", st, det)

    # Traversal probes against the /_upload static mount (backend).
    hello_href = page2.locator('a:text-is("hello.txt")').first.get_attribute("href")
    base = hello_href[: hello_href.rfind("/") + 1] if hello_href else None
    if base:
        for probe in ["../rxconfig.py", "..%2Frxconfig.py", "%2e%2e/rxconfig.py", "sub/../hello.txt"]:
            r = ctx2.request.get(base + probe, max_redirects=0)
            leaked = "app_name" in (r.text() if r.ok else "")
            record(f"upload_mount_traversal[{probe}]", "fail" if leaked else "pass",
                   f"status={r.status} leaked_rxconfig={leaked}")
    ctx2.close()
    browser.close()

(ART / "console.json").write_text(json.dumps(console_msgs, indent=2, ensure_ascii=False))
(ART / "bad_responses.json").write_text(json.dumps(bad_responses, indent=2))
(ART / "page_errors.json").write_text(json.dumps(page_errors, indent=2))
(ART / "upload_responses.json").write_text(json.dumps(upload_responses, indent=2, ensure_ascii=False))
(ART / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))

unexpected_console = [
    m for m in console_msgs
    if m["type"] in ("error", "warning")
    and "HydrateFallback" not in m["text"]
    and "React DevTools" not in m["text"]
    and "[vite] connecting" not in m["text"]
    and "[vite] connected" not in m["text"]
]
print("\nUNEXPECTED CONSOLE:", json.dumps(unexpected_console, indent=2, ensure_ascii=False))
print("ALL CONSOLE TYPES:", json.dumps(sorted({m["type"] for m in console_msgs})))
print("BAD RESPONSES:", json.dumps(bad_responses, indent=2))
print("PAGE ERRORS:", json.dumps(page_errors, indent=2))
print("SUMMARY:", json.dumps({r["name"]: r["status"] for r in results}, ensure_ascii=False))
