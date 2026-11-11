"""Drive reflex-examples basic_crud (rx.App(api_transformer=FastAPI) + sqlmodel + rx.session + bg reload loop).

Usage: drive_basic_crud.py <frontend_url> <backend_url> <outdir> <tag> [expect_code ...]
Flow: list loads from DB (on_load) and shows every expected code; UI query form POSTs a new product through the
FastAPI router (state handler -> httpx -> same backend), the bg loop refreshes the list; direct HTTP GET/POST/PUT/
DELETE on /products; reload shows the final DB contents. Leaves "<tag>-ui" and "<tag>-api" (renamed label) in the DB.
"""

import json
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
FE, BE, OUT, TAG = sys.argv[1:5]
EXPECT = sys.argv[5:]
FE, BE = FE.rstrip("/"), BE.rstrip("/")
run = Run(TAG, OUT)
cli = httpx.Client(timeout=15)


def body(page):
    try:
        return page.inner_text("body")
    except Exception:  # noqa: BLE001
        return ""


def product(code, label):
    return {"code": code, "label": label, "image": "/favicon.ico", "quantity": 3, "category": "qa",
            "seller": "s", "sender": "t"}


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page(viewport={"width": 1400, "height": 1000})
    run.attach(page)
    page.goto(FE + "/", wait_until="load")
    ok = wait_for(lambda: re.search(r"\d+ products found", body(page)), 40)
    run.check("list renders 'N products found'", bool(ok), ok.group(0) if ok else body(page)[:200])
    time.sleep(1)
    txt = body(page)
    for c in EXPECT:
        run.check(f"existing product listed: {c}", f"({c})" in txt)
    n0 = int(re.search(r"(\d+) products found", txt).group(1)) if ok else -1
    run.notes["n0"] = n0
    # UI: POST through the query form (select POST, edit body, Send)
    page.get_by_role("combobox").first.click()
    page.get_by_role("option", name="POST", exact=True).click()
    ta = page.locator("textarea")
    ta.fill(json.dumps(product(f"{TAG}-ui", f"UI {TAG}")))
    time.sleep(0.5)
    page.get_by_role("button", name="Send").click()
    st = wait_for(lambda: re.search(r"Status:\s*(\d+)", body(page)) and re.search(r"Status:\s*(\d+)", body(page)).group(1), 15)
    run.check("UI POST -> status 200", st == "200", st)
    seen = wait_for(lambda: f"({TAG}-ui)" in body(page), 12)
    run.check("bg reload loop shows UI-created product", bool(seen))
    run.shot(page, "after_ui_post")
    # direct HTTP on the api_transformer routes
    r = cli.post(BE + "/products", content=json.dumps(product(f"{TAG}-api", "API original")))
    run.check("HTTP POST /products", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
    lst = cli.get(BE + "/products").json()
    pid = next((x["id"] for x in lst if x["code"] == f"{TAG}-api"), None)
    run.check("HTTP GET /products lists it", pid is not None, f"{len(lst)} rows")
    r = cli.put(BE + f"/products/{pid}", content=json.dumps({"label": f"API {TAG} renamed"}))
    run.check("HTTP PUT /products/{id}", r.status_code == 200, r.status_code)
    g = cli.get(BE + f"/products/{pid}").json()
    run.check("HTTP GET /products/{id} reflects PUT", g.get("label") == f"API {TAG} renamed", g)
    run.notes["get_one"] = g
    r = cli.post(BE + "/products", content=json.dumps(product(f"{TAG}-tmp", "to delete")))
    tmp = next(x["id"] for x in cli.get(BE + "/products").json() if x["code"] == f"{TAG}-tmp")
    r = cli.delete(BE + f"/products/{tmp}")
    run.check("HTTP DELETE /products/{id}", r.status_code == 200 and all(x["code"] != f"{TAG}-tmp" for x in cli.get(BE + "/products").json()), r.status_code)
    r = cli.post(BE + "/products", content=json.dumps(product(f"{TAG}-api", "dup")))
    run.check("HTTP POST duplicate code -> error (unique constraint)", r.status_code >= 400, r.status_code)
    page.reload(wait_until="load")
    wait_for(lambda: re.search(r"\d+ products found", body(page)), 30)
    time.sleep(1.5)
    txt = body(page)
    n1 = int(re.search(r"(\d+) products found", txt).group(1))
    run.check("reload: count = before + 2", n1 == n0 + 2, f"{n0} -> {n1}")
    run.check("reload: renamed API product shown", f"API {TAG} renamed" in txt)
    run.shot(page, "final")
    b.close()
sys.exit(run.finish())
