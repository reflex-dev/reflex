"""Run real Playwright interactions against the published component dashboard."""

import json
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    """Run independent dashboard scenarios and retain browser diagnostics."""
    base_url = sys.argv[1]
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    results = []
    diagnostics = {
        "console": [],
        "page_errors": [],
        "request_failures": [],
        "http_failures": [],
    }
    active_check = "initial"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        context.grant_permissions(
            ["clipboard-read", "clipboard-write"], origin=base_url
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        page.on(
            "console",
            lambda message: diagnostics["console"].append({
                "type": message.type,
                "text": message.text,
                "stage": active_check,
            }),
        )
        page.on(
            "pageerror", lambda error: diagnostics["page_errors"].append(str(error))
        )
        page.on(
            "requestfailed",
            lambda request: diagnostics["request_failures"].append({
                "url": request.url,
                "failure": request.failure,
            }),
        )
        page.on(
            "response",
            lambda response: (
                diagnostics["http_failures"].append({
                    "url": response.url,
                    "status": response.status,
                })
                if response.status >= 400
                else None
            ),
        )

        def check(name: str, action: Callable):
            """Retain one assertion group while allowing unrelated checks to run.

            Args:
                name: Scenario identifier.
                action: Browser assertion group.
            """
            nonlocal active_check
            active_check = name
            try:
                detail = action()
                results.append({"name": name, "status": "passed", "detail": detail})
            except Exception as error:
                results.append({
                    "name": name,
                    "status": "failed",
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                })
                page.screenshot(
                    path=str(output / f"failure-{name}.png"), full_page=True
                )
            print(json.dumps(results[-1]), flush=True)  # noqa: T201

        page.goto(base_url, wait_until="domcontentloaded")

        def initial_state():
            """Assert initial hydration and independent inventory state.

            Returns:
                The independent inventory counts.
            """
            expect(page.locator("#token")).not_to_have_text("")
            expect(page.locator("#inventory-alpha")).to_contain_text("Out of stock")
            expect(page.locator("#inventory-beta")).to_contain_text("Out of stock")
            expect(page.locator("#memo-match")).to_have_text("US report")
            expect(page.locator("#foreach-match")).to_contain_text("Secondary dollar")
            page.locator("#receive-alpha").click()
            expect(page.locator("#stock-alpha")).to_have_text("1")
            expect(page.locator("#inventory-alpha")).to_contain_text("In stock")
            expect(page.locator("#stock-beta")).to_have_text("0")
            return {"alpha": "1", "beta": "0"}

        check("state-match-componentstate", initial_state)

        def reports():
            """Assert Markdown structure, Shiki output and Lucide icons."""
            expect(page.locator("#markdown-report h1")).to_have_text("Weekly report")
            expect(page.locator("#markdown-report table")).to_contain_text("Ready")
            expect(page.locator("#code-in-form code")).to_contain_text(
                "print('dispatch')"
            )
            page.wait_for_function(
                "document.querySelector('#code-in-form code').querySelectorAll('span').length > 0"
            )
            expect(page.locator("#static-icon")).to_be_visible()
            expect(page.locator("#dynamic-icon")).to_be_visible()
            expect(page.locator("#code-in-form pre")).to_have_css(
                "background-color", "rgb(17, 34, 51)"
            )
            page.locator("#shiki-in-form").scroll_into_view_if_needed()
            expect(page.locator("#shiki-in-form .shiki")).to_contain_text(
                "shiki upgraded"
            )
            expect(page.locator("#shiki-in-form .highlighted")).to_be_visible()

        check("markdown-shiki-lucide", reports)

        def default_transformer():
            """Check the standard convenience flag's annotation transformer."""
            page.locator("#shiki-default").scroll_into_view_if_needed()
            expect(page.locator("#shiki-default .highlighted")).to_be_visible()

        check("shiki-default-transformer", default_transformer)

        def plot_titles():
            """Assert real Plotly SVG title strings and preserved object styles.

            Returns:
                The actual rendered SVG title strings.
            """
            expect(page.locator("#plot-static .gtitle")).to_have_text(
                "Static string title"
            )
            expect(page.locator("#plot-object .gtitle")).to_have_text(
                "Object title retained"
            )
            expect(page.locator("#plot-object .gtitle")).to_have_css(
                "fill", "rgb(128, 0, 128)"
            )
            expect(page.locator("#plot-state .gtitle")).to_have_text("Revenue overview")
            return page.locator(".gtitle").all_text_contents()

        check("plotly-initial-titles", plot_titles)

        def live_analytics():
            """Update metadata-bearing FunctionVar formatters and memoized Plotly.

            Returns:
                The changed axis ticks and title text.
            """
            expect(page.locator("#recharts-panel")).to_contain_text("$")
            page.locator("#update-analytics").click()
            expect(page.locator("#memo-match")).to_have_text("European report")
            expect(page.locator("#recharts-panel")).to_contain_text("€")
            expect(page.locator("#recharts-panel")).to_contain_text("Apr")
            expect(page.locator("#foreach-match")).to_contain_text("Secondary euro")
            expect(page.locator("#plot-state .gtitle")).to_have_text("Updated revenue")
            expect(page.locator("#code-in-form pre")).to_have_css(
                "background-color", "rgb(51, 34, 17)"
            )
            return {
                "ticks": page.locator("#recharts-panel").text_content(),
                "title": page.locator("#plot-state .gtitle").text_content(),
            }

        check("state-functionvar-memo-chart-update", live_analytics)

        def local_view():
            """Update a sibling client state consumer."""
            expect(page.locator("#local-mode")).to_have_text("compact")
            page.locator("#local-mode-button").click()
            expect(page.locator("#local-mode")).to_have_text("detailed")

        check("client-state", local_view)

        def dispatch_form():
            """Submit real custom and ID controls while excluding other element IDs.

            Returns:
                The actual backend submission payload.
            """
            expect(page.locator("#submitted")).to_have_text("")
            page.locator("#code-in-form button").click()
            expect(page.locator("#submitted")).to_have_text("")
            page.wait_for_function(
                "navigator.clipboard.readText().then(value => value === \"print('dispatch')\")"
            )
            page.locator("#shiki-in-form button").click()
            expect(page.locator("#submitted")).to_have_text("")
            page.wait_for_function(
                "navigator.clipboard.readText().then(value => value.includes('shiki upgraded') && !value.includes('[!code'))"
            )
            page.locator("#contact").fill("shipping@example.com")
            page.locator("#dispatch-submit").click()
            expect(page.locator("#submitted")).not_to_have_text("")
            payload = json.loads(page.locator("#submitted").inner_text())
            assert payload == {
                "contact": "shipping@example.com",
                "custom_control": "custom-value",
                "empty_control": "",
                "notes": "Ready for dispatch",
            }, payload
            return payload

        check("form-id-filter-custom-control-copy-button", dispatch_form)

        def slider_progress():
            """Move the Radix slider through keyboard interaction.

            Returns:
                The accessible value of the Themes progress bar.
            """
            slider = page.locator("#progress-slider [role=slider]")
            slider.focus()
            slider.press("End")
            expect(page.locator("#progress-value")).to_have_text("100")
            expect(slider).to_have_attribute("aria-valuenow", "100")
            primitive = page.locator("#primitive-slider [role=slider]")
            primitive.focus()
            primitive.press("Home")
            expect(page.locator("#progress-value")).to_have_text("0")
            primitive.press("End")
            expect(page.locator("#progress-value")).to_have_text("100")
            expect(page.locator("#primitive-progress > div")).to_have_css(
                "transform", "matrix(1, 0, 0, 1, 0, 0)"
            )
            return page.locator("#progress-bar").get_attribute("aria-valuenow")

        check("radix-slider-progress", slider_progress)

        def primitive_progress_accessibility():
            """Check the primitive root exposes its actual progress value."""
            expect(page.locator("#primitive-progress")).to_have_attribute(
                "aria-valuenow", "100"
            )

        check(
            "radix-primitive-progress-accessibility", primitive_progress_accessibility
        )

        def moments():
            """Assert Moment locale isolation and duration formatting.

            Returns:
                The actual date and duration strings.
            """
            expect(page.locator("#moment-english")).to_have_text(
                "Thursday 14 March 2024"
            )
            expect(page.locator("#moment-french")).to_have_text("jeudi 14 mars 2024")
            expect(page.locator("#moment-duration")).to_have_text("30 mins")
            expect(page.locator("#moment-timezone")).to_have_text("2024-03-14 16:00")
            return [
                page.locator(f"#{name}").inner_text()
                for name in ["moment-english", "moment-french", "moment-duration"]
            ]

        check("moment-locales-duration", moments)

        def attachments():
            """Upload two real text attachments through the updated dropzone.

            Returns:
                Uploaded filenames and byte counts recorded by the backend.
            """
            page.locator("#attachments input[type=file]").set_input_files([
                {
                    "name": "dispatch.txt",
                    "mimeType": "text/plain",
                    "buffer": b"dispatch",
                },
                {"name": "stock.txt", "mimeType": "text/plain", "buffer": b"stock"},
            ])
            page.locator("#send-attachments").click()
            expect(page.locator("#uploaded")).not_to_have_text("")
            payload = json.loads(page.locator("#uploaded").inner_text())
            assert payload == [
                {"bytes": 8, "name": "dispatch.txt"},
                {"bytes": 5, "name": "stock.txt"},
            ], payload
            return payload

        check("dropzone-upload-roundtrip", attachments)

        def toast_action():
            """Trigger a toast in the frontend and dispatch its action to State."""
            page.locator("#show-toast").click()
            page.locator("[data-sonner-toast]").get_by_role(
                "button", name="Acknowledge"
            ).click()
            expect(page.locator("#toast-count")).to_have_text("1")

        check("sonner-action-state", toast_action)

        def grids():
            """Search the GridJS table and activate the Glide canvas editor.

            Returns:
                The backend record of the edited grid cell.
            """
            expect(page.locator("#gridjs-panel table")).to_contain_text("Alpha")
            page.locator("#gridjs-panel input").fill("Beta")
            expect(page.locator("#gridjs-panel tbody")).to_contain_text("Beta")
            expect(page.locator("#gridjs-panel tbody")).not_to_contain_text("Alpha")
            canvas = page.locator("#dataeditor-panel canvas").first
            expect(canvas).to_be_visible()
            page.locator("#dataeditor-panel .dvn-scroller").dblclick(
                position={"x": 30, "y": 51}
            )
            editor = page.locator(
                ".gdg-growing-entry textarea, .gdg-growing-entry input"
            ).first
            expect(editor).to_be_visible()
            editor.fill("Gamma")
            editor.press("Enter")
            expect(page.locator("#edited")).to_contain_text("Gamma")
            return page.locator("#edited").inner_text()

        check("gridjs-dataeditor", grids)

        def media():
            """Play generated local audio and observe the backend media event."""
            audio = page.locator("#media-panel audio").first
            expect(audio).to_be_visible()
            audio.evaluate("element => element.play()")
            expect(page.locator("#media-plays")).not_to_have_text("0")
            assert audio.evaluate("element => element.duration") == 3
            audio.evaluate("element => element.pause()")

        check("react-player-local-audio", media)
        page.screenshot(path=str(output / "dashboard.png"), full_page=True)
        (output / "browser-results.json").write_text(
            json.dumps(
                {
                    "base_url": base_url,
                    "browser": browser.version,
                    "results": results,
                    "diagnostics": diagnostics,
                },
                indent=2,
            )
            + "\n"
        )
        context.close()
        browser.close()
    if (
        any(result["status"] == "failed" for result in results)
        or diagnostics["page_errors"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
