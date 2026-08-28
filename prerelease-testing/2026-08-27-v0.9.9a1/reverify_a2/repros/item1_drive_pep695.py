"""Item 1 E2E: alias-annotated state var mutation updates the UI on a2.
Also exercises the uncalled alias handler bound to on_change (select)."""
import sys, json
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3140/"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "shots/pep695_a2"
import os; os.makedirs(SHOTS, exist_ok=True)

console_msgs, page_errors, failed = [], [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_context().new_page()
    pg.on("console", lambda m: console_msgs.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: page_errors.append(str(e)))
    pg.on("requestfailed", lambda r: failed.append(f"{r.url} {r.failure}"))
    pg.goto(URL, wait_until="networkidle", timeout=60000)
    pg.wait_for_selector("#key", timeout=20000)
    pg.wait_for_timeout(800)
    def read():
        return {sel: pg.text_content(sel) for sel in ["#name", "#key", "#union", "#nested", "#pos"]}
    before = read()
    pg.screenshot(path=f"{SHOTS}/01_initial.png")
    # click the 'week' button (choose_key('week') -> mutates key/union/nested via setattr on alias vars)
    pg.click("#btn-week")
    pg.wait_for_timeout(700)
    after_week = read()
    pg.screenshot(path=f"{SHOTS}/02_after_week.png")
    # type into rename input (rename(value: Name) alias arg)
    pg.fill("#name-input", "renamed-alias")
    pg.wait_for_timeout(700)
    after_name = read()
    # use the uncalled-handler select (on_change=AliasState.choose_key) -> pick 'month'
    try:
        pg.click("button[role='combobox']", timeout=4000)
        pg.wait_for_timeout(300)
        pg.get_by_role("option", name="month").click(timeout=4000)
        pg.wait_for_timeout(700)
    except Exception as e:
        console_msgs.append(f"select-interaction-note: {e}")
    after_select = read()
    pg.screenshot(path=f"{SHOTS}/03_after_select.png")
    b.close()

print("BEFORE      :", before)
print("AFTER week  :", after_week)
print("AFTER name  :", after_name)
print("AFTER select:", after_select)
key_updated = after_week["#key"] != before["#key"] and "week" in (after_week["#key"] or "")
union_updated = "week" in (after_week["#union"] or "")
name_updated = "renamed-alias" in (after_name["#name"] or "")
select_updated = "month" in (after_select["#key"] or "")
print("RESULT key_updated=%s union_updated=%s name_updated=%s select_updated=%s" % (key_updated, union_updated, name_updated, select_updated))
noise_ok = [c for c in console_msgs if 'error' in c.lower()]
print("console errors:", noise_ok)
print("page errors:", page_errors)
print("failed reqs:", failed)
print("VERDICT:", "PASS" if (key_updated and union_updated and name_updated) else "FAIL")
