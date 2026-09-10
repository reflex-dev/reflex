"""Drive the stock clock example: render, background-task ticking via switch, radix
select timezone (correctness vs fixed offsets), rx.Cookie persistence across reload,
stop ticking.

Usage: python clock_drive.py <url> <shot_prefix> <report_json>
"""

from datetime import datetime, timedelta, timezone

from drive_common import run

# Fixed offsets valid for 2026-09 (DST in effect); driver venv has no tzdata.
OFFSETS = {"US/Pacific": -7, "US/Eastern": -4, "Asia/Tokyo": 9, "Europe/London": 1}


def now_in(zone):
    now = datetime.now(timezone(timedelta(hours=OFFSETS[zone])))
    return now, (now.hour if now.hour <= 12 else now.hour % 12), ("AM" if now.hour < 12 else "PM")


def driver(page, cap):
    SHOT = cap.shot

    def digital():
        return [t.strip() for t in page.locator(".rt-Heading").all_inner_texts() if t.strip()]

    page.goto(cap.url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2500)
    page.screenshot(path=f"{SHOT}-initial.png")
    sw = page.get_by_role("switch")
    sel = page.get_by_role("combobox")
    parts = digital()
    cap.step("index_renders", sw.count() == 1 and sel.count() >= 1 and len(parts) == 6,
             f"switch={sw.count()} select={sel.count()} digital={parts}")
    # analog hands: 3 rotated dividers
    try:
        rots = page.locator(".rt-Separator").evaluate_all(
            "els => els.map(e => getComputedStyle(e).transform).filter(t => t && t !== 'none')")
        cap.step("analog_hands_render", len(rots) == 3 and all(r.startswith("matrix(") for r in rots), f"computed transforms={rots}")
    except Exception as e:
        cap.step("analog_hands_render", False, repr(e))

    s1 = digital(); page.wait_for_timeout(2500); s2 = digital()
    cap.step("clock_stopped_on_load", s1 == s2, f"before={s1} after={s2}")

    sw.first.click(); page.wait_for_timeout(1500)
    t1 = digital(); page.wait_for_timeout(2500); t2 = digital()
    page.screenshot(path=f"{SHOT}-ticking.png")
    cap.step("clock_ticks_when_started", t1 != t2 and len(t2) == 6, f"t1={t1} t2={t2}")

    now, h, mer = now_in("US/Pacific")
    shown = digital()
    cap.step("default_zone_time_correct", bool(shown) and shown[0] == str(h) and shown[-1] == mer,
             f"shown={shown} expected_hour={h} {mer} (US/Pacific now={now.isoformat()})")

    sel.first.click(); page.wait_for_timeout(500)
    page.get_by_role("option", name="Asia/Tokyo").click(); page.wait_for_timeout(1500)
    now_t, h_t, mer_t = now_in("Asia/Tokyo")
    shown_t = digital()
    page.screenshot(path=f"{SHOT}-tokyo.png")
    cap.step("timezone_switch_tokyo", bool(shown_t) and shown_t[0] == str(h_t) and shown_t[-1] == mer_t,
             f"shown={shown_t} expected_hour={h_t} {mer_t} (Tokyo now={now_t.isoformat()})")

    page.reload(wait_until="networkidle"); page.wait_for_timeout(2500)
    sel_text = page.get_by_role("combobox").first.inner_text()
    cookies = [c for c in page.context.cookies() if "zone" in c["name"]]
    r1 = digital(); page.wait_for_timeout(2200); r2 = digital()
    page.screenshot(path=f"{SHOT}-reload.png")
    cap.step("zone_cookie_persists", "Asia/Tokyo" in sel_text, f"select shows {sel_text!r}; cookies={[(c['name'], c['value']) for c in cookies]}")
    cap.step("clock_stopped_after_reload", r1 == r2, f"r1={r1} r2={r2}")

    swl = page.get_by_role("switch").first
    swl.click(); page.wait_for_timeout(1500)
    swl.click(); page.wait_for_timeout(1200)
    x1 = digital(); page.wait_for_timeout(2400); x2 = digital()
    cap.step("clock_stops_when_switched_off", x1 == x2, f"x1={x1} x2={x2}")

    # switch to London and start again: ticking in the new zone
    page.get_by_role("combobox").first.click(); page.wait_for_timeout(500)
    page.get_by_role("option", name="Europe/London").click(); page.wait_for_timeout(1000)
    swl.click(); page.wait_for_timeout(2000)
    now_l, h_l, mer_l = now_in("Europe/London")
    shown_l = digital()
    cap.step("timezone_switch_london_ticking", bool(shown_l) and shown_l[0] == str(h_l) and shown_l[-1] == mer_l,
             f"shown={shown_l} expected_hour={h_l} {mer_l} (London now={now_l.isoformat()})")
    page.screenshot(path=f"{SHOT}-london.png")
    swl.click(); page.wait_for_timeout(800)  # stop the background task before leaving


run(driver)
