"""Drive the enterprise mantine / highcharts / tickets demos in Chromium.

Unlike the shared drive_app.py this keeps going after a failed step (so one bad
selector does not hide the rest of the flow) and records a DOM probe after every
step, which is what makes a chart / toast / table regression visible in the report.

Usage:
    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_mht.py <base_url> <actions.json> <report.json> <shotdir>

Action verbs (one key per dict, plus optional "note"):
    goto, click, click_text, click_nth [sel, i], fill [sel, text], press [sel, key],
    type [sel, text], wait <ms>, wait_for <sel>, shot <name>, expect_text <s>,
    expect_missing <sel>, eval <js>, mouse_click [x, y], click_in_box [sel, fx, fy],
    hover <sel>, keyboard <key>, reload, probe (force a probe now)
"""

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE, ACTIONS_FILE, REPORT, SHOTDIR = sys.argv[1:5]
Path(SHOTDIR).mkdir(parents=True, exist_ok=True)

BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]

PROBE = """() => {
  const t = (s) => document.querySelectorAll(s).length;
  return {
    svg: t('svg'),
    buttons: t('button'),
    inputs: t('input'),
    rows: t('tbody tr'),
    highcharts: t('.highcharts-container'),
    hc_points: t('.highcharts-series > *'),
    mantine: t('[class*="mantine-"]'),
    toasts: t('[data-sonner-toast], [data-radix-toast], li[data-sonner-toast]'),
    toast_text: Array.from(document.querySelectorAll('[data-sonner-toast]')).map(
      (e) => e.innerText.replace(/\\n/g, ' | ')).join(' ;; '),
    dialogs: t('[role="dialog"]'),
    calendar_cells: t('table button, .mantine-Day-day'),
    text_len: document.body.innerText.length,
    head: document.body.innerText.slice(0, 300).replace(/\\n/g, ' | '),
  };
}"""

R = {
    "base": BASE,
    "steps": [],
    "console": [],
    "pageerrors": [],
    "failed": [],
    "http_errors": [],
    "ws": [],
}


def run(page, verb, val, timeout=12000):
    """Apply one action.

    Args:
        page: Playwright page.
        verb: Action name.
        val: Action argument(s).
        timeout: Per-action timeout in ms.

    Returns:
        Optional result value for verbs that produce one.
    """
    if verb == "goto":
        page.goto(BASE + val, wait_until="networkidle", timeout=60000)
    elif verb == "click":
        page.click(val, timeout=timeout)
    elif verb == "click_text":
        page.click(f"text={val}", timeout=timeout)
    elif verb == "click_nth":
        page.locator(val[0]).nth(val[1]).click(timeout=timeout)
    elif verb == "fill":
        page.fill(val[0], val[1], timeout=timeout)
    elif verb == "type":
        page.locator(val[0]).first.click(timeout=timeout)
        page.keyboard.type(val[1], delay=30)
    elif verb == "press":
        page.press(val[0], val[1], timeout=timeout)
    elif verb == "keyboard":
        page.keyboard.press(val)
    elif verb == "hover":
        page.hover(val, timeout=timeout)
    elif verb == "wait":
        page.wait_for_timeout(val)
    elif verb == "wait_for":
        page.wait_for_selector(val, timeout=timeout)
    elif verb == "expect_text":
        page.wait_for_selector(f"text={val}", timeout=timeout)
    elif verb == "expect_missing":
        page.wait_for_selector(val, state="detached", timeout=timeout)
    elif verb == "shot":
        page.screenshot(path=f"{SHOTDIR}/{val}.png", full_page=True)
    elif verb == "eval":
        return page.evaluate(val)
    elif verb == "mouse_click":
        page.mouse.click(val[0], val[1])
    elif verb == "click_in_box":
        box = page.locator(val[0]).first.bounding_box()
        if not box:
            raise RuntimeError(f"no bounding box for {val[0]}")
        page.mouse.click(box["x"] + box["width"] * val[1], box["y"] + box["height"] * val[2])
    elif verb == "reload":
        page.reload(wait_until="networkidle")
    elif verb == "probe":
        pass
    else:
        raise ValueError(f"unknown verb {verb}")
    return None


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 1400, "height": 1000})
    page = ctx.new_page()
    page.on("console", lambda m: R["console"].append({"type": m.type, "text": m.text[:400]}))
    page.on("pageerror", lambda e: R["pageerrors"].append(str(e)[:400]))
    page.on(
        "requestfailed",
        lambda r: R["failed"].append({"url": r.url[:200], "err": str(r.failure)[:120]}),
    )
    page.on(
        "response",
        lambda r: R["http_errors"].append({"url": r.url[:200], "status": r.status})
        if r.status >= 400
        else None,
    )
    page.on(
        "websocket",
        lambda ws: ws.on(
            "framereceived", lambda pl: R["ws"].append(str(pl)[:200])
        ),
    )

    for i, action in enumerate(json.loads(Path(ACTIONS_FILE).read_text())):
        note = action.pop("note", None)
        ((verb, val),) = action.items()
        t0 = time.time()
        rec = {"i": i, "verb": verb, "val": val, "note": note}
        try:
            res = run(page, verb, val)
            rec["ok"] = True
            if res is not None:
                rec["result"] = res
        except Exception as exc:  # noqa: BLE001
            rec["ok"] = False
            rec["err"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        rec["ms"] = int((time.time() - t0) * 1000)
        try:
            rec["probe"] = page.evaluate(PROBE)
            rec["url"] = page.url
        except Exception as exc:  # noqa: BLE001
            rec["probe_err"] = str(exc)[:200]
        R["steps"].append(rec)
        print(
            f"[{i:02d}] {verb} {str(val)[:60]!r} ok={rec['ok']} "
            f"{rec.get('err', '')[:120]} probe={json.dumps(rec.get('probe', {}))[:220]}",
            flush=True,
        )

    page.wait_for_timeout(1200)
    br.close()

R["console_errors"] = [
    c for c in R["console"] if c["type"] == "error" and not any(b.search(c["text"]) for b in BENIGN)
]
R["console_warnings"] = [c for c in R["console"] if c["type"] == "warning"]
R["failed_steps"] = [s for s in R["steps"] if not s["ok"]]
Path(REPORT).write_text(json.dumps(R, indent=1, default=str))
print("\n=== FAILED STEPS:", json.dumps([(s["i"], s["verb"], s.get("err")) for s in R["failed_steps"]])[:1500])
print("=== CONSOLE ERRORS:", json.dumps(R["console_errors"])[:2000])
print("=== PAGE ERRORS:", json.dumps(R["pageerrors"])[:1000])
print("=== REQ FAILED:", json.dumps(R["failed"])[:600])
print("=== HTTP>=400:", json.dumps(R["http_errors"])[:800])
print("saved", REPORT)
