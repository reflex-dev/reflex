"""Playwright + httpx driver for the basic_crud example app.

Usage: python drive_basic_crud.py <frontend_url> <backend_url> <outdir>

UI flows (Radix select + input + textarea + buttons; background task reloads
the product list every 2s after a UI-driven change):
 1. Initial render: "<N> products found" heading (fresh DB -> 0)
 2. POST via UI query form -> status 200, product list grows to N+1
 3. GET via UI -> JSON response containing the created code
 4. PUT via UI (products/<id>) -> update label; list reflects change (bg task)
 5. DELETE via UI -> list shrinks back
API flows via httpx directly against the backend:
 6. GET /ping, GET /products, POST /products, GET /products/{id},
    PUT /products/{id}, DELETE /products/{id}
Captures console messages, failed requests, screenshots.
"""

import json
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
API = sys.argv[2].rstrip("/")
OUT = Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)

console_msgs: list[dict] = []
failed_requests: list[str] = []
bad_responses: list[str] = []
results: list[dict] = []


def step(name: str, ok: bool, detail: str = ""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}: {name} {detail}")


def product_body(code: str, label: str) -> str:
    return json.dumps(
        {
            "code": code,
            "label": label,
            "image": "/favicon.ico",
            "quantity": 42,
            "category": "test",
            "seller": "alice",
            "sender": "bob",
        }
    )


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text}))
    page.on("requestfailed", lambda r: failed_requests.append(f"{r.method} {r.url} -> {r.failure}"))
    page.on(
        "response",
        lambda r: bad_responses.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )

    page.goto(URL, wait_until="load", timeout=60000)

    def found_count() -> int:
        h = page.locator("h1", has_text="products found").inner_text()
        return int(h.split()[0])

    # 1. Initial render
    try:
        page.wait_for_selector("text=products found", timeout=30000)
        n0 = found_count()
        step("initial_render", True, f"initial count={n0}")
    except Exception as e:
        n0 = -1
        step("initial_render", False, repr(e))
    page.screenshot(path=str(OUT / "01_initial.png"), full_page=True)

    def set_method(method: str):
        # Radix select: click trigger, then option
        page.locator("button[role='combobox']").click()
        page.locator(f"[role='option']:has-text('{method}')").click()
        time.sleep(0.3)

    def set_url_query(q: str):
        inp = page.locator("input").filter(has_not_text="x").nth(0)
        # the url input is the only visible text input in the form row
        inp.fill(q)
        time.sleep(0.3)

    def send() -> str:
        page.locator("button", has_text="Send").click()
        # wait for Status text to update
        time.sleep(2.0)
        return page.locator("text=Status:").inner_text()

    # 2. POST via UI
    try:
        set_method("POST")
        # after switching, url_query stays "products" (already set for GET default)
        body = page.locator("textarea")
        body.fill(product_body("UI1", "ui product"))
        status = send()
        # wait for background reload (2s poll)
        deadline = time.time() + 10
        n1 = found_count()
        while n1 != n0 + 1 and time.time() < deadline:
            time.sleep(1)
            n1 = found_count()
        step("ui_post", "200" in status and n1 == n0 + 1, f"status={status!r} count {n0}->{n1}")
    except Exception as e:
        step("ui_post", False, repr(e))
    page.screenshot(path=str(OUT / "02_after_post.png"), full_page=True)

    # 3. GET via UI
    try:
        set_method("GET")
        set_url_query("products")
        status = send()
        resp = page.locator("code").all_inner_texts()
        joined = "\n".join(resp)
        step("ui_get", "200" in status and "UI1" in joined, f"status={status!r} has_UI1={'UI1' in joined}")
    except Exception as e:
        step("ui_get", False, repr(e))
    page.screenshot(path=str(OUT / "03_after_get.png"), full_page=True)

    # find the id of UI1 via the API for the PUT/DELETE steps
    ui1_id = None
    try:
        r = httpx.get(f"{API}/products", timeout=10)
        ui1_id = next(p_["id"] for p_ in r.json() if p_["code"] == "UI1")
    except Exception as e:
        print("could not resolve UI1 id:", e)

    # 4. PUT via UI
    try:
        set_method("PUT")
        set_url_query(f"products/{ui1_id}")
        page.locator("textarea").fill(json.dumps({"label": "renamed by UI"}))
        status = send()
        deadline = time.time() + 10
        ok = False
        while time.time() < deadline:
            if page.locator("text=renamed by UI").count() > 0:
                ok = True
                break
            time.sleep(1)
        step("ui_put", "200" in status and ok, f"status={status!r} renamed_visible={ok}")
    except Exception as e:
        step("ui_put", False, repr(e))
    page.screenshot(path=str(OUT / "04_after_put.png"), full_page=True)

    # 5. DELETE via UI
    try:
        set_method("DELETE")
        set_url_query(f"products/{ui1_id}")
        status = send()
        deadline = time.time() + 10
        n2 = found_count()
        while n2 != n0 and time.time() < deadline:
            time.sleep(1)
            n2 = found_count()
        step("ui_delete", "200" in status and n2 == n0, f"status={status!r} count back to {n2}")
    except Exception as e:
        step("ui_delete", False, repr(e))
    page.screenshot(path=str(OUT / "05_after_delete.png"), full_page=True)

    # 6. Direct API flows
    try:
        r = httpx.get(f"{API}/ping", timeout=10)
        step("api_ping", r.status_code == 200, f"{r.status_code} {r.text[:40]}")
    except Exception as e:
        step("api_ping", False, repr(e))

    try:
        r = httpx.post(f"{API}/products", content=product_body("API1", "api product"), timeout=10)
        ok_post = r.status_code == 200 and r.json() == "OK"
        r2 = httpx.get(f"{API}/products", timeout=10)
        prods = r2.json()
        api1 = next((p_ for p_ in prods if p_["code"] == "API1"), None)
        step("api_post_list", ok_post and api1 is not None, f"post={r.status_code} listed={api1 is not None}")

        pid = api1["id"] if api1 else None
        r3 = httpx.get(f"{API}/products/{pid}", timeout=10)
        step("api_get_one", r3.status_code == 200 and r3.json().get("code") == "API1", f"{r3.status_code} {r3.text[:80]}")

        r4 = httpx.put(f"{API}/products/{pid}", content=json.dumps({"label": "api renamed"}), timeout=10)
        r5 = httpx.get(f"{API}/products/{pid}", timeout=10)
        step(
            "api_put",
            r4.status_code == 200 and r5.json().get("label") == "api renamed",
            f"put={r4.status_code} label={r5.json().get('label')!r}",
        )

        r6 = httpx.delete(f"{API}/products/{pid}", timeout=10)
        r7 = httpx.get(f"{API}/products", timeout=10)
        gone = all(p_["code"] != "API1" for p_ in r7.json())
        step("api_delete", r6.status_code == 200 and gone, f"delete={r6.status_code} gone={gone}")
    except Exception as e:
        step("api_crud", False, repr(e))

    # 404 branch of get_product returns HTTPException as a *body* (app quirk)
    try:
        r = httpx.get(f"{API}/products/999999", timeout=10)
        step("api_get_missing", True, f"{r.status_code} body={r.text[:80]}")
    except Exception as e:
        step("api_get_missing", False, repr(e))

    time.sleep(1.0)
    page.screenshot(path=str(OUT / "06_final.png"), full_page=True)
    ctx.close()
    browser.close()

BENIGN = ("HydrateFallback", "[vite] connecting", "[vite] connected", "React DevTools")
noteworthy = [
    m
    for m in console_msgs
    if m["type"] in ("error", "warning") and not any(b in m["text"] for b in BENIGN)
]
out = {
    "url": URL,
    "api": API,
    "steps": results,
    "console_all": console_msgs,
    "console_noteworthy": noteworthy,
    "failed_requests": failed_requests,
    "bad_responses": bad_responses,
}
(OUT / "result.json").write_text(json.dumps(out, indent=2))
print("noteworthy console:", json.dumps(noteworthy, indent=2))
print("failed_requests:", failed_requests)
print("bad_responses:", bad_responses)
sys.exit(0 if all(r["ok"] for r in results) else 1)
