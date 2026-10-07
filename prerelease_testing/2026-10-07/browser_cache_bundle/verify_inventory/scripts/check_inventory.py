"""Compare direct UI, cached total, backend audit and websocket deltas."""

import gzip
import json
import os
import sys
from pathlib import Path
import playwright

assert (
    str(Path(os.environ["REFLEX_TEST_SB"]) / "envs/driver/lib") in playwright.__file__
), playwright.__file__
from playwright.sync_api import sync_playwright, expect

base, label, outstr = sys.argv[1:]
out = Path(outstr)
out.mkdir(parents=True, exist_ok=True)
result = {
    "label": label,
    "checks": [],
    "steps": [],
    "console": [],
    "pageerrors": [],
    "failed_requests": [],
    "http_errors": [],
    "websocket": [],
}
step = "initial"


def snapshot(page, operation):
    """Read actual rendered and backend-audited state.

    Args:
        page: Browser page.
        operation: Step identifier.

    Returns:
        Snapshot stored in the evidence.
    """
    row = {
        "step": operation,
        "tea": page.locator("#tea").inner_text(),
        "coffee": page.locator("#coffee").inner_text(),
        "total": page.locator("#total").inner_text(),
        "audit": json.loads(page.locator("#audit").inner_text() or "{}"),
    }
    result["steps"].append(row)
    print(json.dumps(row), flush=True)
    return row


def check(name, ok, detail):
    """Append one independently checkable assertion.

    Args:
        name: Assertion label.
        ok: Outcome.
        detail: Supporting UI/backend data.
    """
    result["checks"].append({"name": name, "ok": bool(ok), "detail": detail})


with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.on(
        "console",
        lambda m: result["console"].append(
            {"step": step, "type": m.type, "text": m.text}
        ),
    )
    page.on(
        "pageerror",
        lambda e: result["pageerrors"].append(
            {"step": step, "message": str(e), "stack": e.stack}
        ),
    )
    page.on(
        "requestfailed",
        lambda r: result["failed_requests"].append(
            {"step": step, "url": r.url, "error": r.failure}
        ),
    )
    page.on(
        "response",
        lambda r: (
            result["http_errors"].append(
                {"step": step, "url": r.url, "status": r.status}
            )
            if r.status >= 400
            else None
        ),
    )

    def ws(socket):
        socket.on(
            "framesent",
            lambda frame: result["websocket"].append(
                {"step": step, "direction": "sent", "payload": str(frame)}
            ),
        )
        socket.on(
            "framereceived",
            lambda frame: result["websocket"].append(
                {"step": step, "direction": "received", "payload": str(frame)}
            ),
        )

    page.on("websocket", ws)
    try:
        page.goto(base, wait_until="networkidle", timeout=90000)
        expect(page.locator("#total")).to_have_text("Total: 30")
        page.wait_for_timeout(800)
        snapshot(page, "initial")
        for operation in ("values", "items"):
            step = operation
            page.click(f"#{operation}")
            expect(page.locator("#audit")).to_contain_text(
                f'"operation": "{operation}"'
            )
            page.wait_for_timeout(300)
            first = snapshot(page, operation)
            check(
                f"{operation}_backend_mutated",
                first["audit"]["backend"] == {"tea": 9, "coffee": 19},
                first,
            )
            check(
                f"{operation}_ui_reflects_mutation",
                first["tea"] == "Tea: 9"
                and first["coffee"] == "Coffee: 19"
                and first["total"] == "Total: 28",
                first,
            )
            page.screenshot(path=str(out / f"{operation}-after-event.png"))
            step = operation + "-reload"
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(700)
            second = snapshot(page, step)
            check(
                f"{operation}_reload_total_consistent",
                second["tea"] == "Tea: 9"
                and second["coffee"] == "Coffee: 19"
                and second["total"] == "Total: 28",
                second,
            )
            page.screenshot(path=str(out / f"{operation}-after-reload.png"))
            step = operation + "-reassign"
            page.click("#reassign")
            expect(page.locator("#audit")).to_contain_text('"operation": "reassign"')
            expect(page.locator("#total")).to_have_text("Total: 28")
            healed = snapshot(page, step)
            check(
                f"{operation}_reassign_heals",
                healed["tea"] == "Tea: 9"
                and healed["coffee"] == "Coffee: 19"
                and healed["total"] == "Total: 28",
                healed,
            )
            step = "reset"
            page.click("#reset")
            expect(page.locator("#total")).to_have_text("Total: 30")
            expect(page.locator("#tea")).to_have_text("Tea: 10")
            page.wait_for_timeout(200)
        step = "keys"
        page.click("#keys")
        expect(page.locator("#audit")).to_contain_text('"operation": "keys"')
        expect(page.locator("#total")).to_have_text("Total: 28")
        direct = snapshot(page, step)
        check(
            "indexed_mutation_control",
            direct["tea"] == "Tea: 9"
            and direct["coffee"] == "Coffee: 19"
            and direct["audit"]["cached_total"] == 28,
            direct,
        )
        page.screenshot(path=str(out / "indexed-control.png"))
    except Exception as error:
        result["exception"] = repr(error)
        page.screenshot(path=str(out / "exception.png"))
    finally:
        context.close()
        browser.close()
        (out / "full.json.gz").write_bytes(
            gzip.compress(json.dumps(result, indent=1).encode(), mtime=0)
        )
        result["websocket_frames"] = len(result.pop("websocket"))
        (out / "results.json").write_text(json.dumps(result, indent=1))
