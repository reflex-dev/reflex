"""Drive the awaitapp matrix in Chromium.

usage: drive_await.py <frontend_url> <server_log> <out.json> [case ...]

For each case: click reset, click the case button, wait for `#result` to start
with "<case>:", then record the visible state, toasts, websocket frames,
console messages and the server-log lines written during the case. After each
case a `ping` round trip is timed to prove the state lock was released.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, SERVER_LOG, OUT = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
ONLY = sys.argv[4:]

CASES = [
    # (button id suffix, result prefix, timeout s)
    ("add_twice", "add_twice", 5),
    ("c_sub", "c_sub", 5),
    ("c_parent", "c_parent", 5),
    ("c_other", "c_other", 5),
    ("other_to_main", "other_to_main", 5),
    ("c_other_get_state", "c_other_get_state", 5),
    ("c_mixin", "c_mixin", 5),
    ("c_no_args", "c_no_args", 5),
    ("c_gen_sync", "c_gen_sync", 5),
    ("c_gen_async", "c_gen_async", 6),
    ("c_ret_toast", "c_ret_toast", 5),
    ("c_ret_events", "c_ret_events", 5),
    ("c_ret_empty_list", "c_ret_empty_list", 5),
    ("c_ret_dict", "c_ret_dict", 5),
    ("c_await_frontend", "c_await_frontend", 5),
    ("c_boom_caught", "c_boom_caught", 5),
    ("c_boom_uncaught", "c_boom_uncaught", 3),
    ("c_fact", "c_fact", 5),
    ("c_recurse", "c_recurse", 15),
    ("c_actions", "c_actions", 5),
    ("c_self_sync", "c_self_sync", 5),
    ("c_self_async", "c_self_async", 5),
    ("c_self_gen", "c_self_gen", 5),
    ("c_args", "c_args", 5),
    ("c_proxied", "c_proxied", 5),
    ("c_proxied_yield", "c_proxied_yield", 5),
    ("c_gather", "c_gather", 5),
    ("c_ensure_future", "c_ensure_future", 5),
    ("c_create_task", "c_create_task", 5),
    ("c_wait_for", "c_wait_for", 8),
    ("c_setvar", "c_setvar", 5),
    ("c_fg_await_bg", "c_fg_await_bg", 5),
    ("c_sync_await", "c_sync_await", 5),
    ("c_upload_spec", "c_upload_spec", 5),
    ("c_mw_blocked", "c_mw_blocked", 5),
    ("c_mw_mutate", "c_mw_mutate", 5),
    ("c_mw_raise", "c_mw_raise", 5),
    ("c_mw_self_bypass", "c_mw_self_bypass", 5),
    ("c_mw_bg_blocked", "c_mw_bg_blocked", 6),
    ("c_bg_outside", "c_bg_outside", 8),
    ("c_bg_inside", "c_bg_inside", 6),
    ("c_bg_await_bg", "c_bg_await_bg", 6),
    ("c_bg_inside_await_bg", "c_bg_inside_await_bg", 6),
    ("c_bg_boom", "c_bg_boom", 6),
    ("c_bg_gather", "c_bg_gather", 6),
    ("c_bg_self", "c_bg_self", 6),
    ("add-direct", None, 2),
    ("ret-dict-direct", None, 2),
    ("secret-direct", None, 2),
    ("mutate-direct", None, 2),
    ("cs-a", None, 2),
]

FIELDS = [
    "result", "total", "doubled", "last_added", "progress", "depth", "query",
    "secret_runs", "sub-n", "other-items", "uploaded", "auth", "blocked-count",
    "cs-msg-a", "cs-count-a", "cs-msg-b", "cs-count-b",
]

frames: list[tuple[float, str, str]] = []
console: list[tuple[float, str, str]] = []
failed: list[tuple[float, str]] = []


def snapshot(page) -> dict:
    return page.evaluate(
        """(ids) => Object.fromEntries(ids.map(i => [i, document.getElementById(i)?.textContent ?? null]))""",
        FIELDS,
    )


TOAST_SPY = """
window.__toasts = [];
window.__hist = [];
new MutationObserver((muts) => {
  for (const m of muts) for (const n of m.addedNodes) {
    if (n.nodeType !== 1) continue;
    const els = n.matches?.('[data-sonner-toast]') ? [n] : [...(n.querySelectorAll?.('[data-sonner-toast]') ?? [])];
    for (const e of els) if (!window.__toasts.some((t) => t.el === e)) window.__toasts.push({t: Date.now(), el: e, text: ''});
  }
  for (const t of window.__toasts) if (t.el.isConnected && t.el.textContent) t.text = t.el.textContent;
  const r = document.getElementById('result');
  if (r) {
    const txt = r.textContent, h = window.__hist;
    if (!h.length || h[h.length - 1][1] !== txt) h.push([Date.now(), txt]);
  }
}).observe(document, {childList: true, subtree: true, characterData: true});
"""


def history(page, since: float) -> list[str]:
    """Every distinct value `#result` showed since `since`, in order."""
    return page.evaluate(
        "(since) => (window.__hist ?? []).filter(h => h[0] >= since).map(h => h[1])", since * 1000
    )


def toasts(page, since: float = 0.0) -> list[str]:
    """Texts of the toasts added since `since` (epoch seconds); never touches the DOM."""
    return page.evaluate(
        "(since) => (window.__toasts ?? []).filter(t => t.t >= since).map(t => t.text || t.el.textContent)",
        since * 1000,
    )


def clear_toasts(page) -> None:
    """No-op: removing sonner's nodes by hand crashes React (driver artifact seen in the first run)."""


def wait_result(page, prefix: str, timeout: float) -> bool:
    try:
        page.wait_for_function(
            "(p) => (document.getElementById('result')?.textContent ?? '').startsWith(p + ':')",
            arg=prefix,
            timeout=timeout * 1000,
        )
    except Exception:
        return False
    return True


def ping(page) -> float | None:
    """Round-trip a trivial event; None when it does not come back in 10 s."""
    t0 = time.time()
    try:
        page.click("#b-ping", timeout=5000)
    except Exception as ex:
        return f"ping click failed: {str(ex)[:80]}"
    if wait_result(page, "ping", 10):
        return round(time.time() - t0, 3)
    return None


def delta_summary(since: float) -> dict:
    recv = [f for f in frames if f[0] >= since and f[1] == "recv"]
    deltas = [f for f in recv if '"delta"' in f[2] or "delta" in f[2][:40]]
    progress = re.findall(r'"progress[^"]*":\s*(\d+)', " ".join(f[2] for f in recv))
    names = re.findall(r'"name":\s*"([^"]+)"', " ".join(f[2] for f in recv))
    sent = [f[2][:200] for f in frames if f[0] >= since and f[1] == "sent" and len(f[2]) > 3]
    return {
        "n_recv": len(recv),
        "n_delta_frames": len(deltas),
        "progress_values": progress,
        "event_names_from_backend": names,
        "sent": sent,
    }


def _reset(page) -> None:
    page.click("#b-reset")
    wait_result(page, "reset", 10)
    page.click("#b-logout")
    time.sleep(0.3)


def _capture(page, results: dict, name: str, t0: float, log_off: int, extra: dict | None = None, snap: dict | None = None) -> None:
    snap = snap or snapshot(page)
    with SERVER_LOG.open("rb") as f:
        f.seek(log_off)
        log = f.read().decode(errors="replace")
    results[name] = {
        "snapshot": snap,
        "toasts": toasts(page, t0 - 0.05),
        "result_history": history(page, t0),
        "ws": delta_summary(t0),
        "server_log": log[-6000:],
        "console": [c for c in console if c[0] >= t0 and c[1] in ("error", "warning", "pageerror")],
        "failed_requests": [f for f in failed if f[0] >= t0],
        **(extra or {}),
    }
    keep = {k: v for k, v in snap.items() if v not in ("", "0", None)}
    print(f"[special] {name}: {keep} toasts={results[name]['toasts']} hist={results[name]['result_history']} {extra or ''}", flush=True)


def special(page, results: dict) -> None:
    """Scenarios that need more than one click."""
    here = Path(__file__).parent

    def run(name, clicks, wait, pre=None, gap=0.15, extra_fn=None):
        _reset(page)
        if pre:
            pre()
        log_off = SERVER_LOG.stat().st_size
        t0 = time.time()
        for i, c in enumerate(clicks):
            if i:
                time.sleep(gap)
            page.click(c)
        time.sleep(wait)
        snap = snapshot(page)
        extra = {"ping_after_s": ping(page)}
        if extra_fn:
            extra.update(extra_fn())
        _capture(page, results, name, t0, log_off, extra, snap)

    def login():
        page.click("#b-login")
        page.wait_for_function("() => document.getElementById('auth')?.textContent === 'in'")

    # awaited handler runs once the gate lets it through
    run("mw_logged_in_await", ["#b-c_mw_blocked"], 1.0, pre=login)
    run("mw_logged_in_bg", ["#b-c_mw_bg_blocked"], 1.5, pre=login)
    run("mw_secret_direct_logged_in", ["#b-secret-direct"], 1.0, pre=login)
    # supersedes: awaited inline inside a non-superseding caller, twice
    run("sup_await_inline_x2", ["#b-sup-1", "#b-sup-2"], 2.5)
    # supersedes: the handler itself triggered twice (baseline semantics)
    run("sup_direct_x2", ["#b-search-1", "#b-search-2"], 2.5)
    # supersedes: two background tasks each awaiting (enqueue path) the superseding handler
    run("sup_bg_await_x2", ["#b-bgsup-1", "#b-bgsup-2"], 3.0)
    # double click on a handler that awaits a slow generator
    run("gen_async_x2", ["#b-c_gen_async", "#b-c_gen_async"], 3.0)
    # ComponentState instances are independent
    run("component_state", ["#b-cs-a", "#b-cs-a", "#b-cs-b"], 1.0, gap=0.3)

    # upload: handler awaiting other handlers
    f1, f2 = here / "up1.txt", here / "up2.bin"
    f1.write_text("hello")
    f2.write_bytes(b"x" * 1000)

    def choose():
        page.set_input_files("#u1 input[type=file]", [str(f1), str(f2)])
        time.sleep(0.3)

    run("upload_await", ["#b-upload"], 2.0, pre=choose)
    run("upload_secret_logged_out", ["#b-secret-upload"], 2.0, pre=choose)
    run("upload_secret_logged_in", ["#b-secret-upload"], 2.0, pre=lambda: (login(), choose()))

    # on_load awaiting handlers: client-side navigation, then a hard load
    _reset(page)
    log_off = SERVER_LOG.stat().st_size
    t0 = time.time()
    page.click("#l-onload")
    ok = wait_result(page, "on_load", 10)
    time.sleep(0.5)
    _capture(page, results, "on_load_nav", t0, log_off, {"completed": ok})
    log_off = SERVER_LOG.stat().st_size
    t0 = time.time()
    page.goto(URL.rstrip("/") + "/onload")
    page.wait_for_selector("#l-home")
    time.sleep(2.0)
    _capture(page, results, "on_load_hard", t0, log_off)
    page.click("#l-home")
    page.wait_for_selector("#b-reset")
    time.sleep(1.0)


def main() -> None:
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = browser.new_context()
        page = ctx.new_page()
        page.on("console", lambda m: console.append((time.time(), m.type, m.text)))
        page.on("pageerror", lambda e: console.append((time.time(), "pageerror", str(e))))
        page.on(
            "response",
            lambda r: failed.append((time.time(), f"{r.status} {r.url}")) if r.status >= 400 else None,
        )
        page.on("requestfailed", lambda r: failed.append((time.time(), f"FAILED {r.url}")))

        def on_ws(ws):
            ws.on("framereceived", lambda payload: frames.append((time.time(), "recv", str(payload))))
            ws.on("framesent", lambda payload: frames.append((time.time(), "sent", str(payload))))

        page.on("websocket", on_ws)
        page.add_init_script(TOAST_SPY)
        page.goto(URL)
        page.wait_for_selector("#b-reset")
        page.wait_for_function(
            "() => document.getElementById('auth')?.textContent === 'out'", timeout=30000
        )
        time.sleep(1.0)
        for button, prefix, timeout in CASES:
            if ONLY and button not in ONLY:
                continue
            page.click("#b-reset")
            if not wait_result(page, "reset", 10):
                results[button] = {"error": "reset did not complete", "snapshot": snapshot(page)}
                print(button, "RESET FAILED", flush=True)
                continue
            page.click("#b-logout")
            time.sleep(0.2)
            clear_toasts(page)
            log_off = SERVER_LOG.stat().st_size
            t0 = time.time()
            page.click(f"#b-{button}")
            completed = wait_result(page, prefix, timeout) if prefix else None
            elapsed = round(time.time() - t0, 3)
            time.sleep(1.2 if prefix else timeout)
            snap = snapshot(page)
            tsts = toasts(page, t0 - 0.05)
            summ = delta_summary(t0)
            if (prefix and not completed) or snap["result"] is None:
                page.screenshot(path=str(OUT.with_suffix("")) + f".{button}.png", full_page=True)
                body = page.evaluate("() => document.body.innerText.slice(0, 1500)")
            else:
                body = None
            ping_s = ping(page)
            with SERVER_LOG.open("rb") as f:
                f.seek(log_off)
                log = f.read().decode(errors="replace")
            results[button] = {
                "completed": completed,
                "elapsed_s": elapsed,
                "body_when_broken": body,
                "snapshot": snap,
                "toasts": tsts,
                "ws": summ,
                "ping_after_s": ping_s,
                "server_log": log[-6000:],
                "console": [c for c in console if c[0] >= t0 and c[1] in ("error", "warning", "pageerror")],
                "failed_requests": [f for f in failed if f[0] >= t0],
            }
            print(f"{button:24s} completed={completed} {elapsed}s ping={ping_s} result={snap['result']!r}", flush=True)
            if tsts:
                print(f"{'':24s} toasts={tsts}", flush=True)
            if body:
                print(f"{'':24s} BODY={body[:600]!r}", flush=True)
            if snap["result"] is None:
                page.goto(URL)
                page.wait_for_selector("#b-reset")
                time.sleep(1.5)
        if not ONLY or "special" in ONLY:
            special(page, results)
        browser.close()
    OUT.write_text(json.dumps({"results": results, "console_all": console, "failed_all": failed}, indent=1))


if __name__ == "__main__":
    main()
