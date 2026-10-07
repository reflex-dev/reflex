"""Measure real browser actions only after explicit quiet authorization."""

import argparse
import gzip
import json
import os
import statistics
import time
from pathlib import Path

import playwright
from playwright.sync_api import expect, sync_playwright

SB = Path(os.environ["REFLEX_TEST_SB"])
assert str(SB / "envs/driver/lib") in playwright.__file__, playwright.__file__
parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("output")
parser.add_argument("--smoke", action="store_true")
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
assert args.smoke or os.environ.get("PERF_QUIET_CONFIRMED") == "1", (
    "Explicit quiet authorization is required."
)
output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
ws_pending = {}
ws_replies = {}
result = {
    "load_average_before": os.getloadavg(),
    "url": args.url,
    "smoke": args.smoke,
    "checks": [],
    "errors": [],
    "observations": [],
    "warnings": [],
    "cancellations": [],
    "runs": [],
    "frames": [],
}


def observe_page(page, context_label):
    """Capture every required diagnostic channel with explicit classification.

    Args:
        page: Preflight or measured browser page.
        context_label: Stable label identifying the observation context.
    """

    def record(kind, details, severity="error"):
        """Classify and preserve one observed diagnostic.

        Args:
            kind: Browser diagnostic channel.
            details: Channel-specific evidence.
            severity: Error or warning classification before cancellation handling.
        """
        entry = {"context": context_label, "kind": kind, **details}
        text = str(details.get("text", "")).lower()
        canceled = any(
            marker in text
            for marker in ("err_aborted", "ns_binding_aborted", "cancelled", "canceled")
        )
        if kind in ("requestfailed", "console") and canceled:
            entry["classification"] = "cancellation-retained-for-review"
            result["cancellations"].append(entry)
        elif severity == "warning":
            entry["classification"] = "warning-retained-for-review"
            result["warnings"].append(entry)
        else:
            entry["classification"] = "error-invalidates-run"
            result["errors"].append(entry)
        result["observations"].append(entry)

    page.on(
        "pageerror",
        lambda error: record("pageerror", {"text": str(error), "page_url": page.url}),
    )
    page.on(
        "console",
        lambda message: (
            record(
                "console",
                {
                    "text": message.text,
                    "type": message.type,
                    "location": message.location,
                },
                severity=message.type,
            )
            if message.type in ("warning", "error")
            else None
        ),
    )
    page.on(
        "requestfailed",
        lambda request: record(
            "requestfailed",
            {
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
                "text": request.failure,
            },
        ),
    )
    page.on(
        "response",
        lambda response: (
            record(
                "http",
                {
                    "url": response.url,
                    "status": response.status,
                    "resource_type": response.request.resource_type,
                    "text": f"HTTP {response.status}",
                },
            )
            if response.status >= 400
            else None
        ),
    )


def record_frame(direction, payload, run):
    """Record websocket application payloads and comparable driver timestamps.

    Args:
        direction: Sent or received frame direction.
        payload: Browser websocket payload.
        run: Independent browser-context repeat.
    """
    at_ns = time.perf_counter_ns() if not args.smoke else None
    result["frames"].append(
        {"direction": direction, "payload": str(payload), "run": run, "at_ns": at_ns}
    )
    if not str(payload).startswith("42/_event,"):
        return
    message = json.loads(str(payload).split(",", 1)[1])[1]
    if direction == "sent" and message.get("name", "").endswith(".process_shipments"):
        ws_pending[run] = at_ns
    elif direction == "received":
        for wire_delta in message.get("delta", {}).values():
            delta = {
                name.removesuffix("_rx_state_"): value
                for name, value in wire_delta.items()
            }
            sequence = delta.get("sequence")
            if sequence and run in ws_pending:
                ws_replies[(run, sequence)] = {
                    "ws_roundtrip_ns": at_ns - ws_pending[run] if at_ns else None,
                    "all_50_correct": all(
                        delta.get(f"value_{index}") == sequence for index in range(50)
                    ),
                }


try:
    with sync_playwright() as engine:
        browser = engine.chromium.launch()
        result["browser"] = browser.version
        preflight = browser.new_context(viewport={"width": 1100, "height": 760})
        preview = preflight.new_page()
        observe_page(preview, "preflight")
        preview.on(
            "websocket",
            lambda socket: (
                socket.on(
                    "framesent",
                    lambda payload: record_frame("sent", payload, "preflight"),
                ),
                socket.on(
                    "framereceived",
                    lambda payload: record_frame("received", payload, "preflight"),
                ),
            ),
        )
        preview.goto(args.url, wait_until="networkidle")
        preview.locator("#validate").click()
        expect(preview.locator("#sequence")).to_have_text("1")
        expect(preview.locator("#order-valid")).to_have_text("true")
        expect(preview.locator("#rank-checksum")).to_have_text("31273879436")
        expect(preview.locator("#checksum")).to_have_text("2497500")
        result["checks"].append(
            {
                "name": "untimed-actual-handler-sort-preflight",
                "pass": True,
                "expected_rank_checksum": 31273879436,
            }
        )
        preview.goto(args.url.rstrip("/") + "/compile", wait_until="networkidle")
        expect(preview.locator(".compile-panel")).to_have_count(10)
        expected_expressions = [
            (7 + offset) * (offset + 1)
            if (7 + offset) % 3 == 0
            else (7 - offset) * (offset + 2)
            for offset in range(200)
        ]
        expected_foreach = [
            value + 7 if value % 2 == 0 else value * 7 for value in range(200)
        ]
        for panel in range(10):
            expressions = preview.locator(f"#panel-{panel} .expression-values > span")
            foreach = preview.locator(f"#panel-{panel} .foreach-values > span")
            expect(expressions).to_have_count(200)
            expect(foreach).to_have_count(200)
            actual_expressions = [int(text) for text in expressions.all_text_contents()]
            actual_foreach = [int(text) for text in foreach.all_text_contents()]
            assert actual_expressions == expected_expressions, (
                panel,
                actual_expressions[:3],
                actual_expressions[-2:],
            )
            assert actual_foreach == expected_foreach, (
                panel,
                actual_foreach[:3],
                actual_foreach[-2:],
            )
        result["checks"].append(
            {
                "name": "untimed-compile-route-semantics",
                "pass": True,
                "panels": 10,
                "conditional_values": 2000,
                "foreach_values": 2000,
                "expression_samples": [
                    expected_expressions[i] for i in (0, 1, 2, 198, 199)
                ],
                "foreach_samples": [expected_foreach[i] for i in (0, 1, 2, 198, 199)],
            }
        )
        preflight.close()
        for repeat in range(1 if args.smoke else args.repeats):
            context = browser.new_context(viewport={"width": 1100, "height": 760})
            page = context.new_page()
            observe_page(
                page, f"measured-{repeat}" if not args.smoke else f"smoke-{repeat}"
            )
            page.on(
                "websocket",
                lambda socket: (
                    socket.on(
                        "framesent",
                        lambda payload: record_frame("sent", payload, repeat),
                    ),
                    socket.on(
                        "framereceived",
                        lambda payload: record_frame("received", payload, repeat),
                    ),
                ),
            )
            page.goto(args.url, wait_until="networkidle")
            expect(page.locator("#sequence")).to_have_text("0")
            if not args.smoke:
                page.evaluate("""() => {
                    window.__clickSamples = [];
                    window.__clickStarted = null;
                    document.addEventListener('click', event => {
                        if (event.target.closest('#process')) window.__clickStarted = performance.now();
                    }, true);
                    new MutationObserver(() => {
                        if (window.__clickStarted !== null) {
                            window.__clickSamples.push({sequence: Number(document.querySelector('#sequence').textContent), ms: performance.now() - window.__clickStarted});
                            window.__clickStarted = null;
                        }
                    }).observe(document.querySelector('#sequence'), {childList: true, characterData: true, subtree: true});
                }""")
            samples = []
            for index in range(2 if args.smoke else 55):
                sequence = index + 1
                page.locator("#process").click()
                expect(page.locator("#sequence")).to_have_text(str(sequence))
                expect(page.locator("#checksum")).to_have_text("2497500")
                expect(page.locator("#first-value")).to_have_text(str(sequence))
                expect(page.locator("#last-value")).to_have_text(str(sequence))
                reply = ws_replies[(repeat, sequence)]
                assert reply["all_50_correct"], reply
                if not args.smoke and index >= 5:
                    native = page.evaluate("window.__clickSamples.at(-1)")
                    assert native["sequence"] == sequence, native
                    samples.append(
                        {
                            "sequence": sequence,
                            "click_to_dom_ms": native["ms"],
                            **reply,
                            "handler_wall_ns": int(
                                page.locator("#work-ns").inner_text()
                            ),
                            "handler_cpu_ns": int(
                                page.locator("#work-cpu-ns").inner_text()
                            ),
                        }
                    )
            result["checks"].append(
                {
                    "repeat": repeat,
                    "actions": sequence,
                    "checksum": 2497500,
                    "pass": True,
                }
            )
            row = {"repeat": repeat, "samples": samples}
            if samples:
                row["medians"] = {
                    field: statistics.median(sample[field] for sample in samples)
                    for field in (
                        "click_to_dom_ms",
                        "handler_wall_ns",
                        "handler_cpu_ns",
                        "ws_roundtrip_ns",
                    )
                }
            result["runs"].append(row)
            if repeat == 0:
                page.screenshot(path=str(output.with_suffix(".png")))
            context.close()
        browser.close()
except Exception as error:
    result["errors"].append({"kind": "driver", "text": repr(error)})
finally:
    result["load_average_after"] = os.getloadavg()
    with gzip.open(output.with_suffix(".json.gz"), "wt") as handle:
        json.dump(result, handle, indent=1)
    summary = {key: value for key, value in result.items() if key != "frames"}
    for row in summary["runs"]:
        row["sample_count"] = len(row.pop("samples"))
    output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))
raise SystemExit(1 if result["errors"] or not result["checks"] else 0)
