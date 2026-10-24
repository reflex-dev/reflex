import json, sys
import playwright  # noqa
from playwright.sync_api import sync_playwright
assert "/envs/driver/" in playwright.__file__
base, out = sys.argv[1], sys.argv[2]
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium"); p = b.new_page(); errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(base, wait_until="networkidle"); p.wait_for_selector("#submit_f_dict"); p.wait_for_timeout(1500)
    for f in ["f_dict", "f_td", "f_fd"]:
        if p.locator(f"#submit_{f}").count():
            p.locator(f"#submit_{f}").click(); p.wait_for_timeout(1200)
    res = {"out": p.locator("#out").inner_text(), "errors": errs}
    json.dump(res, open(out, "w"), indent=1); print(json.dumps(res, indent=1)); b.close()
