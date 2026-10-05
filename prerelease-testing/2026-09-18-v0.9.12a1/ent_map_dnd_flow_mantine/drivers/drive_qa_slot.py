"""Drive the mantine QA slot page: PR #6850 Slot transparency + PR #7068 router vars.

Usage: python drive_qa_slot.py <base_url> <shots_dir>
"""

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE, SHOTS = sys.argv[1], pathlib.Path(sys.argv[2])
SHOTS.mkdir(parents=True, exist_ok=True)
results, console, page_errors, net_fail = [], [], [], []
BENIGN = ("Hey developer", "connecting...", "connected", "React DevTools", "Download the React")


def rec(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} :: {detail}")


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: console.append((m.type, m.text)))
    pg.on("pageerror", lambda e: page_errors.append(str(e)))
    pg.on("requestfailed", lambda r: net_fail.append((r.url, r.failure)))
    pg.on("response", lambda r: net_fail.append((r.url, r.status)) if r.status >= 400 else None)

    pg.goto(f"{BASE}/qa-slot?qa=1", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=SHOTS / "01_loaded.png", full_page=True)

    # --- PR #7068: router-derived computed var reaches the page
    echo = pg.locator("#route-echo").inner_text()
    rec("router_computed_var", "/qa-slot" in echo and "qa=1" in echo, echo)

    # --- PR #6850: the Slot parent's injected name/id must reach the memoized input
    named = pg.locator("#qa-form input[name='core_name']")
    rec("slot_injects_name_onto_memo_input", named.count() == 1,
        f"input[name=core_name] count={named.count()}")
    all_inputs = pg.eval_on_selector_all(
        "#qa-form input",
        "els => els.map(e => ({id: e.id, name: e.name, type: e.type}))",
    )
    rec("form_input_attrs", True, json.dumps(all_inputs))

    # fill and submit -> on_submit must see the field
    if named.count():
        named.fill("Ada")
    else:
        pg.locator("#core-input").fill("Ada")
    pg.locator("#submit-btn").click()
    pg.wait_for_timeout(1200)
    sub = pg.locator("#submitted").inner_text()
    rec("form_submit_delivers_field", "core_name" in sub and "Ada" in sub, sub)
    pg.screenshot(path=SHOTS / "02_submitted.png", full_page=True)

    # --- mantine widget bound to State + rx.foreach + @rx.memo chips
    chips_before = pg.locator("#chips .mantine-Pill-root, #chips [class*='Pill']").count()
    pg.locator("#add-tag").click()
    pg.wait_for_timeout(900)
    pg.locator("#add-tag").click()
    pg.wait_for_timeout(900)
    chips_after = pg.locator("#chips .mantine-Pill-root, #chips [class*='Pill']").count()
    rec("foreach_memo_chips_grow", chips_after > chips_before, f"{chips_before} -> {chips_after}")
    badge = pg.locator("#many-badge").count()
    rec("rx_cond_badge_flips", badge == 1, f"many-badge count={badge}")
    mt = pg.eval_on_selector_all(
        "#mantine-tags [class*='Pill'], .mantine-TagsInput-pill",
        "els => els.map(e => e.textContent)",
    )
    rec("mantine_tags_input_reflects_state", len(mt) >= 4, json.dumps(mt))

    # --- event chain
    pg.locator("#chain-btn").click()
    pg.wait_for_timeout(1000)
    cl = pg.locator("#chain-log").inner_text()
    rec("event_chain_runs_both_links", "one" in cl and "two" in cl, cl)

    # --- background task
    pg.locator("#bg-btn").click()
    pg.wait_for_timeout(2500)
    bt = pg.locator("#bg-ticks").inner_text()
    rec("background_task_streams", "3" in bt, bt)

    # --- client_state hover counter
    for _ in range(3):
        pg.locator("#hover-box").hover()
        pg.mouse.move(0, 0)
        pg.wait_for_timeout(120)
    hv = pg.locator("#hovers").inner_text()
    rec("client_state_hover_counter", any(c.isdigit() and c != "0" for c in hv), hv)

    # --- SPA navigation: router vars must update, then come back
    pg.locator("#nav-dates").click()
    pg.wait_for_timeout(1800)
    on_dates = pg.locator("[class*='mantine-']").count()
    rec("spa_nav_to_dates", on_dates > 50, f"mantine elements={on_dates}")
    pg.go_back()
    pg.wait_for_timeout(1800)
    echo2 = pg.locator("#route-echo").inner_text()
    rec("router_var_after_spa_back", "/qa-slot" in echo2, echo2)
    pg.screenshot(path=SHOTS / "03_after_nav.png", full_page=True)

    # --- hard reload on the deep route
    pg.goto(f"{BASE}/qa-slot?qa=2", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    echo3 = pg.locator("#route-echo").inner_text()
    rec("router_var_after_hard_reload", "qa=2" in echo3, echo3)
    pg.screenshot(path=SHOTS / "04_reload.png", full_page=True)

    b.close()

bad = [c for c in console if c[0] in ("error", "warning") and not any(x in c[1] for x in BENIGN)]
print("\n=== CONSOLE (non-benign) ===")
for t, m in bad:
    print(f"  [{t}] {m[:300]}")
print("=== PAGE ERRORS ===")
for e in page_errors:
    print("  " + e[:300])
print("=== NET FAILURES ===")
for u, s in net_fail:
    print(f"  {s} {u[:160]}")
(SHOTS / "results.json").write_text(json.dumps(
    {"results": results, "console": bad, "page_errors": page_errors,
     "net_fail": [(u, str(s)) for u, s in net_fail]}, indent=2))
passed = sum(1 for _, ok, _ in results if ok)
print(f"\nSUMMARY: {passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
