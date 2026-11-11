"""Keep ONE logged-in PySocial tab (user dave) open across server stop -> in-place upgrade -> restart.

Usage: stale_tab_twitter.py <url> <outdir> <tag> <ctldir>
Control files in <ctldir>: operator touches `down` after stopping the old server and `up` once the
new version serves; this script writes `ready` (dave signed up, tweeted, followed alice) and `done`.
Checks that dave is still logged in after the upgrade WITHOUT re-login (server-side State.user
restored from the 0.9.12-written .states pickle for the tab's token), that the tab can post through
the new backend, and that a manual reload keeps the session.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402
from tw_common import (  # noqa: E402
    click_follow, composer_avatar, feed_tweets, list_under_heading, login, new_page, on_home, on_login,
    path_of, post_tweet, pump_wait, search_user_results, signup, token_of, wait_home, wait_login,
)

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, CTL = sys.argv[1:5]
URL = URL.rstrip("/")
CTL = Path(CTL)
CTL.mkdir(parents=True, exist_ok=True)
run = Run(TAG, OUT)
EXPECT_SESSION = os.environ.get("QA_EXPECT_SESSION", "1") == "1"
USER = os.environ.get("QA_STALE_USER", "dave")
FOLLOW = os.environ.get("QA_STALE_FOLLOW", "alice")
run.notes["expect_session"] = EXPECT_SESSION
dialogs: list = []
run.notes["dialogs"] = dialogs


def wait_file(page, name, timeout=3600):
    end = time.time() + timeout
    while time.time() < end:
        if (CTL / name).exists():
            return True
        page.wait_for_timeout(500)
    return False


def snapshot(page, label):
    info = {
        "marker": page.evaluate("() => window.__qa_marker || null"),
        "path": path_of(page),
        "on_home": on_home(page),
        "on_login": on_login(page),
        "avatar": composer_avatar(page),
        "token": token_of(page),
        "feed": feed_tweets(page)[:6],
        "following": list_under_heading(page, "Following"),
        "toasts": page.locator("[data-sonner-toast]").all_inner_texts(),
        "body_tail": page.inner_text("body")[-300:],
    }
    run.notes[label] = info
    run.shot(page, label)
    print(label, info, flush=True)
    return info


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx, page = new_page(browser, run, "dave", dialogs=dialogs)
    signup(page, URL, USER, "pw-dave")
    run.check("A: dave signs up on the old version", bool(wait_home(page)), path_of(page))
    ok = post_tweet(page, f"dave pre-upgrade {TAG}")
    page.locator("input[placeholder='Search users']").fill(FOLLOW)
    wait_for(lambda: search_user_results(page) == [FOLLOW], 10)
    run.check("A: dave tweets + follows alice", bool(ok) and click_follow(page, FOLLOW), feed_tweets(page)[:2])
    page.wait_for_timeout(1000)
    tok0 = token_of(page)
    page.evaluate("() => { window.__qa_marker = 'old-tab-' + Date.now(); }")
    snapshot(page, "A_before")
    (CTL / "ready").write_text(tok0 or "")
    print("READY; waiting for 'down'", flush=True)
    wait_file(page, "down")
    page.wait_for_timeout(8000)
    snapshot(page, "B_server_down")
    print("waiting for 'up'", flush=True)
    wait_file(page, "up")
    run.notes["t_up"] = run._t()
    pump_wait(page, lambda: on_home(page) and composer_avatar(page) == USER[:2], 60)
    page.wait_for_timeout(5000)
    info = snapshot(page, "C_after_up")
    run.check("C: did the old tab reload itself after the new server came up?", "pass" if info["marker"] is None else "anomaly",
              f"marker={'gone (page reloaded)' if info['marker'] is None else info['marker']}")
    survived = info["on_home"] and info["avatar"] == USER[:2] and info["token"] == tok0
    if EXPECT_SESSION:
        run.check("C: dave still logged in after restart WITHOUT re-login (same token)", survived, info)
    else:
        run.check("C: dave logged out after restart (disk state manager wiped by `reflex run`; same on 0.9.12)",
                  (not survived) and info["on_login"] and info["token"] == tok0, info)
    if not on_home(page):
        login(page, URL, USER, "pw-dave", goto=not on_login(page))
        run.check("C2: dave logs in again with password after restart", bool(wait_home(page)), path_of(page))
    ok = post_tweet(page, f"dave after upgrade {TAG}") if on_home(page) else False
    run.check("D: the tab posts a tweet through the new backend", bool(ok), feed_tweets(page)[:3])
    snapshot(page, "D_interact")
    page.reload(wait_until="load")
    pump_wait(page, lambda: on_home(page) and composer_avatar(page) == USER[:2], 30)
    info = snapshot(page, "E_after_manual_reload")
    run.check("E: manual reload keeps dave's session", info["on_home"] and info["avatar"] == USER[:2], info["avatar"])
    try:
        page.get_by_role("button", name="Sign out").click(timeout=10000)
    except Exception as e:  # noqa: BLE001
        run.check("F: sign out button present", False, repr(e)[:300])
    run.check("F: sign out on new version", bool(wait_login(page)), path_of(page))
    login(page, URL, USER, "pw-dave", goto=False)
    run.check("F: dave logs back in with the 0.9.12-written password row", bool(wait_home(page)), path_of(page))
    page.wait_for_timeout(1000)
    fo = list_under_heading(page, "Following")
    run.check("F: dave Following lists alice after fresh login", fo is not None and FOLLOW in fo, fo)
    snapshot(page, "F_relogin")
    browser.close()
(CTL / "done").write_text("1")
sys.exit(run.finish())
