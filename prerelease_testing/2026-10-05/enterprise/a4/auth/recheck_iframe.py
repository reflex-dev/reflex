"""Repeat the default-scope iframe pending replay with inert message diagnostics."""

import json
import re
import traceback
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:3132"


def main() -> None:
    """Observe three fresh embedded login flows and their pending events."""
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for attempt in range(1, 4):
            context = browser.new_context()
            context.add_init_script("""
                window._qaMessages = [];
                addEventListener('message', event => {
                    if (event.data?.type?.startsWith('post_auth_')) {
                        window._qaMessages.push({origin: event.origin, type: event.data.type});
                    }
                });
            """)
            page = context.new_page()
            record = {"attempt": attempt, "page_errors": []}
            page.on(
                "pageerror",
                lambda error, target=record: target["page_errors"].append(str(error)),
            )
            page.goto(BASE + "/iframe")
            frame = page.frame_locator("iframe")
            frame.get_by_role("button", name="Reveal", exact=True).click()
            with page.expect_popup() as opened:
                frame.get_by_role(
                    "button", name="Login with Generic", exact=True
                ).click()
            popup = opened.value
            popup.wait_for_url(re.compile("/oauth2/authorize"))
            popup.locator('button[name="sub"][value="alice"]').click()
            popup.wait_for_event("close")
            try:
                expect(frame.locator("#message")).to_have_text("revealed-alice")
                record["passed"] = True
            except AssertionError:
                record["passed"] = False
                record["traceback"] = traceback.format_exc()
                try:
                    expect(frame.locator("#message")).to_have_text(
                        "revealed-alice", timeout=10000
                    )
                    record["delivered_after_extra_wait"] = True
                except AssertionError:
                    record["delivered_after_extra_wait"] = False
            child = next(item for item in page.frames if item.parent_frame)
            record["frame_url"] = child.url
            record["pending_event"] = child.evaluate(
                "sessionStorage.getItem('rxe_auth_pending_event')"
            )
            record["received_message_types"] = child.evaluate("window._qaMessages")
            record["frame_text"] = child.locator("body").inner_text()
            page.screenshot(
                path=str(ROOT / "screenshots" / f"iframe-repeat-{attempt}.png")
            )
            if not record["passed"]:
                child.goto(BASE + "/")
                try:
                    expect(child.locator("#message")).to_have_text(
                        "revealed-alice", timeout=10000
                    )
                    record["direct_child_navigation_recovery"] = {
                        "replayed": True,
                        "pending_consumed": not child.evaluate(
                            "sessionStorage.getItem('rxe_auth_pending_event')"
                        ),
                    }
                except AssertionError:
                    record["direct_child_navigation_recovery"] = {"replayed": False}
            results.append(record)
            print(
                json.dumps(
                    {
                        key: record[key]
                        for key in (
                            "attempt",
                            "passed",
                            "frame_url",
                            "delivered_after_extra_wait",
                            "direct_child_navigation_recovery",
                        )
                        if key in record
                    }
                ),
                flush=True,
            )
            (ROOT / "logs/iframe-repeat.json").write_text(
                json.dumps(results, indent=2) + "\n"
            )
            context.close()
        browser.close()


if __name__ == "__main__":
    main()
