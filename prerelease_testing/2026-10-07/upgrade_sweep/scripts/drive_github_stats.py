"""Drive reflex-examples github-stats (rx.LocalStorage, recharts, bg task, 2 pages).

Usage: drive_github_stats.py <url> <outdir> <tag> <mode> <profile_dir> <stub_url>
  fresh    empty profile: add alice, bob, ghost1 (unknown user), remove bob, check
           LocalStorage JSON, reload (state restored from LocalStorage by on_load, no
           refetch), widget page /widget/alice?appearance=dark (+ reload within 60s).
  persist  SAME profile after restart/upgrade: users + stats restored from LocalStorage
           written by the previous run/version WITHOUT refetching, then add carol,
           remove ghost1, reload, widget page.
The GraphQL stub (scripts/github_stub.py) counts fetches per login (GET <stub>/count).
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, MODE, PROFILE, STUB = sys.argv[1:7]
BASE = URL.rstrip("/")
run = Run(TAG, OUT)


def counts():
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(STUB.rstrip("/") + "/count") as r:
        return json.loads(r.read())


def chips(page):
    # each selected user renders as a box: "<user>" + an "X" button
    return page.evaluate("""() => Array.from(document.querySelectorAll('button'))
        .filter(b => b.textContent === 'X').map(b => b.parentElement.textContent.replace(/X$/, ''))""")


def data(page):
    try:
        return json.loads(page.locator("textarea").first.input_value() or "[]")
    except Exception:  # noqa: BLE001
        return None


def bars(page):
    return page.locator(".recharts-bar-rectangle").count()


def ls(page):
    return page.evaluate("() => Object.assign({}, window.localStorage)")


def add_user(page, name):
    page.locator("#username").fill(name)
    page.get_by_role("button", name="Get Stats").click()


def remove_user(page, name):
    page.evaluate("""(n) => { for (const b of document.querySelectorAll('button'))
        if (b.textContent === 'X' && b.parentElement.textContent.replace(/X$/, '') === n) { b.click(); return; } }""", name)


def logins(page):
    d = data(page)
    return sorted(u["login"] for u in d) if isinstance(d, list) else None


def wait_idle(page, timeout=15):
    time.sleep(0.5)
    return wait_for(lambda: page.get_by_text("Fetching Data...").count() == 0, timeout)


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(PROFILE, executable_path=CHROMIUM,
                                               viewport={"width": 1200, "height": 1000})
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    run.attach(page)
    c0 = counts()
    run.notes["stub_counts_start"] = c0
    run.notes["localstorage_before_load"] = None
    page.goto(BASE + "/", wait_until="load")
    page.get_by_role("heading", name="Github Stats").wait_for(timeout=40000)
    wait_idle(page)
    time.sleep(2)
    run.notes["localstorage_on_load"] = ls(page)
    run.shot(page, "01_load")
    if MODE == "fresh":
        run.check("fresh: no users initially", chips(page) == [], chips(page))
        add_user(page, "alice")
        ok = wait_for(lambda: logins(page) == ["alice"], 15)
        run.check("add alice: chip + stats fetched (bg task) + textarea JSON", bool(ok) and chips(page) == ["alice"],
                  f"chips={chips(page)} logins={logins(page)}")
        add_user(page, "bob")
        ok = wait_for(lambda: logins(page) == ["alice", "bob"], 15)
        run.check("add bob: 2 users with data", bool(ok), f"chips={chips(page)} logins={logins(page)}")
        nb = wait_for(lambda: bars(page) >= 8 and bars(page), 10)
        run.check("recharts bar_chart renders bars (4 series x 2 users)", bool(nb), f"bars={bars(page)}")
        run.shot(page, "02_two_users")
        add_user(page, "ghost1")
        wait_idle(page)
        time.sleep(1)
        run.check("unknown user ghost1: chip shown, no data row", "ghost1" in chips(page) and logins(page) == ["alice", "bob"],
                  f"chips={chips(page)} logins={logins(page)}")
        remove_user(page, "bob")
        ok = wait_for(lambda: logins(page) == ["alice"] and chips(page) == ["alice", "ghost1"], 10)
        run.check("remove bob: chip + data removed", bool(ok), f"chips={chips(page)} logins={logins(page)}")
        time.sleep(1)
        store = ls(page)
        run.notes["localstorage_after_edits"] = store
        su = [v for k, v in store.items() if "selected_users_json" in k]
        us = [v for k, v in store.items() if "github_stats____state.user_stats_json" in k]
        run.check("LocalStorage holds selected_users_json + user_stats_json",
                  bool(su) and json.loads(su[0]) == ["alice", "ghost1"] and bool(us) and
                  sorted(u["login"] for u in json.loads(us[0])) == ["alice"],
                  {k: v[:80] for k, v in store.items() if "json" in k})
        run.shot(page, "03_after_remove")
    else:
        prev = sorted(json.loads(next((v for k, v in run.notes["localstorage_on_load"].items()
                                       if "selected_users_json" in k), "[]")))
        run.notes["prev_selected_users"] = prev
        ok = wait_for(lambda: sorted(chips(page)) == prev and len(prev) > 0, 15)
        run.check("persist: selected users restored from LocalStorage written by previous run",
                  bool(ok), f"chips={chips(page)} localstorage={prev}")
        prev_stats = sorted(u["login"] for u in json.loads(next((v for k, v in run.notes["localstorage_on_load"].items()
                                                                  if "github_stats____state.user_stats_json" in k), "[]")))
        ok2 = wait_for(lambda: logins(page) == prev_stats and len(prev_stats) > 0, 10)
        run.check("persist: user stats restored (textarea JSON + chart)", bool(ok2) and bars(page) >= 4 * len(prev_stats),
                  f"logins={logins(page)} expected(LocalStorage)={prev_stats} bars={bars(page)}")
        c1 = counts()
        run.check("persist: alice NOT refetched on load (data came from LocalStorage)",
                  c1.get("alice", 0) == c0.get("alice", 0), f"before={c0} after={c1}")
        run.shot(page, "02_restored")
        add_user(page, "carol")
        ok = wait_for(lambda: logins(page) == ["alice", "carol"], 15)
        run.check("persist: add carol after restart", bool(ok), f"logins={logins(page)}")
        remove_user(page, "ghost1")
        ok = wait_for(lambda: "ghost1" not in chips(page), 10)
        run.check("persist: remove ghost1", bool(ok), chips(page))
        time.sleep(1)
    # reload: on_load restores from LocalStorage
    before = counts()
    expected_chips = chips(page)
    expected_logins = logins(page)
    page.reload(wait_until="load")
    page.get_by_role("heading", name="Github Stats").wait_for(timeout=30000)
    ok = wait_for(lambda: chips(page) == expected_chips and logins(page) == expected_logins, 15)
    wait_idle(page)
    after = counts()
    refetched = {k: after.get(k, 0) - before.get(k, 0) for k in after if after.get(k, 0) != before.get(k, 0)}
    run.check("reload: users + stats restored from LocalStorage", bool(ok),
              f"chips={chips(page)} logins={logins(page)} expected={expected_chips}/{expected_logins}")
    known = [u for u in expected_logins or []]
    run.check("reload: no refetch for users already in user_stats_json",
              not any(k in refetched for k in known), f"refetched={refetched} (ghost* refetch is expected app behaviour)")
    run.notes["reload_refetched"] = refetched
    run.shot(page, "04_after_reload")
    # widget page (dynamic route + query param + rx.theme appearance + LocalStorage cache)
    before = counts()
    page.goto(BASE + "/widget/Alice?appearance=dark", wait_until="load")
    try:
        page.get_by_role("heading", name="Github Stats for alice").wait_for(timeout=30000)
        run.check("widget: dynamic route renders heading (param lower-cased)", True)
    except Exception as e:  # noqa: BLE001
        run.check("widget: dynamic route renders heading (param lower-cased)", False, e)
    nb = wait_for(lambda: bars(page) >= 4 and bars(page), 15)
    run.check("widget: chart bars + legend", bool(nb) and page.locator(".recharts-legend-wrapper").count() > 0,
              f"bars={bars(page)}")
    dark = page.evaluate("() => !!document.querySelector('.radix-themes.dark, .dark-theme')")
    themes = page.evaluate("() => Array.from(document.querySelectorAll('.radix-themes')).map(e => e.className + ' root=' + e.getAttribute('data-is-root-theme'))")
    run.notes["widget_theme_classes"] = themes
    run.check("widget: ?appearance=dark applied via nested rx.theme (pre-existing: not applied on 0.9.12)",
              "pass" if dark else "anomaly", themes)
    wl = ls(page)
    run.notes["widget_localstorage"] = {k: v[:120] for k, v in wl.items()}
    run.check("widget: last_fetch LocalStorage written", any("last_fetch" in k and v for k, v in wl.items()))
    run.shot(page, "05_widget")
    mid = counts()
    page.reload(wait_until="load")
    page.get_by_role("heading", name="Github Stats for alice").wait_for(timeout=30000)
    wait_for(lambda: bars(page) >= 4, 10)
    time.sleep(1.5)
    end = counts()
    run.notes["widget_counts"] = {"before": before, "after_first": mid, "after_reload": end}
    run.check("widget: reload within 60s served from LocalStorage cache (no refetch)",
              end.get("alice", 0) == mid.get("alice", 0) and bars(page) >= 4,
              f"first load fetched {mid.get('alice',0)-before.get('alice',0)}, reload fetched {end.get('alice',0)-mid.get('alice',0)}, bars={bars(page)}")
    run.notes["final_localstorage"] = {k: v[:200] for k, v in ls(page).items()}
    ctx.close()

sys.exit(run.finish())
