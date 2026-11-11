"""Helpers shared by the clock drivers (fixed UTC offsets valid for 2026-10-06; no tzdata here)."""
from datetime import datetime, timedelta, timezone

OFFSETS = {"US/Pacific": -7, "US/Eastern": -4, "Europe/London": 1, "Europe/Paris": 2,
           "Europe/Moscow": 3, "Asia/Tokyo": 9, "Australia/Sydney": 11}


def now_in(zone):
    return datetime.now(timezone(timedelta(hours=OFFSETS[zone])))


def expected_hour(zone):
    n = now_in(zone)
    return n, str(n.hour if n.hour <= 12 else n.hour % 12), ("AM" if n.hour < 12 else "PM")


def digital(page):
    return [t.strip() for t in page.locator(".rt-Heading").all_inner_texts() if t.strip()]


def select_text(page):
    return page.get_by_role("combobox").first.inner_text().strip()


def zone_cookie(ctx):
    return {c["name"]: c["value"] for c in ctx.cookies() if "zone" in c["name"]}


def hour_matches(parts, zone):
    """True if the digital clock hour/meridiem matches `zone` now (+-1 minute tolerance at hour edges)."""
    if len(parts) != 6:
        return False
    for delta in (0, -1, 1):
        n = now_in(zone) + timedelta(minutes=delta)
        h = str(n.hour if n.hour <= 12 else n.hour % 12)
        if parts[0] == h and parts[-1] == ("AM" if n.hour < 12 else "PM"):
            return True
    return False
