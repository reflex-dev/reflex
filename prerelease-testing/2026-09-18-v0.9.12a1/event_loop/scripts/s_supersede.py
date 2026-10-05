"""Scenario: #7168 supersedes ordering. Usage: s_supersede.py <base_url> <outdir>"""

import sys
import time

sys.argv = [sys.argv[0], "supersede", *sys.argv[1:]]
from playwright.sync_api import sync_playwright  # noqa: E402
from wsdrive import BASE, OUT, attach, dump, log, txt  # noqa: E402


def wait_quiet(page, seconds=3.0):
    page.wait_for_timeout(int(seconds * 1000))


def logval(page):
    return txt(page, "#sslog")


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    attach(page, "c1")
    page.goto(f"{BASE}/supersede", wait_until="networkidle")
    page.wait_for_selector("#sslog", timeout=30000)
    time.sleep(1.0)

    def case(name, steps, settle=4.0):
        page.click("#clear")
        page.wait_for_timeout(400)
        for sel, delay in steps:
            page.click(sel)
            page.wait_for_timeout(int(delay * 1000))
        wait_quiet(page, settle)
        log(f"[{name}] {logval(page)}")

    # (a) two roots of the same superseding handler: newest wins
    case("a-roots", [("#rootA", 0.4), ("#rootB", 0.0)])

    # (b) shared superseding child under two DIFFERENT root chains (#7041)
    case("b-chains", [("#chainA", 0.4), ("#chainB", 0.0)])

    # (c) sibling fan-out from one parent: both must run
    case("c-fanout", [("#fanout", 0.0)])

    # (d) self-chaining superseding poll loop, restarted mid-run
    page.click("#clear")
    page.wait_for_timeout(300)
    page.click("#startpoll")
    page.wait_for_timeout(1400)
    mid = logval(page)
    page.click("#startpoll")  # restart mid-run
    page.wait_for_timeout(1400)
    page.click("#stoppoll")
    wait_quiet(page, 1.5)
    log(f"[d-poll] mid={mid!r} final={logval(page)!r}")

    # (e) stale chain enqueues refresh AFTER a newer chain already did
    page.click("#clear")
    page.wait_for_timeout(300)
    page.click("#slow")  # 3s before it enqueues refresh("stale")
    page.wait_for_timeout(1500)
    page.click("#rootB")  # newer root generation claims the slot
    wait_quiet(page, 6.0)
    log(f"[e-stale] {logval(page)!r}")

    # (f) foreground superseding handlers
    case("f-foreground", [("#fgA", 0.4), ("#fgB", 0.0)], settle=4.0)

    # (g) mixing: foreground A then background B (different handler names)
    case("g-mixed", [("#fgA", 0.3), ("#rootB", 0.0)], settle=4.0)

    # (h) two roots from two different browser contexts must not cancel each other
    ctx2 = b.new_context()
    page2 = ctx2.new_page()
    attach(page2, "c2")
    page2.goto(f"{BASE}/supersede", wait_until="networkidle")
    page2.wait_for_selector("#sslog", timeout=30000)
    page.click("#clear")
    page2.click("#clear")
    page.wait_for_timeout(400)
    page.click("#rootA")
    page2.click("#rootB")
    wait_quiet(page, 4.0)
    log(f"[h-two-clients] c1={logval(page)!r} c2={txt(page2, '#sslog')!r}")

    page.screenshot(path=str(OUT / "supersede_final.png"))
    dump("supersede")
    from wsdrive import console_log, errors, net  # noqa: E402

    log("== console ==")
    for line in console_log:
        if any(
            s in line
            for s in ("Hey developer", "connecting", "connected", "React DevTools")
        ):
            continue
        log("  ", line)
    log("== pageerrors ==", errors)
    log("== net ==", net)
    ctx.close()
    ctx2.close()
    b.close()
