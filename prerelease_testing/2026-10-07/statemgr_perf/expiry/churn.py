"""Observe backend RSS and bookkeeping across real short-lived sessions."""

import asyncio
import contextlib
import gzip
import hashlib
import json
import time
from pathlib import Path

from playwright.async_api import async_playwright


async def measure(metrics):
    """Read observer counts and the backend worker's resident memory.

    Args:
        metrics: Observer JSONL file.

    Returns:
        Counts and RSS in KiB for the same backend PID.
    """
    row = {}
    for line in reversed(metrics.read_text().splitlines()):
        try:
            row = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    process = await asyncio.create_subprocess_exec(
        "ps", "-o", "rss=", "-p", str(row["pid"]), stdout=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    row["rss_kib"] = int(stdout.strip()) if stdout.strip() else None
    row["sample_time"] = time.time()
    return row


async def exercise(args, out, engine, metrics):
    """Create, mutate and close bounded-concurrency browser contexts.

    Args:
        args: Run arguments.
        out: Evidence directory.
        engine: Playwright engine.
        metrics: Read-only backend observer output.

    Returns:
        Browser assertions, samples and bounded diagnostic records.
    """
    result = {
        "engine": engine,
        "checks": [],
        "contexts": [],
        "samples": [],
        "messages": [],
        "frames": [],
    }
    tokens = set()
    gate = asyncio.Semaphore(args.workers)
    sampler = None

    def record(name, expected, actual):
        """Record an aggregate correctness check.

        Args:
            name: Check name.
            expected: Expected value.
            actual: Observed value.
        """
        result["checks"].append({
            "name": name,
            "expected": expected,
            "actual": actual,
            "passed": actual == expected,
        })

    async def sample():
        """Record periodic RSS and manager counts until cancelled."""
        while True:
            result["samples"].append(await measure(metrics))
            await asyncio.sleep(1)

    async with async_playwright() as playwright:
        browser = await getattr(playwright, engine).launch()
        result["browser_version"] = browser.version

        async def context_case(index):
            """Run one session and close its context on every exit path.

            Args:
                index: Stable context identifier; minus one denotes warm-up.

            Returns:
                The per-session assertion record.
            """
            async with gate:
                start = time.time()
                row = {"index": index, "started": start}
                context = await browser.new_context()
                try:
                    page = await context.new_page()

                    def message(kind, **values):
                        """Save bounded browser diagnostics.

                        Args:
                            kind: Diagnostic category.
                            **values: Browser diagnostic details.
                        """
                        if len(result["messages"]) < 1000:
                            result["messages"].append({
                                "context": index,
                                "type": kind,
                                **values,
                            })

                    page.on(
                        "console",
                        lambda item: (
                            message(item.type, text=item.text)
                            if item.type in {"warning", "error"}
                            else None
                        ),
                    )
                    page.on(
                        "pageerror", lambda error: message("pageerror", text=str(error))
                    )
                    page.on(
                        "requestfailed",
                        lambda request: message(
                            "requestfailed", url=request.url, failure=request.failure
                        ),
                    )
                    page.on(
                        "response",
                        lambda response: (
                            message(
                                "http_error", url=response.url, status=response.status
                            )
                            if response.status >= 400
                            else None
                        ),
                    )

                    def socket(ws):
                        """Sample frames from the first and final two sessions.

                        Args:
                            ws: Session websocket.
                        """
                        if index in {0, 1, args.contexts - 2, args.contexts - 1}:
                            for direction in ("framesent", "framereceived"):
                                ws.on(
                                    direction,
                                    lambda payload, direction=direction: (
                                        result["frames"].append({
                                            "context": index,
                                            "direction": direction,
                                            "payload": str(payload),
                                        })
                                        if len(result["frames"]) < 2000
                                        else None
                                    ),
                                )

                    page.on("websocket", socket)
                    await page.goto(f"http://localhost:{args.port}", timeout=40000)
                    await page.locator("#add-root").click(timeout=40000)
                    await page.wait_for_function(
                        "document.getElementById('count-root').textContent === '1'",
                        timeout=15000,
                    )
                    token = await page.evaluate("sessionStorage.getItem('token')")
                    row["token_sha256"] = (
                        hashlib.sha256(token.encode()).hexdigest() if token else None
                    )
                    row["counts"] = await page.evaluate(
                        "() => Object.fromEntries(['root','child','a','b'].map(k => [k, Number(document.getElementById('count-'+k).textContent)]))"
                    )
                    row["passed"] = bool(token) and row["counts"] == {
                        "root": 1,
                        "child": 0,
                        "a": 0,
                        "b": 0,
                    }
                    if index >= 0 and token:
                        tokens.add(token)
                    if index == 0:
                        await page.screenshot(
                            path=str(out / f"{engine}-churn-first.png")
                        )
                except Exception as error:
                    row["passed"] = False
                    row["error"] = f"{type(error).__name__}: {error}"
                finally:
                    await context.close()
                row["elapsed_seconds"] = time.time() - start
                if index >= 0:
                    result["contexts"].append(row)
                    if len(result["contexts"]) % 50 == 0:
                        print(
                            f"{engine} churn: {len(result['contexts'])}/{args.contexts} contexts complete",
                            flush=True,
                        )
                return row

        try:
            result["warmup"] = await context_case(-1)
            await asyncio.sleep(args.expiration + 2)
            result["before"] = await measure(metrics)
            sampler = asyncio.create_task(sample())
            result["load_started"] = time.time()
            await asyncio.gather(
                *(context_case(index) for index in range(args.contexts))
            )
            result["load_finished"] = time.time()
            result["after_load"] = await measure(metrics)
            await asyncio.sleep(args.expiration + 5)
            result["after_expiry"] = await measure(metrics)
            record("warmup-event", True, result["warmup"]["passed"])
            record(
                "all-context-events",
                args.contexts,
                sum(row["passed"] for row in result["contexts"]),
            )
            record("unique-session-tokens", args.contexts, len(tokens))
            record("states-after-expiry", 0, result["after_expiry"].get("states"))
            record("locks-after-expiry", 0, result["after_expiry"].get("locks"))
            if args.manager == "disk":
                record(
                    "disk-files-after-expiry",
                    [],
                    [
                        path.name
                        for path in (
                            Path(args.sb)
                            / "apps/statemgr_expiry"
                            / out.name
                            / ".states"
                        ).glob("*.pkl")
                    ],
                )
        except Exception as error:
            result["driver_error"] = f"{type(error).__name__}: {error}"
        finally:
            if sampler is not None:
                sampler.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sampler
            await browser.close()
    result["peak"] = {
        key: max((sample.get(key) or 0 for sample in result["samples"]), default=0)
        for key in ("rss_kib", "states", "locks")
    }
    result["anomalies"] = result["messages"]
    result["passed"] = not result.get("driver_error") and all(
        row["passed"] for row in result["checks"]
    )
    for key in ("messages", "frames"):
        (out / f"{engine}-{key}.json.gz").write_bytes(
            gzip.compress(json.dumps(result.pop(key), indent=2).encode(), mtime=0)
        )
    (out / f"{engine}-results.json").write_text(json.dumps(result, indent=2))
    return result


def run_churn(args, out, engine, metrics):
    """Run the async browser churn driver from the synchronous server harness.

    Args:
        args: Run arguments.
        out: Output directory.
        engine: Playwright engine.
        metrics: Backend observer output.

    Returns:
        Complete churn evidence and aggregate checks.
    """
    return asyncio.run(exercise(args, out, engine, metrics))
