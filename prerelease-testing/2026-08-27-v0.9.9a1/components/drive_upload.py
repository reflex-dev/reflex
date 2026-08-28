"""Drive the buffered (non-streamed) upload handler with adversarial filenames.

Uses Playwright FilePayload to set arbitrary multipart filenames (path
traversal, special chars, unicode) without them being real files on disk, then
reads back the sanitized name/path recorded by the handler (#6753).
Usage: python drive_upload.py <base_url> <outdir>
"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3380"
OUT = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "."

# raw filename -> expected sanitized path (from _sanitize_upload_filename)
CASES = [
    ("../../evil.txt", "evil.txt"),
    ("..\\..\\evil.txt", "evil.txt"),
    ("/etc/passwd", "passwd"),
    ("C:\\Windows\\system32\\evil.dll", "evil.dll"),
    ("a b<>|.txt", "a b<>|.txt"),
    ("café_日本_🎉.txt", "café_日本_🎉.txt"),
    ("sub/dir/ok.txt", "sub/dir/ok.txt"),
    ("....//....//evil.txt", "..../..../evil.txt"),
    ("normal.txt", "normal.txt"),
]

console_msgs = []
http_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append((m.type, m.text)))
    page.on("response", lambda r: http_errors.append((r.status, r.url)) if r.status >= 400 else None)

    page.goto(BASE + "/upload", wait_until="networkidle", timeout=60000)
    page.wait_for_selector("#upload-btn", timeout=30000)
    page.wait_for_timeout(1000)

    file_input = page.locator("#up1 input[type=file]")
    payloads = [
        {"name": raw, "mimeType": "text/plain", "buffer": f"content-of-{i}".encode()}
        for i, (raw, _) in enumerate(CASES)
    ]
    file_input.set_input_files(payloads)
    page.wait_for_timeout(500)
    page.click("#upload-btn")
    # wait for saved list to populate to len(CASES)
    try:
        page.wait_for_function(
            f"() => document.querySelectorAll('.saved-file').length >= {len(CASES)}",
            timeout=20000,
        )
    except Exception as e:
        print("WAIT_ERROR:", e)
    page.wait_for_timeout(500)

    saved = page.eval_on_selector_all(
        ".saved-file", "els => els.map(e => e.textContent)"
    )
    page.screenshot(path=OUT + "/upload.png", full_page=True)
    browser.close()

print("SAVED_ENTRIES:")
for s in saved:
    print("  ", s)

# Parse "name=<repr> path=<repr>" back out and compare to expected.
import re

parsed = {}
for s in saved:
    m = re.search(r"path='([^']*)'", s) or re.search(r'path="([^"]*)"', s)
    if m:
        parsed.setdefault(m.group(1), s)

print("\nCHECKS:")
fails = 0
for raw, expected in CASES:
    ok = expected in parsed
    status = "pass" if ok else "FAIL"
    if not ok:
        fails += 1
    print(f"  [{status}] raw={raw!r} expected_path={expected!r} present={ok}")

print("\nCONSOLE:")
for t, m in console_msgs:
    print(f"  [{t}] {m[:200]}")
print("HTTP_4XX_5XX:", http_errors)
print("\nSUMMARY:", "ALL PASS" if fails == 0 else f"{fails} FAILS")
sys.exit(1 if fails else 0)
