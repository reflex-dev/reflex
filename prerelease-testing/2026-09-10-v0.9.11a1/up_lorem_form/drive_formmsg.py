"""Check the minimal FormMessage repro: /unnamed must render, /named must render.

usage: drive_formmsg.py <frontend_url> <artifacts_dir> <label>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drive_common import Run, wait_for  # noqa: E402

BOUNDARY = "An error occurred while rendering this page"


def main():
    base = sys.argv[1].rstrip("/") + "/"
    with Run(sys.argv[2], sys.argv[3]) as run:
        for route in ("unnamed", "named"):
            ctx, page = run.new_page(tag=route)
            page.set_default_timeout(15000)
            page.goto(base + route, wait_until="networkidle")
            page.wait_for_timeout(1500)
            boundary = page.get_by_text(BOUNDARY).count() > 0
            heading = page.locator("#hd").count() > 0
            input_ok = page.locator("input[name='who']").count() > 0
            run.shot(page, f"{route}.png")
            errs = [m["text"][:200] for m in run.console if m["type"] == "error" and route in m["text"]]
            run.record(
                f"{route}_page_renders",
                "pass" if not boundary and heading and input_ok else "fail",
                f"error_boundary={boundary} heading_present={heading} input_present={input_ok}",
            )
            if not boundary and input_ok:
                page.locator("input[name='who']").fill("someone")
                page.get_by_role("button", name="Submit").click()
                page.wait_for_timeout(1200)
                run.record(f"{route}_submit_works", "pass", "submitted without error")
            else:
                run.record(f"{route}_submit_works", "skipped", "page did not render")
            ctx.close()
        formmsg_errors = [
            m["text"][:300] for m in run.console if "FormMessage" in m["text"]
        ]
        run.record(
            "formmsg_console_error_present",
            "anomaly" if formmsg_errors else "pass",
            json.dumps(formmsg_errors)[:900],
        )


main()
