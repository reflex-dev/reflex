"""Edit the wrapped local React component (hello.jsx) while `reflex run` (dev) is live.

Usage: probe_lc_hot_edit.py <url> <outdir> <tag> <app_dir>
Changes the greeting template "Hello" -> "Howdy" in <app_dir>/local_component/hello.jsx, waits for the
running page to show it (vite HMR / reflex hot reload), then reverts and waits again. State (State.who set
before the edit) should survive.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, APP = sys.argv[1:5]
SRC = Path(APP) / "local_component" / "hello.jsx"
orig = SRC.read_text()
assert "const message = `Hello${" in orig, "unexpected hello.jsx content"
run = Run(TAG, OUT)


def wait_text(page, want, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if page.locator("#greeting h1").inner_text() == want:
                return round(time.time() - t0, 2)
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(250)
    return None


try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        run.attach(page, "main")
        page.goto(URL, wait_until="load")
        page.locator("#greeting h1").wait_for(timeout=60000)
        page.locator("#greeting h1").click()
        page.locator("input[name='who']").fill("QA")
        page.locator("input[name='who']").press("Enter")
        run.check("baseline greeting with State.who=QA", wait_text(page, "Hello QA!", 10) is not None, page.locator("#greeting h1").inner_text())
        page.evaluate("() => { window.__qa_marker = 1; }")
        SRC.write_text(orig.replace("const message = `Hello${", "const message = `Howdy${"))
        dt = wait_text(page, "Howdy QA!", 60)
        reloaded = page.evaluate("() => window.__qa_marker === undefined")
        run.check("edit hello.jsx -> running page shows the change (State.who kept)", dt is not None, f"after {dt}s, full_reload={reloaded}, text={page.locator('#greeting h1').inner_text()}")
        run.notes["edit"] = {"seconds": dt, "full_reload": reloaded}
        run.shot(page, "edited")
        page.evaluate("() => { window.__qa_marker = 1; }")
        SRC.write_text(orig)
        dt2 = wait_text(page, "Hello QA!", 60)
        run.check("revert hello.jsx -> page shows the original again", dt2 is not None, f"after {dt2}s full_reload={page.evaluate('() => window.__qa_marker === undefined')}")
        run.notes["revert"] = {"seconds": dt2}
        browser.close()
finally:
    SRC.write_text(orig)
sys.exit(run.finish())
