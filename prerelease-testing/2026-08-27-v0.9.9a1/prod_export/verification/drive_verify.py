"""Drive the verifier app: load index, check BadDomLink renders, click it, check navigation.

Usage: drive_verify.py <base_url> <label>
"""

import json
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1]
label = sys.argv[2]

console_msgs = []
page_errors = []
bad_responses = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on(
        "response",
        lambda r: bad_responses.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )

    page.goto(base + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_selector("#idx-heading", timeout=30000)
    link = page.wait_for_selector("#bad-link", timeout=15000)
    href = link.get_attribute("href")
    print("RESULT link_rendered=True href=%r tag=%s" % (href, link.evaluate("e => e.tagName")))
    page.screenshot(path=f"{label}_index.png")
    link.click()
    page.wait_for_selector("#other-heading", timeout=15000)
    print("RESULT navigated=True url=%s" % page.url)
    page.screenshot(path=f"{label}_other.png")
    browser.close()

with open(f"{label}_console.json", "w") as f:
    json.dump(
        {"console": console_msgs, "pageerrors": page_errors, "bad_responses": bad_responses},
        f,
        indent=1,
    )
interesting = [
    m
    for m in console_msgs
    if m["type"] in ("error", "warning")
    and "HydrateFallback" not in m["text"]
    and "React DevTools" not in m["text"]
    and "[vite]" not in m["text"]
]
print("RESULT console_errors_warnings=%s" % json.dumps(interesting))
print("RESULT pageerrors=%s" % json.dumps(page_errors))
print("RESULT bad_responses=%s" % json.dumps(bad_responses))
