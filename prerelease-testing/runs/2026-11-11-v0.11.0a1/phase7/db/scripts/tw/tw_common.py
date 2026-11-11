"""Shared helpers for the twitter (PySocial) drivers."""
from __future__ import annotations

import json

from harness import wait_for

TOKEN_KEY = "token"  # reflex sessionStorage key (same in 0.9.12 and 0.10.0a1)


def new_page(browser, run, label, token=None, dialogs=None):
    """New context+page, optionally pre-seeding the reflex client token (simulates the same tab)."""
    ctx = browser.new_context(viewport={"width": 1400, "height": 950})
    if token:
        ctx.add_init_script(
            f"if (!window.sessionStorage.getItem({json.dumps(TOKEN_KEY)})) "
            f"window.sessionStorage.setItem({json.dumps(TOKEN_KEY)}, {json.dumps(token)});"
        )
    page = ctx.new_page()
    run.attach(page, label)
    if dialogs is not None:
        def _d(d, label=label):
            dialogs.append({"page": label, "type": d.type, "message": d.message, "t": run._t()})
            d.accept()
        page.on("dialog", _d)
    return ctx, page


def token_of(page):
    return page.evaluate(f"() => window.sessionStorage.getItem({json.dumps(TOKEN_KEY)})")


def path_of(page):
    return page.evaluate("() => window.location.pathname")


def on_home(page):
    return page.locator("textarea[placeholder=\"What's happening?\"]").count() > 0 and page.get_by_role("button", name="Tweet", exact=True).count() > 0


def on_login(page):
    return page.get_by_role("button", name="Log in").count() > 0


def on_signup(page):
    return page.get_by_role("button", name="Sign up").count() > 0


def composer_avatar(page):
    return page.evaluate("""() => {
        const ta = document.querySelector('textarea[placeholder="What\\'s happening?"]');
        if (!ta) return null;
        let g = ta; while (g && !(g.classList && g.classList.contains('rt-Grid'))) g = g.parentElement;
        return g ? g.firstElementChild.innerText.trim().toLowerCase() : null;
    }""")


def list_under_heading(page, heading):
    """usernames rendered as <p> inside the box headed by `heading` (Followers / Following)."""
    return page.evaluate("""(h) => {
        const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(e => e.innerText.trim() === h);
        if (!hs.length) return null;
        const box = hs[0].parentElement;
        return [...box.querySelectorAll('p')].map(p => p.innerText.trim());
    }""", heading)


def feed_tweets(page):
    """[(author, content)] in feed order."""
    return page.evaluate("""() => {
        const out = [];
        for (const p of document.querySelectorAll('p')) {
            const t = p.innerText.trim();
            if (t.startsWith('@')) {
                const nxt = p.nextElementSibling;
                out.push([t.slice(1), nxt ? nxt.innerText.trim() : null]);
            }
        }
        return out;
    }""")


def search_user_results(page):
    """usernames listed under the 'Search users' input (each row has a follow button)."""
    return page.evaluate("""() => {
        const inp = document.querySelector('input[placeholder="Search users"]');
        if (!inp) return null;
        let col = inp; while (col && !(col.classList && col.classList.contains('rt-Flex') && col.querySelector('h1,h2,h3,h4,h5,h6'))) col = col.parentElement;
        if (!col) return null;
        return [...col.querySelectorAll('button')].map(b => {
            const row = b.parentElement; const p = row ? row.querySelector('p') : null; return p ? p.innerText.trim() : null;
        }).filter(Boolean);
    }""")


def click_follow(page, username):
    return page.evaluate("""(u) => {
        const inp = document.querySelector('input[placeholder="Search users"]');
        let col = inp; while (col && !(col.classList && col.classList.contains('rt-Flex') && col.querySelector('h1,h2,h3,h4,h5,h6'))) col = col.parentElement;
        for (const b of col.querySelectorAll('button')) {
            const p = b.parentElement && b.parentElement.querySelector('p');
            if (p && p.innerText.trim() === u) { b.click(); return true; }
        }
        return false;
    }""", username)


def fill_blur(page, selector, value):
    loc = page.locator(selector)
    loc.click()
    loc.fill(value)
    loc.press("Tab")  # the app uses on_blur setters


def signup(page, url, user, pw, confirm=None):
    page.goto(url.rstrip("/") + "/signup", wait_until="load")
    page.get_by_role("button", name="Sign up").wait_for(timeout=60000)
    page.wait_for_timeout(800)
    fill_blur(page, "input[placeholder='Username']", user)
    fill_blur(page, "input[placeholder='Password']", pw)
    fill_blur(page, "input[placeholder='Confirm password']", pw if confirm is None else confirm)
    page.get_by_role("button", name="Sign up").click()


def login(page, url, user, pw, goto=True):
    if goto:
        page.goto(url.rstrip("/") + "/login", wait_until="load")
    page.get_by_role("button", name="Log in").wait_for(timeout=60000)
    page.wait_for_timeout(800)
    fill_blur(page, "input[placeholder='Username']", user)
    fill_blur(page, "input[placeholder='Password']", pw)
    page.get_by_role("button", name="Log in").click()


def post_tweet(page, text):
    ta = page.locator("textarea[placeholder=\"What's happening?\"]")
    ta.click()
    ta.fill(text)
    page.get_by_role("button", name="Tweet", exact=True).click()
    return wait_for(lambda: any(c == text for _, c in feed_tweets(page)), 15)


def wait_home(page, timeout=30):
    return wait_for(lambda: on_home(page) and path_of(page) == "/", timeout)


def wait_login(page, timeout=30):
    return wait_for(lambda: on_login(page) and path_of(page).rstrip("/") == "/login", timeout)


def pump_wait(page, cond, timeout=10.0):
    """Like harness.wait_for but pumps Playwright's event loop (dialog/console events)."""
    import time as _t
    end = _t.time() + timeout
    while _t.time() < end:
        if cond():
            return True
        page.wait_for_timeout(200)
    return bool(cond())
