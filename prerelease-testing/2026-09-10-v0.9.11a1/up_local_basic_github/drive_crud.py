"""Driver for the reflex-examples `basic_crud` app: REST endpoints with httpx + the UI in Chromium.

usage: drive_crud.py <frontend_url> <backend_url> <artifacts_dir> <label>

Part A drives the app's own FastAPI routes (mounted through `rx.App(api_transformer=FastAPI())`)
directly with httpx: full CRUD plus the error paths and the OpenAPI surface.
Part B drives the same endpoints through the UI (rx.select / rx.input / rx.text_area / Send) and
checks the product list refreshes via the app's `@rx.event(background=True)` poller and that
rx.foreach renders each row.

The DB is emptied through the API before each run so the two phases are comparable across versions.
"""

import json
import sys

import httpx

from drive_common import Run, wait_for

FRONTEND, BACKEND, ART, LABEL = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

CLIENT = httpx.Client(base_url=BACKEND, timeout=30.0, trust_env=False)


def body_for(code, label, qty=7, category="tools", seller="acme", sender="depot"):
    return json.dumps(
        {
            "code": code,
            "label": label,
            "image": "/favicon.ico",
            "quantity": qty,
            "category": category,
            "seller": seller,
            "sender": sender,
        }
    )


def heading_count(page):
    t = page.inner_text("h1, h2, h3, .rt-Heading")
    return t


with Run(ART, LABEL) as run:
    api = {}

    # ---------------- Part A: the REST API, straight at the backend -------------------
    r = CLIENT.get("/products")
    api["GET /products (initial)"] = (r.status_code, r.text[:200])
    run.record(
        "api_list_initial",
        "pass" if r.status_code == 200 and isinstance(r.json(), list) else "fail",
        f"{r.status_code} {len(r.json()) if r.status_code == 200 else '?'} rows",
    )
    for p in r.json() if r.status_code == 200 else []:
        CLIENT.delete(f"/products/{p['id']}")
    left = len(CLIENT.get("/products").json())
    run.record("api_cleanup", "pass" if left == 0 else "fail", f"{left} rows left after DELETE sweep")

    r = CLIENT.post("/products", content=body_for("API-1", "Api Widget"))
    api["POST /products"] = (r.status_code, r.text[:200])
    run.record(
        "api_create",
        "pass" if r.status_code == 200 and r.json() == "OK" else "fail",
        f"{r.status_code} {r.text[:80]}",
    )

    rows = CLIENT.get("/products").json()
    made = [p for p in rows if p["code"] == "API-1"]
    run.record(
        "api_list_after_create",
        "pass" if len(made) == 1 else "fail",
        f"{len(rows)} rows, API-1 x{len(made)}",
    )
    pid = made[0]["id"] if made else None
    if made:
        keys = sorted(made[0])
        run.record(
            "api_row_shape",
            "pass" if {"id", "code", "label", "quantity", "created", "updated"} <= set(keys) else "fail",
            f"keys={keys}",
        )

    if pid is not None:
        r = CLIENT.get(f"/products/{pid}")
        api[f"GET /products/{pid}"] = (r.status_code, r.text[:300])
        run.record(
            "api_get_one",
            "pass" if r.status_code == 200 and r.json().get("code") == "API-1" else "fail",
            f"{r.status_code} {r.text[:120]}",
        )

        r = CLIENT.put(f"/products/{pid}", content=json.dumps({"quantity": 99, "label": "Api Widget v2"}))
        api[f"PUT /products/{pid}"] = (r.status_code, r.text[:200])
        after = CLIENT.get(f"/products/{pid}").json()
        run.record(
            "api_update",
            "pass" if r.status_code == 200 and after.get("quantity") == 99 and after.get("label") == "Api Widget v2" else "fail",
            f"PUT {r.status_code}; now quantity={after.get('quantity')} label={after.get('label')!r}",
        )
        run.record(
            "api_update_touches_updated",
            "pass" if after.get("updated") >= after.get("created") else "fail",
            f"created={after.get('created')} updated={after.get('updated')}",
        )

    # error / edge paths
    r = CLIENT.get("/products/999999")
    api["GET /products/999999"] = (r.status_code, r.text[:300])
    run.record(
        "api_get_missing",
        "anomaly" if r.status_code == 200 else "pass" if r.status_code == 404 else "anomaly",
        f"{r.status_code} body={r.text[:150]!r} (app `return HTTPException(404)` instead of raising)",
    )

    r = CLIENT.post("/products", content=body_for("", "No Code"))
    api["POST /products (empty code)"] = (r.status_code, r.text[:300])
    run.record(
        "api_create_empty_code",
        "anomaly" if r.status_code == 200 else "pass",
        f"{r.status_code} body={r.text[:150]!r} (app `return HTTPException(402)`)",
    )

    r = CLIENT.post("/products", content=body_for("API-1", "Duplicate"))
    api["POST /products (duplicate code)"] = (r.status_code, r.text[:300])
    run.record(
        "api_create_duplicate_code",
        "pass" if r.status_code >= 500 else "anomaly",
        f"{r.status_code} (unique constraint on code; 500 expected, app does not catch it)",
    )

    r = CLIENT.get("/openapi.json")
    ok = r.status_code == 200
    paths = sorted(r.json().get("paths", {})) if ok else []
    api["GET /openapi.json"] = (r.status_code, str(paths))
    run.record(
        "api_openapi",
        "pass" if ok and "/products" in paths and "/products/{spec_id}" in paths else "fail",
        f"{r.status_code} paths={paths}",
    )
    r = CLIENT.get("/docs")
    run.record("api_docs", "pass" if r.status_code == 200 else "fail", f"GET /docs -> {r.status_code}")
    r = CLIENT.get("/ping")
    run.record("api_reflex_ping", "pass" if r.status_code == 200 else "fail", f"GET /ping -> {r.status_code} {r.text[:40]!r}")

    # leave exactly one row for the UI phase
    for p in CLIENT.get("/products").json():
        if p["code"] != "API-1":
            CLIENT.delete(f"/products/{p['id']}")
    (run.art / "api_calls.json").write_text(json.dumps(api, indent=2))

    # ---------------- Part B: the UI ---------------------------------------------------
    ctx, page = run.new_page(LABEL)
    page.set_default_timeout(20000)
    page.goto(FRONTEND, wait_until="load")
    ok = wait_for(lambda: "products found" in page.inner_text("body"), 60)
    run.record("ui_load", "pass" if ok else "fail", f"'products found' present={ok}")
    page.wait_for_timeout(1500)
    run.shot(page, "01_index.png", full_page=True)

    n_start = wait_for(lambda: page.inner_text(".rt-Heading").strip().startswith("1 "), 20)
    run.record(
        "ui_on_load_lists_products",
        "pass" if n_start else "fail",
        f"heading={page.inner_text('.rt-Heading').strip()!r} (expect '1 products found' from the API row)",
    )
    run.record(
        "ui_foreach_row",
        "pass" if "(API-1)" in page.inner_text("body") else "fail",
        "rx.foreach rendered the API-1 row",
    )

    def set_method(m):
        page.get_by_role("combobox").click()
        page.get_by_role("option", name=m, exact=True).click()
        page.wait_for_timeout(400)

    def set_url(u):
        page.locator("input").first.fill(u)
        page.wait_for_timeout(300)

    def set_body(b):
        page.locator("textarea").first.fill(b)
        page.wait_for_timeout(300)

    def send():
        page.get_by_role("button", name="Send").click()
        page.wait_for_timeout(1500)

    def status_text():
        for el in page.locator(".rt-Text").all():
            t = el.inner_text()
            if t.startswith("Status:"):
                return t.strip()
        return "?"

    def response_text():
        return page.locator("pre, code").first.inner_text() if page.locator("pre, code").count() else ""

    # UI POST
    set_method("POST")
    set_url("products")
    set_body(body_for("UI-1", "Ui Widget", qty=3, category="ui"))
    send()
    st = status_text()
    run.record("ui_post_status", "pass" if "200" in st else "fail", f"{st!r} resp={response_text()[:60]!r}")
    grew = wait_for(lambda: page.inner_text(".rt-Heading").strip().startswith("2 "), 20)
    run.record(
        "ui_background_poller_refreshes",
        "pass" if grew else "fail",
        f"heading={page.inner_text('.rt-Heading').strip()!r} (background reload_product should reach 2)",
    )
    run.record(
        "ui_new_row_rendered",
        "pass" if "(UI-1)" in page.inner_text("body") else "fail",
        "UI-1 row present after background refresh",
    )
    run.shot(page, "02_after_post.png", full_page=True)

    ui_row = [p for p in CLIENT.get("/products").json() if p["code"] == "UI-1"]
    ui_id = ui_row[0]["id"] if ui_row else None

    # UI GET list
    set_method("GET")
    set_url("products")
    send()
    st, resp = status_text(), response_text()
    run.record(
        "ui_get_list",
        "pass" if "200" in st and "UI-1" in resp and "API-1" in resp else "fail",
        f"{st!r} resp_has_UI-1={'UI-1' in resp} resp_has_API-1={'API-1' in resp}",
    )
    run.shot(page, "03_after_get.png", full_page=True)

    # UI PUT
    if ui_id is not None:
        set_method("PUT")
        set_url(f"products/{ui_id}")
        set_body(json.dumps({"quantity": 55}))
        send()
        st = status_text()
        now = CLIENT.get(f"/products/{ui_id}").json()
        run.record(
            "ui_put",
            "pass" if "200" in st and now.get("quantity") == 55 else "fail",
            f"{st!r} quantity now {now.get('quantity')}",
        )
        qty_shown = wait_for(lambda: "Stock:55" in page.inner_text("body").replace(" ", "").replace("\n", ""), 20)
        run.record(
            "ui_put_reflected_in_list",
            "pass" if qty_shown else "fail",
            f"'Stock: 55' visible={qty_shown}",
        )

        # UI DELETE
        set_method("DELETE")
        set_url(f"products/{ui_id}")
        send()
        st = status_text()
        shrank = wait_for(lambda: page.inner_text(".rt-Heading").strip().startswith("1 "), 20)
        run.record(
            "ui_delete",
            "pass" if "200" in st and shrank else "fail",
            f"{st!r} heading={page.inner_text('.rt-Heading').strip()!r}",
        )
        run.shot(page, "04_after_delete.png", full_page=True)

    # Clear resets the form
    page.get_by_role("button", name="Clear").click()
    page.wait_for_timeout(800)
    cleared = page.locator("input").first.input_value() == "products" and '"code":""' in page.locator("textarea").first.input_value().replace(" ", "").replace("\n", "")
    run.record(
        "ui_clear_resets_form",
        "pass" if cleared else "fail",
        f"url={page.locator('input').first.input_value()!r}",
    )

    # An error response must surface in the UI, not crash it
    set_method("GET")
    set_url("products/999999")
    send()
    st, resp = status_text(), response_text()
    run.record(
        "ui_error_response_surfaced",
        "pass" if st != "?" else "fail",
        f"{st!r} resp={resp[:120]!r}",
    )
    run.shot(page, "05_error_response.png", full_page=True)

    # reload: state re-hydrates and the poller restarts
    page.reload(wait_until="load")
    ok = wait_for(lambda: page.inner_text(".rt-Heading").strip().startswith("1 "), 40)
    run.record("ui_reload", "pass" if ok else "fail", f"heading={page.inner_text('.rt-Heading').strip()!r}")
    run.shot(page, "06_reload.png", full_page=True)

    (run.art / "final_products.json").write_text(json.dumps(CLIENT.get("/products").json(), indent=2))
    ctx.close()
    CLIENT.close()
