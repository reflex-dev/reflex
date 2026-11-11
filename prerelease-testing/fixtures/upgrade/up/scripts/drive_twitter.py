"""Drive the reflex-examples `twitter` (PySocial) app.

Usage: drive_twitter.py <url> <outdir> <tag> base|up <tokfile> [expect_version]
  base: fresh DB. alice signs up, tweets, searches; bob (2nd context) signs up, tweets, follows alice;
        reload keeps the login; logout/login; bad password + duplicate/mismatch signup alerts.
        Saves alice/bob client tokens (sessionStorage) to <tokfile>.
  up:   existing DB + tokens from <tokfile>: a new context seeded with alice's token (= same tab after
        reload) must land on the home page WITHOUT logging in (server-side State.user restored from
        .states); pre-upgrade tweets/follows visible; new tweet; bob via token and via password;
        new user carol follows alice; logout/login. Rewrites <tokfile> for the next run.
Writes <outdir>/<tag>.json (harness format) + screenshots.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402
from tw_common import (  # noqa: E402
    click_follow, composer_avatar, feed_tweets, list_under_heading, login, new_page, on_home,
    on_login, path_of, post_tweet, pump_wait, search_user_results, signup, token_of, wait_home, wait_login,
)

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, MODE, TOKFILE = sys.argv[1:6]
URL = URL.rstrip("/")
run = Run(TAG, OUT)
EXPECT_SESSION = os.environ.get("QA_EXPECT_SESSION", "1") == "1"
run.notes["expect_session"] = EXPECT_SESSION
dialogs: list = []
run.notes["dialogs"] = dialogs


def obs(name, value):
    run.notes.setdefault("observations", {})[name] = value
    print(f"   obs {name}: {value}", flush=True)


def base(browser):
    sfx = os.environ.get("QA_USER_SUFFIX", "")
    ua, ub = "alice" + sfx, "bob" + sfx
    ctxA, a = new_page(browser, run, "alice", dialogs=dialogs)
    a.goto(URL + "/", wait_until="load")
    run.check("anon / redirects to /login (on_load check_login)", bool(wait_login(a, 60)), path_of(a))
    run.shot(a, "01_login_redirect")
    signup(a, URL, ua, "pw-alice")
    run.check("alice signup -> redirect to home", bool(wait_home(a)), path_of(a))
    run.check("home shows alice avatar (State.user set)", wait_for(lambda: composer_avatar(a) == "al", 10) is not None, composer_avatar(a))
    obs("A_feed_initial", feed_tweets(a))
    obs("A_click_to_load_button", a.get_by_text("Click to load tweets").count())
    ok1 = post_tweet(a, f"alice tweet one {TAG}")
    ok2 = post_tweet(a, f"alice tweet two {TAG}")
    run.check("alice posts 2 tweets, feed shows them newest-first", bool(ok1 and ok2) and feed_tweets(a)[:2] == [[ua, f"alice tweet two {TAG}"], [ua, f"alice tweet one {TAG}"]], feed_tweets(a))
    run.shot(a, "02_alice_tweets")
    s = a.locator("input[placeholder='Search tweets']")
    s.fill(f"two {TAG}")
    okS = wait_for(lambda: [c for _, c in feed_tweets(a)] == [f"alice tweet two {TAG}"], 10)
    run.check("search tweets filters feed (set_search -> get_tweets)", bool(okS), feed_tweets(a))
    s.fill("")
    wait_for(lambda: len(feed_tweets(a)) >= 2, 10)
    tokA = token_of(a)

    ctxB, b = new_page(browser, run, "bob", dialogs=dialogs)
    signup(b, URL, ub, "pw-bob")
    run.check("bob signup (2nd context) -> home", bool(wait_home(b)), path_of(b))
    okb = post_tweet(b, f"bob tweet {TAG}")
    run.check("bob tweet; feed shows all users' tweets", bool(okb) and {u for u, _ in feed_tweets(b)} >= {ua, ub}, feed_tweets(b))
    b.locator("input[placeholder='Search users']").fill(ua)
    okU = wait_for(lambda: search_user_results(b) == [ua], 10)
    run.check("search users 'ali' lists alice with follow button", bool(okU), search_user_results(b))
    run.check("follow alice click", click_follow(b, ua))
    b.wait_for_timeout(1500)
    obs("B_following_after_follow_no_reload", list_under_heading(b, "Following"))
    run.shot(b, "03_bob_follow")
    b.reload(wait_until="load")
    wait_home(b)
    b.wait_for_timeout(1500)
    obs("B_following_after_reload", list_under_heading(b, "Following"))
    run.check("bob still logged in after reload (token kept)", on_home(b) and composer_avatar(b) == "bo", composer_avatar(b))
    tokB = token_of(b)

    obs("A_followers_before_reload", list_under_heading(a, "Followers"))
    a.reload(wait_until="load")
    run.check("alice still logged in after reload", bool(wait_home(a)) and wait_for(lambda: composer_avatar(a) == "al", 10) is not None, composer_avatar(a))
    a.wait_for_timeout(1000)
    obs("A_followers_after_reload", list_under_heading(a, "Followers"))
    obs("A_feed_after_reload", feed_tweets(a))
    run.shot(a, "04_alice_reload")

    # logout / bad login / login
    a.get_by_role("button", name="Sign out").click()
    run.check("sign out -> /login", bool(wait_login(a)), path_of(a))
    a.goto(URL + "/", wait_until="load")
    run.check("after sign out, / redirects to /login again", bool(wait_login(a)), path_of(a))
    n = len(dialogs)
    login(a, URL, ua, "WRONG", goto=False)
    pump_wait(a, lambda: len(dialogs) > n, 10)
    run.check("wrong password -> window_alert", any("Invalid username or password" in d["message"] for d in dialogs[n:]), dialogs[n:])
    login(a, URL, ua, "pw-alice")
    run.check("alice re-login -> home", bool(wait_home(a)) and wait_for(lambda: composer_avatar(a) == "al", 10) is not None, composer_avatar(a))
    a.wait_for_timeout(1000)
    fl = list_under_heading(a, "Followers")
    run.check("alice Followers lists bob after fresh login", fl is not None and ub in fl, fl)
    obs("A_feed_after_relogin", feed_tweets(a))
    run.check("same token kept across logout/login (reset() keeps session)", token_of(a) == tokA, f"{tokA} -> {token_of(a)}")
    run.shot(a, "05_alice_relogin")

    ctxC, c = new_page(browser, run, "carol0", dialogs=dialogs)
    n = len(dialogs)
    signup(c, URL, ub, "x")
    pump_wait(c, lambda: len(dialogs) > n, 10)
    run.check("duplicate username -> alert", any("Username already exists" in d["message"] for d in dialogs[n:]), dialogs[n:])
    n = len(dialogs)
    signup(c, URL, "zed" + sfx, "p1", confirm="p2")
    pump_wait(c, lambda: len(dialogs) > n, 10)
    run.check("password mismatch -> alert", any("Passwords do not match" in d["message"] for d in dialogs[n:]), dialogs[n:])
    ctxC.close()
    run.notes["tokens"] = {"alice": tokA, "bob": tokB}
    Path(TOKFILE).write_text(json.dumps({"alice": tokA, "bob": tokB}))
    # keep alice logged in (state persisted for the next run); bob too


def up(browser):
    sfx = os.environ.get("QA_USER_SUFFIX", "")
    ua, ub = "alice" + sfx, "bob" + sfx
    toks = json.loads(Path(TOKFILE).read_text())
    run.notes["tokens_in"] = toks
    ctxA, a = new_page(browser, run, "alice-tok", token=toks["alice"], dialogs=dialogs)
    a.goto(URL + "/", wait_until="load")
    home = wait_for(lambda: on_home(a) or on_login(a), 60)
    a.wait_for_timeout(1500)
    av = composer_avatar(a)
    restored = on_home(a) and path_of(a) == "/" and av == "al"
    detail = f"path={path_of(a)} avatar={av} token_now={token_of(a)} same_token={token_of(a) == toks['alice']}"
    if EXPECT_SESSION:
        run.check("alice's pre-restart session survives: / renders home without re-login", restored, detail)
    else:
        run.check("alice's token after restart lands on /login (disk state manager: `reflex run` wipes .states, both versions)",
                  (not restored) and on_login(a), detail)
    obs("A_feed_on_restore", feed_tweets(a))
    obs("A_followers_on_restore", list_under_heading(a, "Followers"))
    run.shot(a, "01_alice_restored")
    if not on_home(a):
        login(a, URL, ua, "pw-alice", goto=not on_login(a))
        wait_home(a)
    ok = post_tweet(a, f"alice after {TAG}")
    tw = feed_tweets(a)
    run.check("alice posts after upgrade; pre-upgrade tweets still in feed", bool(ok) and sum(1 for u, c in tw if u == ua) >= 3 and any(u == ub for u, _ in tw), tw)
    run.shot(a, "02_alice_tweet")

    ctxB, b = new_page(browser, run, "bob-tok", token=toks["bob"], dialogs=dialogs)
    b.goto(URL + "/", wait_until="load")
    wait_for(lambda: on_home(b) or on_login(b), 60)
    b.wait_for_timeout(1500)
    rb = on_home(b) and composer_avatar(b) == "bo"
    if EXPECT_SESSION:
        run.check("bob's pre-restart session survives (token)", rb, f"path={path_of(b)} avatar={composer_avatar(b)}")
        # app quirk: `following` is a cached computed var that only recomputes when `user` changes,
        # so a restored session shows the value cached at its last recompute (observation, compare versions)
        obs("B_following_on_restore", list_under_heading(b, "Following"))
    else:
        run.check("bob's token after restart lands on /login (disk mode, expected)", (not rb) and on_login(b), f"path={path_of(b)}")
    ctxB.close()

    ctxB2, b2 = new_page(browser, run, "bob-pw", dialogs=dialogs)
    login(b2, URL, ub, "pw-bob")
    run.check("bob logs in with pre-upgrade password row", bool(wait_home(b2)) and composer_avatar(b2) == "bo", composer_avatar(b2))
    b2.wait_for_timeout(800)
    fo2 = list_under_heading(b2, "Following")
    run.check("bob Following lists alice after login (pre-upgrade follow row)", fo2 is not None and ua in fo2, fo2)
    b2.locator("button:has-text('Click to load tweets')").click() if b2.get_by_text("Click to load tweets").count() else None
    wait_for(lambda: len(feed_tweets(b2)) >= 3, 10)
    run.check("bob loads full feed (pre+post upgrade tweets)", any(c == f"alice after {TAG}" for _, c in feed_tweets(b2)), feed_tweets(b2))
    ctxB2.close()

    ctxC, c = new_page(browser, run, "carol", dialogs=dialogs)
    user = f"carol{TAG.replace('-', '')[-6:]}"
    signup(c, URL, user, "pw-carol")
    run.check(f"new user {user} signup after upgrade", bool(wait_home(c)), path_of(c))
    c.locator("input[placeholder='Search users']").fill(ua)
    wait_for(lambda: search_user_results(c) == [ua], 10)
    run.check(f"{user} follows alice", click_follow(c, ua), search_user_results(c))
    c.wait_for_timeout(1000)
    ctxC.close()

    a.get_by_role("button", name="Sign out").click()
    run.check("alice sign out -> /login", bool(wait_login(a)), path_of(a))
    login(a, URL, ua, "pw-alice")
    run.check("alice re-login -> home", bool(wait_home(a)) and wait_for(lambda: composer_avatar(a) == "al", 10) is not None, composer_avatar(a))
    a.wait_for_timeout(1000)
    fl = list_under_heading(a, "Followers")
    run.check(f"alice Followers = bob + {user}", fl is not None and ub in fl and user in fl, fl)
    run.shot(a, "03_alice_relogin")
    a.reload(wait_until="load")
    run.check("alice still logged in after reload", bool(wait_home(a)) and wait_for(lambda: composer_avatar(a) == "al", 10) is not None, composer_avatar(a))
    newtok = {"alice": token_of(a), "bob": toks["bob"]}
    run.notes["tokens_out"] = newtok
    Path(TOKFILE).write_text(json.dumps(newtok))


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    try:
        (base if MODE == "base" else up)(browser)
    except Exception as e:  # noqa: BLE001
        run.check(f"driver exception in {MODE}", False, repr(e)[:800])
    browser.close()
sys.exit(run.finish())
