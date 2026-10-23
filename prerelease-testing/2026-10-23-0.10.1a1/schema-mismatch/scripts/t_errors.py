"""Frontend error reporting: click each error button on /errors and check the
backend's frontend_exceptions.log grows and no secondary TypeError hits the console.

Usage: t_errors.py <errors_url> <exc_log_path> <report.json> <shots_prefix>
"""
import sys
from pathlib import Path

from pwlib import Capture, browser, sync_playwright

url, exc_log, report, shots = sys.argv[1:5]
log = Path(exc_log)
log.parent.mkdir(parents=True, exist_ok=True)
log.write_text("")
BUTTONS = ["throw-string", "empty-errorevent", "message-errorevent", "ro-loop", "throw-error", "reject"]
results = {}
with sync_playwright() as p:
    b = browser(p)
    page = b.new_page()
    cap = Capture(page)
    page.goto(url)
    page.wait_for_selector("#inc")
    page.click("#inc")
    page.wait_for_selector("#count:has-text('count: 1')", timeout=15000)
    for bid in BUTTONS:
        before = log.read_text().count("---")
        n_console = len(cap.console)
        page.click(f"#{bid}")
        page.wait_for_timeout(1500)
        after = log.read_text().count("---")
        new_console = [m for m in cap.console[n_console:]]
        results[bid] = {
            "exceptions_logged": after - before,
            "console": [f"{m['type']}: {m['text'][:200]}" for m in new_console],
        }
    page.screenshot(path=f"{shots}_errors.png")
    # the app still works afterwards
    page.click("#inc")
    page.wait_for_timeout(800)
    results["count_after"] = page.locator("#count").inner_text()
    results["anomalies"] = cap.anomalies()
    results["exception_log"] = log.read_text()
    cap.dump(report, results=results)
    b.close()
for k, v in results.items():
    print(k, "=", v if k != "exception_log" else "\n" + v)
