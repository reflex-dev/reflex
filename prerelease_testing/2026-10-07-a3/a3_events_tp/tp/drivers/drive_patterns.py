"""Drive the tp_patterns app (identical source on 0.9.12 and 0.10.0a1) and record observed values.

Usage: drive_patterns.py <base_url> <out_dir> <label>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tpdrive import Capture, browser, wait_text

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
LABEL = sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
cap = Capture()
obs: dict[str, str] = {}


def txt(page, sel):
    loc = page.locator(sel)
    return loc.first.inner_text() if loc.count() else "<missing>"


def shot(page, name):
    page.screenshot(path=str(OUT / f"{LABEL}-{name}.png"), full_page=True)


with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page(), "main")

    cap.label = "storage-seed"
    page.goto(BASE + "/storage", wait_until="networkidle")
    wait_text(page, "#store_log", "on_load")
    page.evaluate("""() => {
        for (const k of ['tp_ls_cv','tp_ls_onload','tp_ls_event','tp_ls_nd']) localStorage.setItem(k, 'bad');
        document.cookie = 'tp_ck_onload=bad; path=/';
    }""")
    cap.label = "storage-reload"
    page.goto(BASE + "/storage", wait_until="networkidle")
    wait_text(page, "#store_log", "on_load")
    page.wait_for_timeout(2500)
    ls = page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")
    ck = page.evaluate("() => document.cookie")
    for sel in ["#ls_cv", "#cv_check", "#ls_onload", "#ck_onload", "#ls_nd", "#ls_event", "#store_log"]:
        obs[f"storage {sel}"] = txt(page, sel)
    obs["storage localStorage"] = json.dumps({k: v for k, v in ls.items() if k.startswith("tp_")})
    obs["storage cookie"] = ck
    cap.check("computed-var reset of LocalStorage reaches browser", ls.get("tp_ls_cv") == "", f"tp_ls_cv={ls.get('tp_ls_cv')!r} ui={obs['storage #ls_cv']!r} cv={obs['storage #cv_check']!r}")
    cap.check("on_load reset (to default '') of LocalStorage reaches browser", ls.get("tp_ls_onload") == "", f"tp_ls_onload={ls.get('tp_ls_onload')!r} ui={obs['storage #ls_onload']!r}")
    cap.check("on_load reset (to default '') of Cookie reaches browser", "tp_ck_onload=bad" not in ck, f"cookie={ck!r} ui={obs['storage #ck_onload']!r}")
    cap.check("on_load set to non-default of LocalStorage reaches browser", ls.get("tp_ls_nd") == "fixed", f"tp_ls_nd={ls.get('tp_ls_nd')!r}")
    shot(page, "storage-after-reload")
    cap.label = "storage-event"
    page.click("#reset_event")
    page.wait_for_timeout(1500)
    ls = page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")
    obs["storage after reset_event localStorage"] = json.dumps({k: v for k, v in ls.items() if k.startswith("tp_")})
    obs["storage after reset_event #ls_event"] = txt(page, "#ls_event")
    cap.check("event-handler reset (to default '') of LocalStorage reaches browser", ls.get("tp_ls_event") == "", f"tp_ls_event={ls.get('tp_ls_event')!r}")
    # second fresh tab: what does the backend think now?
    p2 = cap.attach(ctx.new_page(), "tab2")
    p2.goto(BASE + "/storage", wait_until="networkidle")
    wait_text(p2, "#store_log", "on_load")
    p2.wait_for_timeout(1500)
    for sel in ["#ls_cv", "#cv_check", "#ls_onload", "#ck_onload"]:
        obs[f"storage tab2 {sel}"] = txt(p2, sel)
    p2.close()

    cap.label = "mixins"
    page.goto(BASE + "/mixins", wait_until="networkidle")
    wait_text(page, "#a_view", "count=")
    page.click("#a_inc"); page.click("#a_inc"); page.click("#b_inc")
    page.wait_for_timeout(1000)
    page.click("#a_slow")
    page.wait_for_timeout(1500)
    obs["mixins A"] = txt(page, "#a_view")
    obs["mixins B"] = txt(page, "#b_view")
    cap.check("mixin A independent counter + mixin computed var + backend var + background", obs["mixins A"].replace(" ", "") == "Acount=12doubled=24hits=3", obs["mixins A"])
    cap.check("mixin B independent counter + overridden computed var", obs["mixins B"].replace(" ", "") == "Bcount=1doubled=20hits=1", obs["mixins B"])
    shot(page, "mixins")

    cap.label = "inherit"
    page.goto(BASE + "/inherit", wait_until="networkidle")
    wait_text(page, "#items", "items=")
    for bid in ["#pkg_add", "#add_twice", "#touch_other"]:
        page.click(bid)
        page.wait_for_timeout(700)
    obs["inherit items after pkg_add+add_twice"] = txt(page, "#items")
    obs["inherit user_items"] = txt(page, "#user_items")
    obs["inherit extra after add_twice"] = txt(page, "#extra")
    obs["inherit note after touch_other"] = txt(page, "#note")
    obs["inherit remote"] = txt(page, "#remote")
    page.click("#read_values"); page.wait_for_timeout(700)
    obs["inherit extra after read_values"] = txt(page, "#extra")
    page.click("#setvar"); page.wait_for_timeout(700)
    obs["inherit extra after setvar"] = txt(page, "#extra")
    page.click("#dyn_bump"); page.click("#dyn_bump"); page.wait_for_timeout(700)
    obs["inherit dyn after 2 bumps"] = txt(page, "#dyn")
    if page.locator("#shadow_set").count():
        page.click("#shadow_set"); page.wait_for_timeout(700)
    obs["inherit shadow"] = txt(page, "#shadow")
    page.click("#clear_dict"); page.wait_for_timeout(700)
    obs["inherit items after clear via event_handlers"] = txt(page, "#items")
    obs["inherit fields report"] = txt(page, "#fields")
    cap.check("inherited handler + get_state + setvar + dynamic type() state all respond", "set-by-setvar" in obs["inherit extra after setvar"] and "dyn=5" in obs["inherit dyn after 2 bumps"].replace(" ", "") and "touched by UserState" in obs["inherit remote"], json.dumps({k: v for k, v in obs.items() if k.startswith("inherit") and "fields" not in k}))
    shot(page, "inherit")

    cap.label = "classattr"
    page.goto(BASE + "/classattr", wait_until="networkidle")
    wait_text(page, "#classattr", "class-level")
    obs["classattr report"] = txt(page, "#classattr")
    obs["classattr component"] = txt(page, "#from_const")
    page.click("#show_instance"); page.wait_for_timeout(1000)
    obs["classattr instance"] = txt(page, "#shown")
    cap.check("class-level backend constants read as values", "_LABEL='label-const'" in obs["classattr report"], obs["classattr report"])
    cap.check("component built from class-level constant", obs["classattr component"] == "label-const", obs["classattr component"])
    cap.check("instance-level constants + classmethod-assigned static", obs["classattr instance"].replace(" ", "") == "shown=label-const|16|A|cache='configured-at-import'", obs["classattr instance"])
    shot(page, "classattr")

    cap.label = "background"
    page.goto(BASE + "/background", wait_until="networkidle")
    wait_text(page, "#bg_flags", "is_background")
    obs["bg flags"] = txt(page, "#bg_flags")
    page.click("#late_bg"); page.wait_for_timeout(2000)
    obs["bg status"] = txt(page, "#bg_status")
    shot(page, "background")
    ctx.close()

for k, v in obs.items():
    print(f"OBS {k} = {v[:400]!r}")
cap.dump(OUT / f"{LABEL}-report.json", {"observations": obs})
