"""Assert full annotation-shape snapshots through real browser events."""

import contextlib
import datetime
import gzip
import json
import time

from playwright.sync_api import sync_playwright


def expected(mutations=0, reset=False, counter=0, greeted=False, bumped=False):
    """Build the independent expected browser values.

    Args:
        mutations: Number of mutation-button events.
        reset: Whether nullable values were reset after mutation.
        counter: Completed background increments.
        greeted: Whether the ABC event ran.
        bumped: Whether the postponed-annotation event ran.

    Returns:
        Complete parsed DOM snapshot, excluding interpreter version.
    """
    nullable = None if reset or not mutations else [7] * mutations
    return {
        "l_opt": nullable,
        "d_nested": {"k": ["v1", "v2"] + ["v3"] * mutations},
        "ann": 5 + mutations,
        "point": {"x": 1 + 10 * mutations, "y": 2, "tags": ["t"] + ["t2"] * mutations},
        "pm": {
            "name": "pm",
            "tags": ["a"] + ["b"] * mutations,
            "when": "2026-01-01 00:00:00" if mutations else None,
        },
        "lit": "b" if mutations else "a",
        "color": "green" if mutations else "red",
        "when": str(
            datetime.datetime(2026, 10, 6, 12, 30) + datetime.timedelta(days=mutations)
        ),
        "fld": ["f1"] + ["f2"] * mutations,
        "uni": "two" if mutations else 1,
        "tup": [2, "two"] if mutations else [1, "one"],
        "td": {"a": 2, "b": "bee2"} if mutations else {"a": 1, "b": "bee"},
        "o_str": "none" if reset or not mutations else "now set",
        "cond-list": "has list" if nullable else "no list",
        "point-x": str(1 + 10 * mutations),
        "pm-name": "pm",
        "counter": str(counter),
        "bg_running": "false",
        "greeting": "hello world" if greeted else "hello",
        "f_summary": "[0]|fut|6|green|2030" if bumped else "None|fut|5|green|2030",
        "fld-items": ["f1"] + ["f2"] * mutations,
        "rows": [f"{i}->{i * i}" for i in range(len(nullable or []) + 1)],
    }


def snapshot(page):
    """Read visible state atomically from the page.

    Args:
        page: Playwright page.

    Returns:
        Parsed state fields and rendered iteration values.
    """
    return page.evaluate("""() => {
      const raw = ['l_opt','d_nested','ann','point','pm','lit','color','when','fld','uni','tup','td'];
      const plain = ['o_str','cond-list','point-x','pm-name','counter','bg_running','greeting','f_summary'];
      const value = Object.fromEntries(raw.map(k => [k, JSON.parse(document.getElementById('v-'+k).textContent)]));
      plain.forEach(k => value[k] = document.getElementById(k).textContent);
      value['fld-items'] = [...document.querySelectorAll('.fld-item')].map(n => n.textContent);
      value.rows = [...document.querySelectorAll('.row')].map(n => n.textContent);
      return value;
    }""")


def run_browser(args, out, engine, python_version):
    """Exercise annotation shapes, hydration and session independence.

    Args:
        args: Runner arguments.
        out: Artifact directory.
        engine: Playwright engine name.
        python_version: Exact expected backend interpreter version.

    Returns:
        Checks, browser metadata and anomalies.
    """
    result = {"engine": engine, "checks": [], "messages": [], "frames": []}

    def record(name, want, actual):
        """Retain one assertion with its exact values.

        Args:
            name: Assertion label.
            want: Expected value.
            actual: Observed value.
        """
        result["checks"].append(
            {
                "name": name,
                "passed": want == actual,
                "expected": want,
                "actual": actual,
            }
        )
        print(f"{engine} {name}: {'PASS' if want == actual else 'FAIL'}", flush=True)

    def check(page, name, want, timeout=10):
        """Wait for a complete state snapshot to converge.

        Args:
            page: Playwright page.
            name: Assertion label.
            want: Expected snapshot.
            timeout: Maximum seconds to wait.
        """
        actual = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with contextlib.suppress(Exception):
                actual = snapshot(page)
            if actual == want:
                break
            page.wait_for_timeout(100)
        record(name, want, actual)

    def attach(page, label):
        """Capture browser console, failed network requests and complete frames.

        Args:
            page: Playwright page.
            label: Session identifier.
        """
        page.on(
            "console",
            lambda item: result["messages"].append(
                {
                    "page": label,
                    "type": item.type,
                    "text": item.text,
                }
            ),
        )
        page.on(
            "pageerror",
            lambda error: result["messages"].append(
                {
                    "page": label,
                    "type": "pageerror",
                    "text": str(error),
                }
            ),
        )
        page.on(
            "requestfailed",
            lambda request: result["messages"].append(
                {
                    "page": label,
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
                        "page": label,
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
            """Capture every frame with its websocket and page identity.

            Args:
                ws: Playwright websocket.
            """
            for direction in ("framesent", "framereceived"):
                ws.on(
                    direction,
                    lambda payload, direction=direction: result["frames"].append(
                        {
                            "page": label,
                            "url": ws.url,
                            "direction": direction,
                            "payload": str(payload),
                            "time": time.time(),
                        }
                    ),
                )

        page.on("websocket", socket)

    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch()
        result["browser_version"] = browser.version
        context = browser.new_context(viewport={"width": 1100, "height": 1000})
        other_context = None
        try:
            page = context.new_page()
            attach(page, "A")
            page.goto(f"http://localhost:{args.port}")
            page.locator("#mutate").wait_for()
            check(page, "initial-all-shapes", expected(), 20)
            record(
                "backend-python", python_version, page.locator("#pyver").inner_text()
            )
            page.locator("#mutate").click()
            check(page, "nested-mutation-all-shapes", expected(1))
            page.locator("#mutate").click()
            check(page, "repeated-mutation-derived-rows", expected(2))
            page.screenshot(path=str(out / f"{engine}-mutated.png"), full_page=True)
            page.locator("#bg").click()
            check(page, "background-completion", expected(2, counter=3))
            page.locator("#greet").click()
            check(page, "abstract-mixin-event", expected(2, counter=3, greeted=True))
            page.locator("#bump").click()
            populated = expected(2, counter=3, greeted=True, bumped=True)
            check(page, "postponed-annotation-event", populated)
            page.reload()
            check(page, "reload-all-mutations", populated, 20)
            page.locator("#reset").click()
            reset = expected(2, reset=True, counter=3, greeted=True, bumped=True)
            check(page, "nullable-reset-and-derived-rows", reset)
            page.locator("#to-other").click()
            page.locator("#page-other").wait_for()
            record(
                "client-route-retains-values",
                ["3", populated["f_summary"]],
                [
                    page.locator("#other-counter").inner_text(),
                    page.locator("#other-f_summary").inner_text(),
                ],
            )
            page.reload()
            page.locator("#page-other").wait_for()
            record(
                "route-reload-retains-values",
                ["3", populated["f_summary"]],
                [
                    page.locator("#other-counter").inner_text(),
                    page.locator("#other-f_summary").inner_text(),
                ],
            )
            page.locator("#to-index").click()
            check(page, "return-route-all-values", reset, 20)
            tab = context.new_page()
            attach(tab, "B-tab")
            tab.goto(f"http://localhost:{args.port}")
            check(tab, "independent-tab-all-defaults", expected(), 20)
            tab.locator("#mutate").click()
            check(tab, "independent-tab-mutation", expected(1))
            check(page, "original-after-other-tab-mutation", reset)
            other_context = browser.new_context(
                viewport={"width": 1100, "height": 1000}
            )
            isolated = other_context.new_page()
            attach(isolated, "C-context")
            isolated.goto(f"http://localhost:{args.port}")
            check(isolated, "independent-context-default-factories", expected(), 20)
            isolated.locator("#mutate").click()
            check(isolated, "independent-context-mutation", expected(1))
            page.reload()
            check(page, "original-reload-after-independent-mutations", reset, 20)
            page.screenshot(path=str(out / f"{engine}-final.png"), full_page=True)
        except Exception as error:
            result["driver_error"] = f"{type(error).__name__}: {error}"
            print(result["driver_error"], flush=True)
        finally:
            if other_context:
                other_context.close()
            context.close()
            browser.close()
    result["anomalies"] = [
        row
        for row in result["messages"]
        if row["type"]
        in {"warning", "error", "pageerror", "requestfailed", "http_error"}
    ]
    result["passed"] = (
        not result.get("driver_error")
        and len(result["checks"]) == 18
        and all(row["passed"] for row in result["checks"])
    )
    for key in ("messages", "frames"):
        result[f"{key}_count"] = len(result[key])
        (out / f"{engine}-{key}.json.gz").write_bytes(
            gzip.compress(json.dumps(result.pop(key), indent=2).encode(), mtime=0)
        )
    (out / f"{engine}-results.json").write_text(json.dumps(result, indent=2))
    return result
