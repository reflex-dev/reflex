"""Drive the linkinbio example (no LD_SDK_KEY -> the 'Bio Page if False' branch renders).

Checks: heading/bio text, 4 external link buttons with correct hrefs + target,
lucide icons rendered via dynamic tag, radix avatar, hover style, popup on click,
and rx.moment (react-moment) rendering HH:mm:ss + ticking on its 3s interval +
on_change payloads sent to the backend (captured from the /_event websocket).

Usage: python linkinbio_drive.py <url> <shot_prefix> <report_json>
"""

import json
import re

from drive_common import run

EXPECTED_LINKS = [
    ("Website", "https://reflex.dev"),
    ("Twitter", "https://twitter.com/getreflex"),
    ("GitHub", "https://github.com/reflex-dev/reflex-examples"),
    ("LinkedIn", "https://www.linkedin.com/company/reflex-dev"),
]
TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def driver(page, cap):
    SHOT = cap.shot
    page.goto(cap.url, wait_until="networkidle", timeout=60000)
    try:
        page.get_by_role("heading", name="Bio Page if False").wait_for(timeout=30000)
        cap.step("false_branch_renders", True, "heading 'Bio Page if False' visible (no LD_SDK_KEY)")
    except Exception as e:
        cap.step("false_branch_renders", False, repr(e))
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{SHOT}-initial.png")

    try:
        texts = page.locator("p, .rt-Text").all_inner_texts()
        cap.step("bio_texts", any("dub.link/pronouns" in t for t in texts) and any("< insert bio here >" in t for t in texts), f"texts={texts}")
    except Exception as e:
        cap.step("bio_texts", False, repr(e))

    try:
        links = page.locator("a[href^='http']").evaluate_all(
            "els => els.map(a => [a.innerText.trim(), a.getAttribute('href'), a.getAttribute('target'), a.getAttribute('rel'), a.querySelectorAll('svg').length])")
        # prod mode appends the "Built with Reflex" badge (an extra <a href=https://reflex.dev>); not part of the app
        badge = [l for l in links if l[0] == "Built with Reflex"]
        links = [l for l in links if l[0] != "Built with Reflex"]
        cap.step("built_with_reflex_badge", True, f"badge links present={len(badge)} (expected 1 in prod, 0 in dev)")
        got = [(t, h) for t, h, *_ in links]
        ok = got == EXPECTED_LINKS and all(tg == "_blank" for _, _, tg, _, _ in links)
        cap.step("link_buttons", ok, f"links={links}")
        cap.step("link_icons_rendered", all(n == 1 for *_, n in links) and len(links) == 4, f"svg-per-link={[n for *_, n in links]}")
    except Exception as e:
        cap.step("link_buttons", False, repr(e))

    try:
        av = page.locator(".rt-AvatarRoot")
        cap.step("avatar_renders", av.count() == 1, f"avatar roots={av.count()} inner={av.first.inner_html()[:200] if av.count() else ''}")
    except Exception as e:
        cap.step("avatar_renders", False, repr(e))

    try:
        btn = page.get_by_role("link", name="Website").locator("button")
        before = btn.evaluate("e => getComputedStyle(e).backgroundColor")
        btn.hover(); page.wait_for_timeout(600)
        after = btn.evaluate("e => getComputedStyle(e).backgroundColor")
        cap.step("button_hover_style", before != after, f"{before} -> {after}")
        page.mouse.move(5, 5)
    except Exception as e:
        cap.step("button_hover_style", False, repr(e))

    # rx.moment: react-moment renders a <time> element
    try:
        tm = page.locator("time")
        tm.first.wait_for(timeout=15000)
        html = tm.first.evaluate("e => e.outerHTML")
        txt = tm.first.inner_text().strip()
        browser_now = page.evaluate("new Date().toTimeString().slice(0,8)")
        def secs(s):
            h, m, x = (int(v) for v in s.split(":")); return h * 3600 + m * 60 + x
        close = TIME_RE.match(txt) and abs(secs(txt) - secs(browser_now)) <= 6
        cap.step("moment_renders_time", tm.count() == 1 and bool(TIME_RE.match(txt)), f"count={tm.count()} text={txt!r} outerHTML={html!r}")
        cap.step("moment_matches_browser_clock", bool(close), f"moment={txt!r} browser={browser_now!r}")
        page.wait_for_timeout(3600)
        txt2 = tm.first.inner_text().strip()
        cap.step("moment_interval_ticks", txt2 != txt and bool(TIME_RE.match(txt2)), f"t1={txt!r} t2={txt2!r} (interval=3000)")
    except Exception as e:
        cap.step("moment_renders_time", False, repr(e))
    page.screenshot(path=f"{SHOT}-after3s.png")

    # wait for a couple more on_change events, then inspect what the frontend sent
    page.wait_for_timeout(3500)
    frames = [f for f in cap.event_frames if "on_update" in f]
    payloads = []
    for f in frames:
        try:
            body = json.loads(f[f.index("["):]) if "[" in f else None
            tag = f.split(" ", 1)[0] if f.startswith("ws#") else ""
            if body and isinstance(body, list) and len(body) > 1 and isinstance(body[1], dict):
                if "on_update" in body[1].get("name", ""):
                    payloads.append((tag, body[1].get("payload", {}).get("date")))
        except Exception:
            payloads.append(f"UNPARSED:{f[:200]}")
    cap.step("moment_on_change_events_sent", len(frames) >= 2, f"on_update frames={len(frames)} payloads={payloads[:5]}")
    # mount-time behaviour: react-moment 1.2.2 only fires onChange from its interval (first event ~interval ms
    # after mount); react-moment 2.0.2 also fires onChange once on mount (twice under React StrictMode in dev).
    dates = [re.search(r'"date":"([^"]+)"', f).group(1) for f in frames if '"date":"' in f]
    dups = [d for i, d in enumerate(dates) if i and d == dates[i - 1]]
    cap.step("moment_on_change_mount_duplicates", True,
             f"on_update dates={dates} consecutive-duplicate dates={dups} (0.9.10/react-moment 1.2.2: none; react-moment 2.0.2 dev: one duplicate per mount)")

    # click opens a new tab (target=_blank)
    try:
        with page.context.expect_page(timeout=8000) as pop:
            page.get_by_role("link", name="Website").click()
        popup = pop.value
        page.wait_for_timeout(1500)
        cap.step("link_click_opens_new_tab", True, f"popup url={popup.url!r}")
        popup.close()
    except Exception as e:
        cap.step("link_click_opens_new_tab", False, repr(e))

    try:
        page.reload(wait_until="networkidle")
        page.get_by_role("heading", name="Bio Page if False").wait_for(timeout=30000)
        tm = page.locator("time"); tm.first.wait_for(timeout=15000)
        a = tm.first.inner_text().strip(); page.wait_for_timeout(3600); b = tm.first.inner_text().strip()
        cap.step("reload_rerenders_and_ticks", bool(TIME_RE.match(a)) and a != b, f"a={a!r} b={b!r}")
    except Exception as e:
        cap.step("reload_rerenders_and_ticks", False, repr(e))
    page.screenshot(path=f"{SHOT}-reload.png")


run(driver)
