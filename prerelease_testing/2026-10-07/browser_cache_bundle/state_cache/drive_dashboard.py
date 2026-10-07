"""Compare browser-visible state with a plain-Python order oracle."""

import copy
import gzip
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable


def line(sku, price, qty):
    """Create an expected line independent of the application implementation.

    Args:
        sku: Product identifier.
        price: Unit price in cents.
        qty: Ordered quantity.

    Returns:
        A plain dictionary line.
    """
    return {
        "sku": sku,
        "unit_cents": price,
        "qty": qty,
        "options": {"tags": ["fresh"], "attributes": {"warehouse": {"zone": "A"}}},
    }


def initial():
    """Create the expected independent session defaults.

    Returns:
        Plain Python expected state.
    """
    return {
        "lines": [line("tea", 700, 2), line("mug", 1200, 1)],
        "inventory": {"tea": {"stock": 10}, "mug": {"stock": 20}},
        "rules": {"discount": {"percent": 0}},
        "matrix": [[1]],
        "notes": [],
        "receipt": "",
        "background_steps": 0,
    }


def subtotal(state):
    """Calculate expected cents using independent plain dictionaries.

    Args:
        state: Expected state.

    Returns:
        Sum of line prices times quantities.
    """
    return sum(item["qty"] * item["unit_cents"] for item in state["lines"])


def apply(state, operation):
    """Advance the independent expected model by one operation.

    Args:
        state: Expected state, updated in place.
        operation: Dashboard operation.
    """
    lines = state["lines"]
    if operation in ("quantity", "list_alias"):
        lines[0]["qty"] += 1
    elif operation == "nested":
        lines[0]["options"]["tags"].append("gift")
        lines[0]["options"]["attributes"]["warehouse"]["zone"] = "B"
    elif operation == "iterate":
        for item in lines:
            item["qty"] += 1
    elif operation == "sorted":
        for item in lines:
            item["unit_cents"] += 25
    elif operation == "slice":
        lines[0]["qty"] += 2
    elif operation == "append":
        lines.append(line("cocoa", 450, 2))
        lines[-1]["options"]["tags"].append("new")
    elif operation in ("dict_values", "dict_items", "dict_keys"):
        for item in state["inventory"].values():
            item["stock"] -= 1
    elif operation == "inventory_assign":
        pass
    elif operation == "dict_get":
        state["inventory"]["tea"]["stock"] -= 2
    elif operation == "setdefault":
        state["inventory"]["cocoa"] = {"stock": 7}
    elif operation == "dict_update":
        state["inventory"]["tea"]["stock"] = 3
    elif operation == "discount":
        state["rules"]["discount"]["percent"] = 10
    elif operation == "private":
        state["notes"].append("packed")
    elif operation == "defaults":
        state["matrix"][0].append(2)
    elif operation == "reverse":
        lines.reverse()
    elif operation == "sort_inplace":
        lines.sort(key=lambda item: item["sku"])
    elif operation == "replace":
        lines[0]["qty"] = 7
    elif operation in ("read_only", "cache_between"):
        before = subtotal(state)
        if operation == "cache_between":
            lines[0]["qty"] += 1
        state["receipt"] = {"before": before, "after": subtotal(state)}
    elif operation == "pop":
        lines.pop()
    elif operation == "slice_replace":
        state["lines"] = initial()["lines"]
    elif operation == "background":
        lines[0]["qty"] += 3
        state["notes"].extend(["bg"] * 3)
        state["background_steps"] += 3
    elif operation == "sibling":
        lines[0]["qty"] += 3
    elif operation == "reset":
        state.clear()
        state.update(initial())
    else:
        raise ValueError(operation)


def projection(state):
    """Expand independent state into every expected UI projection.

    Args:
        state: The expected plain state.

    Returns:
        Values expected for each visible field.
    """
    total = subtotal(state)
    net = total * (100 - state["rules"]["discount"]["percent"]) // 100
    return {
        "raw-lines": state["lines"],
        "cached-lines": state["lines"],
        "uncached-lines": state["lines"],
        "inventory": state["inventory"],
        "rules": state["rules"],
        "matrix": state["matrix"],
        "notes": state["notes"],
        "receipt": state["receipt"],
        "ranked": [
            item["sku"]
            for item in sorted(
                state["lines"], key=lambda item: (-item["qty"], item["sku"])
            )
        ],
        "subtotal": total,
        "uncached-subtotal": total,
        "net": net,
        "invoice": net + 50,
        "quote": net + 50,
        "stock": sum(item["stock"] for item in state["inventory"].values()),
        "background-steps": state["background_steps"],
        "rows": [
            f"{item['sku']} × {item['qty']} @ {item['unit_cents']}"
            for item in state["lines"]
        ],
    }


def snapshot(page):
    """Read visible dashboard values atomically from the DOM.

    Args:
        page: The browser page.

    Returns:
        Parsed visible values.
    """
    ids = list(projection(initial()))
    raw = page.evaluate(
        "ids => Object.fromEntries(ids.map(id => [id, id === 'rows' ? Array.from(document.querySelectorAll('.line-row')).map(x => x.textContent) : document.getElementById(id)?.textContent]))",
        ids,
    )
    for key in (
        "raw-lines",
        "cached-lines",
        "uncached-lines",
        "inventory",
        "rules",
        "matrix",
        "notes",
        "ranked",
        "receipt",
    ):
        if raw.get(key):
            try:
                raw[key] = json.loads(raw[key])
            except (TypeError, ValueError):
                pass
    for key in (
        "subtotal",
        "uncached-subtotal",
        "net",
        "invoice",
        "quote",
        "stock",
        "background-steps",
    ):
        try:
            raw[key] = int(raw[key].split(":")[-1].strip())
        except (AttributeError, ValueError, TypeError):
            pass
    return raw


def run_browser(base, out, engine):
    """Run mutation and multi-session correctness checks in one browser engine.

    Args:
        base: App URL.
        out: Evidence directory.
        engine: Playwright browser engine.

    Returns:
        Compact run result with per-step expected/actual comparisons.
    """
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    result = {"engine": engine, "checks": [], "messages": [], "frames": []}
    sessions = {}

    def attach(page, name):
        """Attach bounded browser instrumentation.

        Args:
            page: Browser page.
            name: Session identifier.
        """
        page.on(
            "console",
            lambda message: result["messages"].append(
                {"session": name, "type": message.type, "text": message.text}
            ),
        )
        page.on(
            "pageerror",
            lambda error: result["messages"].append(
                {
                    "session": name,
                    "type": "pageerror",
                    "text": str(error),
                    "stack": error.stack,
                }
            ),
        )
        page.on(
            "requestfailed",
            lambda request: result["messages"].append(
                {
                    "session": name,
                    "type": "requestfailed",
                    "url": request.url,
                    "failure": request.failure,
                }
            ),
        )
        page.on(
            "response",
            lambda response: (
                result["messages"].append(
                    {
                        "session": name,
                        "type": "http_error",
                        "url": response.url,
                        "status": response.status,
                    }
                )
                if response.status >= 400
                else None
            ),
        )

        def socket(ws):
            """Capture bounded websocket event payloads.

            Args:
                ws: Browser websocket.
            """
            for event in ("framesent", "framereceived"):
                ws.on(
                    event,
                    lambda payload, direction=event: (
                        result["frames"].append(
                            {
                                "session": name,
                                "direction": direction,
                                "payload": str(payload),
                            }
                        )
                        if len(result["frames"]) < 4000
                        else None
                    ),
                )

        page.on("websocket", socket)

    def check(page, state, name, timeout=8):
        """Poll for every expected visible value and retain failures.

        Args:
            page: Browser page.
            state: Independent expected state.
            name: Step name.
            timeout: Maximum convergence time.
        """
        expected = projection(state)
        deadline = time.monotonic() + timeout
        actual = {}
        while time.monotonic() < deadline:
            actual = snapshot(page)
            if actual == expected:
                break
            page.wait_for_timeout(100)
        mismatch = {
            key: {"expected": value, "actual": actual.get(key)}
            for key, value in expected.items()
            if actual.get(key) != value
        }
        result["checks"].append(
            {
                "name": name,
                "passed": not mismatch,
                "mismatches": copy.deepcopy(mismatch),
                "actual": actual,
            }
        )
        print(
            f"{engine} {name}: {'PASS' if not mismatch else 'FAIL ' + ','.join(mismatch)}",
            flush=True,
        )
        if mismatch and sum(not item["passed"] for item in result["checks"]) <= 4:
            page.screenshot(path=str(out / f"{engine}-{name}.png"), full_page=True)

    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch()
        result["browser_version"] = browser.version
        try:
            for name in ("a", "b"):
                context = browser.new_context(viewport={"width": 1360, "height": 1000})
                page = context.new_page()
                page.set_default_timeout(15000)
                attach(page, name)
                page.goto(base)
                sessions[name] = (context, page, initial())
                check(page, initial(), f"{name}-initial", timeout=30)
            _, page, state = sessions["a"]
            operations = [
                "quantity",
                "nested",
                "iterate",
                "sorted",
                "slice",
                "list_alias",
                "append",
                "dict_values",
                "dict_items",
                "dict_get",
                "setdefault",
                "dict_update",
                "discount",
                "private",
                "defaults",
                "reverse",
                "sort_inplace",
                "replace",
                "cache_between",
                "read_only",
                "background",
                "sibling",
                "pop",
                "slice_replace",
            ]
            for index, operation in enumerate(operations):
                page.locator(f"#op-{operation}").click()
                apply(state, operation)
                check(page, state, f"a-{operation}")
                if index % 5 == 4:
                    check(sessions["b"][1], sessions["b"][2], f"b-isolation-{index}")
            page.screenshot(path=str(out / f"{engine}-mutated.png"), full_page=True)
            page.reload()
            check(page, state, "a-reload")
            _, other, other_state = sessions["b"]
            for operation in ("quantity", "nested", "defaults"):
                other.locator(f"#op-{operation}").click()
                apply(other_state, operation)
                check(other, other_state, f"b-{operation}")
            check(page, state, "a-isolation-after-b")
            other.reload()
            check(other, other_state, "b-reload")
            fresh = browser.new_context(viewport={"width": 1360, "height": 1000})
            fresh_page = fresh.new_page()
            attach(fresh_page, "c")
            fresh_page.goto(base)
            sessions["c"] = (fresh, fresh_page, initial())
            check(fresh_page, initial(), "c-late-fresh-defaults")
            page.locator("#op-reset").click()
            apply(state, "reset")
            check(page, state, "a-reset")
            check(other, other_state, "b-after-a-reset")
            page.screenshot(path=str(out / f"{engine}-reset.png"), full_page=True)
            for operation in ("dict_values", "dict_items", "dict_keys"):
                name = f"isolated-{operation}"
                context = browser.new_context(viewport={"width": 1360, "height": 1000})
                isolated = context.new_page()
                attach(isolated, name)
                isolated.goto(base)
                model = initial()
                sessions[name] = (context, isolated, model)
                check(isolated, model, f"{name}-initial")
                isolated.locator(f"#op-{operation}").click()
                apply(model, operation)
                check(isolated, model, f"{name}-mutation")
                if operation != "dict_keys":
                    isolated.reload()
                    check(isolated, model, f"{name}-reload")
                    isolated.locator("#op-inventory_assign").click()
                    check(isolated, model, f"{name}-explicit-assignment")
        except Exception as error:
            result["driver_error"] = f"{type(error).__name__}: {error}"
            print(result["driver_error"], flush=True)
        finally:
            for context, _, _ in sessions.values():
                context.close()
            browser.close()
    for key in ("messages", "frames"):
        payload = result.pop(key)
        (out / f"{engine}-{key}.json.gz").write_bytes(
            gzip.compress(json.dumps(payload, ensure_ascii=False).encode(), mtime=0)
        )
        result[f"{key}_count"] = len(payload)
        if key == "messages":
            result["anomalies"] = [
                item
                for item in payload
                if item["type"]
                in ("warning", "error", "pageerror", "requestfailed", "http_error")
            ]
    result["passed"] = not result.get("driver_error") and all(
        item["passed"] for item in result["checks"]
    )
    (out / f"{engine}-results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    return result
