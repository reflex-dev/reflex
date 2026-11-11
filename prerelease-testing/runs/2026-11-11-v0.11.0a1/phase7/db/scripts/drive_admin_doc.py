"""drive_admin_doc.py <backend-base> <shotdir>: drive the v0.11.0a2 admin-dashboard guide app in Chromium.

/admin (no slash) status, login through MyAuthProvider, then "New" for User (SQLModel), TagOk / TagReq (MappedAsDataclass).
"""

import sys

from playwright.sync_api import sync_playwright

base, shots = sys.argv[1:3]
console, bad = [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: m.type in ("error", "warning") and console.append(f"{m.type}: {m.text[:160]}"))
    pg.on("response", lambda r: r.status >= 400 and bad.append(f"{r.status} {r.url}"))
    r = pg.goto(base + "/admin")
    print("GET /admin ->", r.status if r else None)
    r = pg.goto(base + "/admin/")
    print("GET /admin/ ->", r.status if r else None, "url", pg.url)
    pg.fill("input[name=username]", "qa")
    pg.fill("input[name=password]", "wrong")
    pg.click("button[type=submit]")
    pg.wait_for_load_state()
    print("bad login -> url", pg.url, "| 'Invalid username' shown:", pg.get_by_text("Invalid username or password").count() > 0)
    pg.fill("input[name=username]", "qa")
    pg.fill("input[name=password]", "pw-qa")
    pg.click("button[type=submit]")
    pg.wait_for_load_state()
    print("good login -> url", pg.url)
    pg.screenshot(path=f"{shots}/admin-home.png")
    for ident, fields in [("user", {"username": "qa", "email": "qa@example.com"}), ("tag-ok", {"name": "ok"}), ("tag-req", {"name": "req"})]:
        r = pg.goto(f"{base}/admin/{ident}/create")
        print(f"GET /admin/{ident}/create ->", r.status if r else None)
        for k, v in fields.items():
            pg.fill(f"[name={k}]", v)
        with pg.expect_response(lambda resp: resp.request.method == "POST") as ri:
            pg.locator("form button[type=submit], form input[type=submit]").first.click()
        print(f"POST /admin/{ident}/create ->", ri.value.status)
        pg.wait_for_load_state()
        r = pg.goto(f"{base}/admin/api/{ident}?skip=0&limit=10")
        print(f"  api list {ident} ->", r.status if r else None, (pg.content()[:0] or pg.inner_text("body"))[:160].replace("\n", " "))
    pg.screenshot(path=f"{shots}/admin-after.png")
    b.close()
print("console:", console or "none")
print("http>=400:", bad or "none")
