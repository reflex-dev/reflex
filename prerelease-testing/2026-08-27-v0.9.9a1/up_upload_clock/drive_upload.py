"""Playwright driver for the reflex-examples `upload` app.

Usage:
    python drive_upload.py <frontend_url> <artifacts_dir> <upload_dir_on_disk> <label>

Exercises: file selection display, real uploads (text / png / unicode+spaces
filename), uploaded-file listing + content served via upload URL, files landing
on disk, re-selection replacing the selected list, and a throttled-upload
cancel flow. Captures console messages, failed/4xx-5xx responses, screenshots.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

FRONTEND = sys.argv[1]
ART = Path(sys.argv[2])
UPLOAD_DIR = Path(sys.argv[3])
LABEL = sys.argv[4]
ART.mkdir(parents=True, exist_ok=True)

results = []
console_msgs = []
bad_responses = []
page_errors = []


def record(name, status, details=""):
    results.append({"name": name, "status": status, "details": details})
    print(f"[{status.upper()}] {name}: {details}")


# Test fixture files
FIX = ART / "fixtures"
FIX.mkdir(exist_ok=True)
txt_file = FIX / "hello.txt"
txt_file.write_text("hello from the upload test - " + LABEL)
png_file = FIX / "tiny.png"
# 1x1 red pixel PNG
png_file.write_bytes(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63f8cfc0f01f0005050202b03f14ad0000000049454e44ae426082"
    )
)
uni_file = FIX / "héllo wörld 测试 файл.txt"
uni_file.write_text("unicode filename content - " + LABEL)
big_file = FIX / "bigfile.bin"
big_file.write_bytes(b"\xab" * (5 * 1024 * 1024))  # 5 MB for cancel test

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    context = browser.new_context()
    page = context.new_page()
    page.on(
        "console",
        lambda m: console_msgs.append({"type": m.type, "text": m.text}),
    )
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on(
        "response",
        lambda r: bad_responses.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )
    page.on(
        "requestfailed",
        lambda r: bad_responses.append({"url": r.url, "status": "FAILED:" + str(r.failure)}),
    )

    page.goto(FRONTEND, wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(ART / "01_initial.png"))

    # 1. initial state shows "No files selected"
    if page.get_by_text("No files selected").count() > 0:
        record("initial_no_files_selected", "pass", "placeholder text visible")
    else:
        record("initial_no_files_selected", "fail", "placeholder text missing")

    # 2. select two files, check selected list renders their names
    file_input = page.locator("input[type=file]")
    file_input.set_input_files([str(txt_file), str(png_file)])
    page.wait_for_timeout(800)
    sel_ok = (
        page.get_by_text("hello.txt", exact=True).count() > 0
        and page.get_by_text("tiny.png", exact=True).count() > 0
    )
    page.screenshot(path=str(ART / "02_selected.png"))
    record(
        "selected_files_displayed",
        "pass" if sel_ok else "fail",
        "hello.txt + tiny.png shown after selection" if sel_ok else "names not shown",
    )

    # 3. re-select with a different (unicode) file: selection should be replaced
    file_input.set_input_files([str(uni_file)])
    page.wait_for_timeout(800)
    uni_shown = page.get_by_text(uni_file.name, exact=True).count() > 0
    old_gone = page.get_by_text("hello.txt", exact=True).count() == 0
    record(
        "reselect_replaces_selection",
        "pass" if (uni_shown and old_gone) else "fail",
        f"unicode name shown={uni_shown}, old selection cleared={old_gone}",
    )

    # 4. select all three and upload for real
    file_input.set_input_files([str(txt_file), str(png_file), str(uni_file)])
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Upload").click()
    # wait for files to land on disk
    deadline = time.time() + 20
    expected = ["hello.txt", "tiny.png", uni_file.name]
    while time.time() < deadline:
        if all((UPLOAD_DIR / n).exists() for n in expected):
            break
        time.sleep(0.5)
    on_disk = {n: (UPLOAD_DIR / n).exists() for n in expected}
    record(
        "files_land_on_disk",
        "pass" if all(on_disk.values()) else "fail",
        json.dumps(on_disk, ensure_ascii=False),
    )
    if (UPLOAD_DIR / "hello.txt").exists():
        content_ok = (UPLOAD_DIR / "hello.txt").read_text() == txt_file.read_text()
        record("uploaded_content_matches", "pass" if content_ok else "fail",
               "hello.txt content roundtrip")
    if (UPLOAD_DIR / uni_file.name).exists():
        ucontent_ok = (UPLOAD_DIR / uni_file.name).read_text() == uni_file.read_text()
        record("unicode_filename_content_matches", "pass" if ucontent_ok else "fail",
               f"{uni_file.name} content roundtrip")

    # 5. Files: list in UI (computed var over upload dir). May need reload if
    #    the cached var does not recompute - record which.
    page.wait_for_timeout(1500)
    def links_present():
        return all(
            page.locator(f'a:has-text("{n}")').count() > 0 for n in ["hello.txt", "tiny.png"]
        )
    listed_without_reload = links_present()
    if not listed_without_reload:
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1500)
    listed = links_present()
    page.screenshot(path=str(ART / "03_after_upload.png"))
    record(
        "uploaded_files_listed_in_ui",
        "pass" if listed else "fail",
        f"listed_without_reload={listed_without_reload}, listed_after_reload={listed}",
    )

    # 6. fetch an uploaded file through its link href (backend /_upload route)
    href = None
    loc = page.locator('a:has-text("hello.txt")')
    if loc.count() > 0:
        href = loc.first.get_attribute("href")
    if href:
        resp = context.request.get(href if href.startswith("http") else FRONTEND.rstrip("/") + href)
        body = resp.text() if resp.ok else ""
        ok = resp.ok and body == txt_file.read_text()
        record("uploaded_file_served_via_url", "pass" if ok else "fail",
               f"href={href} status={resp.status} content_match={body == txt_file.read_text()}")
    else:
        record("uploaded_file_served_via_url", "fail", "no link href found for hello.txt")

    # 7. cancel flow: throttle upload, start big upload, verify progress UI, cancel
    cdp = context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send(
        "Network.emulateNetworkConditions",
        {"offline": False, "latency": 20, "downloadThroughput": -1,
         "uploadThroughput": 300 * 1024},
    )
    file_input.set_input_files([str(big_file)])
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Upload").click()
    try:
        page.get_by_text("Uploading...").wait_for(state="visible", timeout=10000)
        record("uploading_indicator_shown", "pass", "Uploading... text + cancel link appeared")
        page.wait_for_timeout(1200)  # let some progress accumulate
        prog = page.locator("[role=progressbar]").first.get_attribute("aria-valuenow")
        page.screenshot(path=str(ART / "04_uploading_progress.png"))
        record("upload_progress_updates", "pass" if prog not in (None, "0") else "anomaly",
               f"aria-valuenow={prog} during throttled upload")
        page.get_by_text("cancel", exact=True).click()
        page.get_by_text("Uploading...").wait_for(state="hidden", timeout=5000)
        time.sleep(2)
        landed = (UPLOAD_DIR / "bigfile.bin").exists()
        record("cancel_upload_aborts", "pass" if not landed else "fail",
               f"bigfile.bin on disk after cancel: {landed}")
    except Exception as e:
        page.screenshot(path=str(ART / "04_cancel_flow_error.png"))
        record("cancel_upload_flow", "fail", f"exception: {e}")
    cdp.send(
        "Network.emulateNetworkConditions",
        {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1},
    )

    # 8. after cancel, a fresh upload still works (connection healthy)
    extra = FIX / "after cancel ok.txt"
    extra.write_text("post-cancel upload - " + LABEL)
    file_input.set_input_files([str(extra)])
    page.wait_for_timeout(400)
    page.get_by_role("button", name="Upload").click()
    deadline = time.time() + 15
    while time.time() < deadline and not (UPLOAD_DIR / extra.name).exists():
        time.sleep(0.5)
    ok = (UPLOAD_DIR / extra.name).exists()
    record("upload_after_cancel_works", "pass" if ok else "fail",
           f"'{extra.name}' (space in name) landed={ok}")
    page.screenshot(path=str(ART / "05_final.png"))

    # 9. fresh browser context (new state token): Files list should include
    #    uploads, and the file link should serve the content.
    ctx2 = browser.new_context()
    page2 = ctx2.new_page()
    page2.on("console", lambda m: console_msgs.append({"type": m.type, "text": "[ctx2] " + m.text}))
    page2.goto(FRONTEND, wait_until="networkidle")
    page2.wait_for_timeout(2000)
    fresh_listed = all(
        page2.locator(f'a:has-text("{n}")').count() > 0 for n in ["hello.txt", "tiny.png", uni_file.name]
    )
    page2.screenshot(path=str(ART / "06_fresh_context_list.png"))
    record("files_listed_fresh_session", "pass" if fresh_listed else "fail",
           f"links for uploads visible in new session={fresh_listed}")
    href2 = None
    l2 = page2.locator('a:has-text("hello.txt")')
    if l2.count() > 0:
        href2 = l2.first.get_attribute("href")
    if href2:
        resp2 = ctx2.request.get(href2 if href2.startswith("http") else FRONTEND.rstrip("/") + href2)
        ok2 = resp2.ok and resp2.text() == txt_file.read_text()
        record("upload_url_serves_content", "pass" if ok2 else "fail",
               f"href={href2} status={resp2.status}")
        # unicode filename link too
        l3 = page2.locator(f'a:has-text("{uni_file.name}")')
        if l3.count() > 0:
            href3 = l3.first.get_attribute("href")
            resp3 = ctx2.request.get(href3 if href3.startswith("http") else FRONTEND.rstrip("/") + href3)
            ok3 = resp3.ok and resp3.text() == uni_file.read_text()
            record("unicode_upload_url_serves_content", "pass" if ok3 else "fail",
                   f"href={href3} status={resp3.status}")
    else:
        record("upload_url_serves_content", "fail", "no hello.txt link in fresh session")
    ctx2.close()

    browser.close()

(ART / "console.json").write_text(json.dumps(console_msgs, indent=2, ensure_ascii=False))
(ART / "bad_responses.json").write_text(json.dumps(bad_responses, indent=2))
(ART / "page_errors.json").write_text(json.dumps(page_errors, indent=2))
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
print("BAD RESPONSES:", json.dumps(bad_responses, indent=2))
print("PAGE ERRORS:", json.dumps(page_errors, indent=2))
print("SUMMARY:", json.dumps({r["name"]: r["status"] for r in results}))
