"""Hammer the #6920 race: foreground clicks vs background task completions.

Usage: drive_race.py <frontend_url> <screenshot_dir> [rounds]

Per round: fire a one-shot background task (two locked writes + long tail),
click "inc both" (client_state increment + server counter increment) rapidly
until the background task reports completion, then stop clicking and assert
the displayed counter reaches the exact click count WITHOUT further writes.
A stale counter that catches up only after a "poke" click is the #6920
lost-delta signature.

Then: a 4s background poller at 10 Hz with 30 clicks spread across it.
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3180/"
SHOTDIR = sys.argv[2] if len(sys.argv) > 2 else "."
ROUNDS = int(sys.argv[3]) if len(sys.argv) > 3 else 20
# Which increment button to hammer: btn-inc-both (sync handler) or
# btn-inc-both-io (async handler awaiting after the write -- the realistic
# pre-#6920 lost-delta shape).
BTN = sys.argv[4] if len(sys.argv) > 4 else "btn-inc-both"

COUNTER_OBSERVER = """
() => {
  window.__cvals = [];
  const el = document.querySelector('#counter');
  const mo = new MutationObserver(() => {
    window.__cvals.push({t: performance.now(), v: el.textContent});
  });
  mo.observe(el, {childList: true, characterData: true, subtree: true});
}
"""

console_msgs = []
failed_requests = []
bad_responses = []

results = {"rounds": [], "stale_rounds": 0, "poke_recovered": 0}


def txt(page, elem_id):
    return page.locator(f"#{elem_id}").inner_text().strip()


def wait_text(page, elem_id, expected, timeout_s=5.0, poll=0.05):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if txt(page, elem_id) == expected:
            return True
        time.sleep(poll)
    return False


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append((m.type, m.text)))
    page.on("requestfailed", lambda r: failed_requests.append((r.url, str(r.failure))))
    page.on(
        "response",
        lambda r: bad_responses.append((r.status, r.url)) if r.status >= 400 else None,
    )
    page.goto(URL, wait_until="networkidle", timeout=90000)

    # Wait for hydration: reset, then a probe click must move the counter.
    page.wait_for_selector("#counter", timeout=30000)
    deadline = time.monotonic() + 30
    hydrated = False
    while time.monotonic() < deadline:
        page.click("#btn-reset")
        time.sleep(0.3)
        if txt(page, "counter") == "0":
            page.click("#btn-inc")
            if wait_text(page, "counter", "1", timeout_s=3):
                hydrated = True
                break
        time.sleep(0.5)
    if not hydrated:
        print("FATAL: app never hydrated / responded to clicks")
        page.screenshot(path=f"{SHOTDIR}/race_hydration_fail.png")
        sys.exit(2)

    page.click("#btn-reset")
    wait_text(page, "counter", "0", timeout_s=5)
    # client_state var has no server reset; track it from its current value.
    cs_base = int(txt(page, "cs-clicks"))
    page.evaluate(COUNTER_OBSERVER)

    clicks = 0
    for r in range(1, ROUNDS + 1):
        page.click("#btn-bg-once")
        round_clicks = 0
        # Click until this round's bg task completes (bg-runs == r), max 40.
        while round_clicks < 40 and txt(page, "bg-runs") != str(r):
            page.click(f"#{BTN}")
            round_clicks += 1
        # A few trailing clicks right as/after completion (race the tail).
        for _ in range(3):
            page.click(f"#{BTN}")
            round_clicks += 1
        clicks += round_clicks
        if not wait_text(page, "bg-runs", str(r), timeout_s=5):
            print(f"round {r}: bg-runs never reached {r} (got {txt(page, 'bg-runs')})")
        # Quiescence: no further writes. The counter must catch up on its own.
        ok = wait_text(page, "counter", str(clicks), timeout_s=3)
        entry = {"round": r, "clicks_total": clicks, "ok": ok}
        if not ok:
            stale_val = txt(page, "counter")
            entry["stale_value"] = stale_val
            page.screenshot(path=f"{SHOTDIR}/race_stale_round{r}.png")
            # wait longer to prove it is genuinely stuck, not slow
            time.sleep(2)
            entry["still_stale_after_2s"] = txt(page, "counter") != str(clicks)
            # poke: one more write should flush the missed value
            page.click(f"#{BTN}")
            clicks += 1
            entry["poke_recovers"] = wait_text(page, "counter", str(clicks), timeout_s=3)
            results["stale_rounds"] += 1
            if entry["poke_recovers"]:
                results["poke_recovered"] += 1
        results["rounds"].append(entry)

    # Verify client_state clicks all landed and bg counters are exact.
    results["final_counter"] = txt(page, "counter")
    results["expected_counter"] = str(clicks)
    results["cs_clicks"] = str(int(txt(page, "cs-clicks")) - cs_base)
    # 1 probe click used #btn-inc (not both); pokes and round clicks used both.
    results["expected_cs_clicks"] = str(clicks)
    wait_text(page, "bg-ticks", str(2 * ROUNDS), timeout_s=5)
    results["bg_ticks"] = txt(page, "bg-ticks")
    results["expected_bg_ticks"] = str(2 * ROUNDS)
    # Soft signal: counter values whose delta never rendered. React render
    # batching can also skip values, so this is advisory, not a hard failure.
    cvals = [int(c["v"]) for c in page.evaluate("() => window.__cvals") if c["v"].isdigit()]
    seen = set(cvals)
    results["counter_values_never_rendered"] = [
        v for v in range(1, clicks + 1) if v not in seen
    ]
    page.screenshot(path=f"{SHOTDIR}/race_after_rounds.png")

    # Poller phase: 40 ticks at 10 Hz (~4s); click 30 times spread across it.
    page.click("#btn-reset")
    wait_text(page, "counter", "0", timeout_s=5)
    page.click("#btn-poller")
    poller_clicks = 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < 4.2:
        page.click(f"#{BTN}")
        poller_clicks += 1
        time.sleep(0.09)
    ok = wait_text(page, "poller-running", "false", timeout_s=10)
    results["poller_stopped"] = ok
    results["poller_counter_ok"] = wait_text(page, "counter", str(poller_clicks), timeout_s=3)
    results["poller_final_counter"] = txt(page, "counter")
    results["poller_expected_counter"] = str(poller_clicks)
    wait_text(page, "poller-ticks", "40", timeout_s=5)
    results["poller_ticks"] = txt(page, "poller-ticks")
    # window (uncached async computed var) should equal bg_ticks + poller_ticks
    time.sleep(0.5)
    results["window"] = txt(page, "window")
    results["window_expected"] = str(int(txt(page, "bg-ticks")) + int(txt(page, "poller-ticks")))
    page.screenshot(path=f"{SHOTDIR}/race_after_poller.png")
    browser.close()

print("RESULTS:", json.dumps(results, indent=1))
interesting_console = [
    (t, m)
    for t, m in console_msgs
    if not any(
        s in m
        for s in ("HydrateFallback", "[vite]", "React DevTools", "Download the React DevTools")
    )
]
print("CONSOLE:", json.dumps(interesting_console[:40], default=str))
print("FAILED_REQUESTS:", json.dumps(failed_requests, default=str))
print("HTTP_4XX_5XX:", json.dumps(bad_responses))
verdict_ok = (
    results["stale_rounds"] == 0
    and results["final_counter"] == results["expected_counter"]
    and results["cs_clicks"] == results["expected_cs_clicks"]
    and results["bg_ticks"] == results["expected_bg_ticks"]
    and results["poller_counter_ok"]
)
print("VERDICT:", "PASS" if verdict_ok else "FAIL")
sys.exit(0 if verdict_ok else 1)
