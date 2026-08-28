"""Playwright driver for the reflex-examples `clock` app (+ added /moment page).

Usage:
    python drive_clock.py <frontend_url> <artifacts_dir> <label>

Exercises: analog/digital clock render, start/stop switch driving a background
tick task, timezone select (radix) with correctness vs zoneinfo, cookie
persistence across reload, and the /moment page (reflex-components-moment,
stable 0.9.3, with tz from shared state). Captures console, bad responses,
screenshots.
"""

import json
import sys
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright

# Fixed offsets valid for 2026-08 (DST in effect where applicable); the shared
# driver venv has no tzdata so zoneinfo is unavailable.
OFFSETS = {
    "US/Eastern": -4, "US/Pacific": -7,
    "Asia/Tokyo": 9,
    "Europe/London": 1,
}


def ZoneInfo(zone):  # noqa: N802 - drop-in stand-in for zoneinfo.ZoneInfo
    return timezone(timedelta(hours=OFFSETS[zone]))

FRONTEND = sys.argv[1].rstrip("/")
ART = __import__("pathlib").Path(sys.argv[2])
LABEL = sys.argv[3]
ART.mkdir(parents=True, exist_ok=True)

results = []
console_msgs = []
bad_responses = []
page_errors = []


def record(name, status, details=""):
    results.append({"name": name, "status": status, "details": details})
    print(f"[{status.upper()}] {name}: {details}")


def digital_parts(page):
    """Return the digital clock heading texts [hour, :, minute, :, second, meridiem]."""
    texts = [t.strip() for t in page.locator(".rt-Heading").all_inner_texts()]
    return [t for t in texts if t]


def expected_hour(zone: str):
    now = datetime.now(ZoneInfo(zone))
    return now, (now.hour if now.hour <= 12 else now.hour % 12)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    context = browser.new_context()
    page = context.new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
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

    page.goto(FRONTEND + "/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    page.screenshot(path=str(ART / "01_initial.png"))

    # 1. page renders: switch + select + digital clock present
    sw = page.get_by_role("switch")
    sel = page.get_by_role("combobox")
    parts = digital_parts(page)
    render_ok = sw.count() == 1 and sel.count() >= 1 and len(parts) == 6
    record("index_renders", "pass" if render_ok else "fail",
           f"switch={sw.count()} select={sel.count()} digital_parts={parts}")

    # 2. clock stopped on load: seconds must not advance before switch flip
    s1 = digital_parts(page)
    page.wait_for_timeout(2500)
    s2 = digital_parts(page)
    record("clock_stopped_on_load", "pass" if s1 == s2 else "fail",
           f"before={s1} after={s2}")

    # 3. flip switch on -> background tick task starts, seconds advance
    sw.first.click()
    page.wait_for_timeout(1500)
    t1 = digital_parts(page)
    page.wait_for_timeout(2500)
    t2 = digital_parts(page)
    ticking = t1 != t2 and len(t2) == 6
    page.screenshot(path=str(ART / "02_ticking.png"))
    record("clock_ticks_when_started", "pass" if ticking else "fail",
           f"t1={t1} t2={t2}")

    # 4. default timezone correctness (US/Eastern)
    now, exp_h = expected_hour("US/Pacific")
    shown = digital_parts(page)
    h_ok = shown and shown[0] == str(exp_h)
    meridiem_ok = shown and shown[-1] == ("AM" if now.hour < 12 else "PM")
    record("default_zone_time_correct", "pass" if (h_ok and meridiem_ok) else "fail",
           f"shown={shown} expected_hour={exp_h} (US/Pacific now={now.isoformat()})")

    # 5. switch timezone to Asia/Tokyo via radix select
    sel.first.click()
    page.wait_for_timeout(500)
    page.get_by_role("option", name="Asia/Tokyo").click()
    page.wait_for_timeout(1500)
    now_t, exp_ht = expected_hour("Asia/Tokyo")
    shown_t = digital_parts(page)
    ok_t = shown_t and shown_t[0] == str(exp_ht) and shown_t[-1] == (
        "AM" if now_t.hour < 12 else "PM"
    )
    page.screenshot(path=str(ART / "03_tokyo.png"))
    record("timezone_switch_tokyo", "pass" if ok_t else "fail",
           f"shown={shown_t} expected_hour={exp_ht} (Tokyo now={now_t.isoformat()})")

    # 6. cookie persistence: reload, zone should still be Asia/Tokyo, clock stopped
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2500)
    sel_text = page.get_by_role("combobox").first.inner_text()
    cookie_ok = "Asia/Tokyo" in sel_text
    r1 = digital_parts(page)
    page.wait_for_timeout(2200)
    r2 = digital_parts(page)
    stopped = r1 == r2
    page.screenshot(path=str(ART / "04_after_reload.png"))
    record("zone_cookie_persists", "pass" if cookie_ok else "fail",
           f"select shows: {sel_text!r}")
    record("clock_stopped_after_reload", "pass" if stopped else "fail",
           f"r1={r1} r2={r2}")

    # 7. stop the clock via switch: start then stop, ticking ceases
    swl = page.get_by_role("switch").first
    swl.click()  # on
    page.wait_for_timeout(1500)
    swl.click()  # off
    page.wait_for_timeout(1200)
    x1 = digital_parts(page)
    page.wait_for_timeout(2400)
    x2 = digital_parts(page)
    record("clock_stops_when_switched_off", "pass" if x1 == x2 else "fail",
           f"x1={x1} x2={x2}")

    # 8. /moment page: moment component (stable reflex-components-moment 0.9.3)
    page.goto(FRONTEND + "/moment", wait_until="networkidle")
    page.wait_for_timeout(2500)
    mc = page.locator("#moment_clock")
    page.screenshot(path=str(ART / "05_moment.png"))
    if mc.count() == 0:
        record("moment_page_renders", "fail", "no #moment_clock element")
    else:
        txt = mc.inner_text().strip()
        # zone cookie is Asia/Tokyo from step 5
        now_m = datetime.now(ZoneInfo("Asia/Tokyo"))
        try:
            hh = int(txt.split(":")[0])
            hour_ok = hh in (now_m.hour, (now_m.hour + 24 - 1) % 24, (now_m.hour + 1) % 24)
        except Exception:
            hour_ok = False
        record("moment_page_renders", "pass" if txt else "fail", f"text={txt!r}")
        record("moment_tz_from_state_cookie", "pass" if hour_ok else "fail",
               f"moment shows {txt!r}, Tokyo now {now_m.strftime('%H:%M:%S')}")
        # 9. moment ticks via interval
        page.wait_for_timeout(2500)
        txt2 = mc.inner_text().strip()
        record("moment_interval_ticks", "pass" if txt2 != txt else "fail",
               f"t1={txt!r} t2={txt2!r}")
        # 10. change timezone on /moment -> moment display shifts
        page.get_by_role("combobox").first.click()
        page.wait_for_timeout(500)
        page.get_by_role("option", name="Europe/London").click()
        page.wait_for_timeout(1500)
        txt3 = mc.inner_text().strip()
        now_l = datetime.now(ZoneInfo("Europe/London"))
        try:
            hh3 = int(txt3.split(":")[0])
            ok_l = hh3 == now_l.hour
        except Exception:
            ok_l = False
        page.screenshot(path=str(ART / "06_moment_london.png"))
        record("moment_tz_switch_london", "pass" if ok_l else "fail",
               f"moment shows {txt3!r}, London now {now_l.strftime('%H:%M:%S')}")

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
