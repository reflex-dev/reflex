"""Drive the /verify page of formsapp in Chromium and record what each handler received.

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_verify.py http://localhost:<FP> out.json
Records per form: steps, ws frames sent on submit, the handler records (from pre#results), the toast text if any,
plus console messages and page errors. Screenshot next to the json.
"""

import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = re.compile(r"Hey developer|HydrateFallback|\[vite\]|React DevTools|favicon")

ACTIONS = {
    "v_group_id_eq_name": [
        ("clicknth", "button[role=checkbox]", 0),
        ("clicknth", "button[role=checkbox]", 2),
        ("check", "#topping"),
        ("check", "input[name=topping][value=olives]"),
    ],
    "v_once_id_eq_name": [("clicknth", "button[role=checkbox]", 1), ("check", "#solo")],
    "v_msel_id_eq_name": [("nselect", "select[name=msel]", ["o1", "o3"])],
    "v_rep_id_eq_name": [],
    "collide_plain": [],
    "collide_chain": [],
}
# how many handler records a submit produces (collide_chain: 2 when the second handler runs)
EXPECT_SEQ = {"collide_chain": 2}
RESULT_KEYS = {"collide_chain": ("collide_first", "collide_second")}


def main():
    base = sys.argv[1].rstrip("/")
    out = sys.argv[2]
    report = {"base": base, "forms": {}, "console": [], "errors": [], "ws_sent": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_context().new_page()
        page.on("console", lambda m: report["console"].append(f"[{m.type}] {m.text}") if not BENIGN.search(m.text) else None)
        page.on("pageerror", lambda e: report["errors"].append(str(e)))
        page.on("websocket", lambda ws: ws.on("framesent", lambda f: report["ws_sent"].append(f if isinstance(f, str) else f"<binary {len(f)}>")))
        page.goto(base + "/verify")
        page.wait_for_selector("#results", timeout=60000)
        page.wait_for_timeout(1500)
        for key, steps in ACTIONS.items():
            rec = {"steps": steps, "error": None}
            try:
                box = page.locator(f'[data-form="{key}"]')
                box.scroll_into_view_if_needed()
                for step in steps:
                    if step[0] == "clicknth":
                        box.locator(step[1]).nth(step[2]).click()
                    elif step[0] == "check":
                        box.locator(step[1]).first.check(force=True)
                    elif step[0] == "nselect":
                        box.locator(step[1]).first.select_option(step[2])
                sent_before = len(report["ws_sent"])
                seq0 = int(page.locator("#seq").inner_text())
                want = seq0 + EXPECT_SEQ.get(key, 1)
                box.locator("button[type=submit]").first.click()
                deadline = time.time() + 8
                while time.time() < deadline:
                    if int(page.locator("#seq").inner_text()) >= want:
                        break
                    page.wait_for_timeout(100)
                page.wait_for_timeout(700)
                rec["seq_reached"] = int(page.locator("#seq").inner_text()) - seq0
                rec["ws_sent"] = [f for f in report["ws_sent"][sent_before:] if "event" in f[:40]]
                results = json.loads(page.locator("#results").inner_text())
                keys = RESULT_KEYS.get(key, (key,))
                rec["results"] = {k: json.loads(results[k]) for k in keys if k in results}
                toasts = page.locator("[data-sonner-toast]")
                rec["toasts"] = [toasts.nth(i).inner_text() for i in range(toasts.count())]
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{type(e).__name__}: {e}"[:500]
            report["forms"][key] = rec
        page.screenshot(path=out.replace(".json", ".png"), full_page=True)
        browser.close()
    with open(out, "w") as f:
        json.dump(report, f, indent=1)
    for key, rec in report["forms"].items():
        print(f"{key:22} seq+{rec.get('seq_reached')} results={json.dumps(rec.get('results'))[:300]} toasts={rec.get('toasts')} err={rec['error']}")
    print("console:", report["console"][:20])
    print("pageerrors:", report["errors"][:10])


if __name__ == "__main__":
    main()
