"""Drive the tickets demo UI (rxe EventHandlerAPIPlugin test bed) in Chromium.

Usage: drive_tickets.py <base_url> <out_dir> <expected_venv> <label> [<backend_base_for_api>]
The UI test seeds the DB, creates/edits/closes/deletes tickets, searches, filters, sorts, pages,
navigates to the detail page and back, reloads, opens a second context; if a backend base URL is
given it also creates a ticket over the HTTP API and checks the UI sees it after reload.
"""
import sys
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
api = sys.argv[5] if len(sys.argv) > 5 else None
info = assert_driver_and_server(venv)


def titles(p):
    return [t.strip() for t in p.locator("table tbody tr th:first-child").all_inner_texts()]


def badge(p, txt):
    return p.locator(f".rt-Badge:has-text('{txt}')").first.inner_text()


def scenario(s, name, fn, *a):
    try:
        fn(*a)
    except Exception:
        s.check(f"{name}: scenario completed", False, traceback.format_exc()[-800:])


def wait_rows(p, n, timeout=8000):
    try:
        p.wait_for_function("n => document.querySelectorAll('table tbody tr').length === n", arg=n, timeout=timeout)
    except Exception:
        pass


def main_flow(s, ctx, p):
    p.goto(base + "/", wait_until="networkidle")
    p.wait_for_timeout(1500)
    p.click("button:has-text('Seed')")
    wait_rows(p, 4)
    s.check("seed: 4 tickets listed, Open 4 / Total 4", len(titles(p)) == 4 and badge(p, "Open") == "Open: 4" and badge(p, "Total") == "Total: 4",
            {"titles": titles(p), "open": badge(p, "Open"), "total": badge(p, "Total")})
    # create via form
    p.click("button:has-text('New Ticket')")
    p.fill("input[placeholder='Title']", "Monitor flickers")
    p.fill("textarea[placeholder='Description'], input[placeholder='Description']", "Second screen flickers")
    p.fill("input[placeholder='Assignee']", "dave")
    p.click("button:has-text('Create')")
    wait_rows(p, 5)
    s.check("create form: new ticket appears first (created_at desc), Total 5", titles(p)[:1] == ["Monitor flickers"] and badge(p, "Total") == "Total: 5", titles(p))
    # search via form submit -> redirect with ?q=
    p.fill("input[name=q]", "VPN")
    p.click("button:has-text('Apply')")
    p.wait_for_url("**q=VPN**", timeout=10000)
    wait_rows(p, 1)
    q = parse_qs(urlparse(p.url).query)
    s.check("search: Apply redirects with ?q=VPN and lists 1 ticket", titles(p) == ["VPN slow from home"] and q.get("q") == ["VPN"], {"url": p.url, "titles": titles(p)})
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(1500)
    s.check("search: reload keeps the filter from the URL (on_load reads query params)", titles(p) == ["VPN slow from home"], titles(p))
    p.click("button:has-text('Reset filters')")
    wait_rows(p, 5)
    s.check("reset filters: back to 5 tickets and clean URL params", len(titles(p)) == 5 and "q=" not in p.url, {"url": p.url, "n": len(titles(p))})
    # sort by title (header button) asc
    p.locator("table thead button:has-text('Title')").click()
    p.wait_for_url("**sort_by=title**", timeout=10000)
    p.wait_for_timeout(1000)
    t = titles(p)
    s.check("sort: Title header sorts ascending", t == sorted(t), t)
    p.locator("table thead button:has-text('Title')").click()
    p.wait_for_url("**sort_dir=desc**", timeout=10000)
    p.wait_for_timeout(1000)
    t = titles(p)
    s.check("sort: second click sorts descending", t == sorted(t, reverse=True), t)
    # status buttons on the 'Printer offline' row
    row = p.locator("table tbody tr:has-text('Printer offline')")
    row.locator("button:has-text('Close')").click()
    p.wait_for_timeout(1200)
    s.check("row action: close button -> status badge 'closed', Open count 4", "closed" in p.locator("table tbody tr:has-text('Printer offline')").inner_text() and badge(p, "Open") == "Open: 4",
            {"row": p.locator("table tbody tr:has-text('Printer offline')").inner_text(), "open": badge(p, "Open")})
    # priority filter via radix select
    p.locator("button[role=combobox]").nth(1).click()
    p.locator("[role=option]:has-text('high')").first.click()
    p.wait_for_url("**priority=high**", timeout=10000)
    p.wait_for_timeout(1200)
    s.check("filter: priority=high select -> only high tickets", titles(p) == ["Laptop won't boot"], titles(p))
    p.click("button:has-text('Reset filters')")
    wait_rows(p, 5)
    # page size 10 -> still one page; next disabled
    s.check("paging: Prev/Next disabled on single page", p.locator("button:has-text('Next')").is_disabled() and p.locator("button:has-text('Prev')").is_disabled())
    # open detail, edit, save
    p.locator("table tbody tr:has-text('Email signature broken') th").first.click()
    p.wait_for_url("**/ticket?ticket_id=**", timeout=10000)
    p.wait_for_selector("input[placeholder='Title']")
    p.wait_for_timeout(1500)
    s.check("detail: on_load fills the edit form from the DB", p.locator("input[placeholder='Title']").input_value() == "Email signature broken", p.locator("input[placeholder='Title']").input_value())
    s.shot(p, "detail")
    p.fill("input[placeholder='Title']", "Email signature fixed?")
    p.fill("input[placeholder='Assignee']", "erin")
    p.click("button:has-text('Save changes')")
    p.wait_for_timeout(1500)
    if "/ticket" in p.url:
        p.click("button:has-text('Back to tickets')")
    p.wait_for_url(lambda u: "/ticket" not in u, timeout=10000)
    wait_rows(p, 5)
    s.check("detail: save + back shows the edited title in the list", "Email signature fixed?" in titles(p), titles(p))
    # direct load of a bogus ticket id
    p.goto(base + "/ticket?ticket_id=does-not-exist", wait_until="networkidle")
    p.wait_for_timeout(1500)
    s.check("detail: unknown ticket_id shows the error callout", p.locator(".rt-CalloutRoot").count() > 0, p.locator("body").inner_text()[:300])
    p.goto(base + "/", wait_until="networkidle")
    p.wait_for_timeout(1200)
    # delete via ⋯ menu on a row
    row = p.locator("table tbody tr:has-text('Monitor flickers')")
    row.locator("button:has-text('⋯')").click()
    p.locator("[role=menuitem]").filter(has_text="Delete").first.click()
    wait_rows(p, 4)
    s.check("row menu: Delete removes the ticket", "Monitor flickers" not in titles(p) and badge(p, "Total") == "Total: 4", titles(p))
    s.shot(p, "list-after")
    # second context sees the same DB rows
    p2 = s.new_page(s.new_context("tickets-ctx2"), "tickets-ctx2")
    p2.goto(base + "/", wait_until="networkidle")
    p2.wait_for_timeout(1500)
    s.check("second context: same 4 tickets from the shared DB", sorted(titles(p2)) == sorted(titles(p)), titles(p2))
    if api:
        c = httpx.Client(base_url=api, timeout=30, trust_env=False)
        tok = c.post("/_reflex/auth/token").json()["access_token"]
        r = c.post("/_reflex/event/tickets___tickets____ticket_state/create_ticket", headers={"Authorization": f"Bearer {tok}"},
                   json={"title": "Created over HTTP", "priority": "low"})
        s.check("HTTP API: create_ticket returns 200", r.status_code == 200, r.status_code)
        p.reload(wait_until="networkidle")
        wait_rows(p, 5)
        s.check("HTTP API: browser sees the ticket created over HTTP after reload", "Created over HTTP" in titles(p), titles(p))
    # clear all via menu
    p.locator("button:has-text('⋯')").first.click()
    p.locator("[role=menuitem]:has-text('Clear all')").click()
    wait_rows(p, 0)
    s.check("Clear all empties the table", len(titles(p)) == 0 and badge(p, "Total") == "Total: 0", titles(p))


with Session(f"tickets-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    ctx = s.new_context("tickets")
    p = s.new_page(ctx, "tickets")
    scenario(s, "tickets", main_flow, s, ctx, p)
