"""Playwright driver for the devtools_perf cluster (reflex 0.9.9a1).

Verifies at runtime, by walking the React fiber tree:
  - #6945 displayNames: memo components (Python names), pages labelled with
    route (incl. dynamic blog/[slug]), named contexts (StateContext(...) for
    nested substates, ColorModeContext, ...), ClientSide(Plot) for the
    NoSSRComponent plotly wrapper.
  - #6905 owner stacks: React.captureOwnerStack() during render returns no
    frames in default dev mode, frames with REFLEX_REACT_OWNER_STACKS=1;
    mechanism (recentlyCreatedOwnerStacks pinned at 1e9) checked directly.
  - plotly chart renders and reacts to state updates.
  - rough perf numbers for a navigation to a ~1600-element page via CDP
    Performance metrics (recorded, not asserted).

Env vars: BASE_URL (default http://localhost:3500), OUT (output dir),
MODE = dev-default | dev-ownerstacks | prod.
"""

import json
import os
import pathlib
import time

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3500").rstrip("/")
MODE = os.environ.get("MODE", "dev-default")
OUT = pathlib.Path(os.environ.get("OUT", "out_" + MODE))
OUT.mkdir(parents=True, exist_ok=True)

results = []
console_lines = []
failed_requests = []

BENIGN_CONSOLE = (
    "HydrateFallback",
    "[vite] connecting",
    "[vite] connected",
    "React DevTools",
    "Disconnect websocket on page navigation",
    "Download the React DevTools",
)


def check(name, ok, details=""):
    """Record one check."""
    status = "pass" if ok else "fail"
    results.append({"name": name, "status": status, "details": str(details)[:800]})
    print(f"[{status.upper()}] {name} {'' if ok else '-> ' + str(details)[:200]}")


def record(name, details):
    """Record an informational (non-asserted) entry."""
    results.append({"name": name, "status": "info", "details": str(details)[:2000]})
    print(f"[INFO] {name}: {details}")


FIBER_WALK_JS = """
() => {
  const el = document.getElementById('page-root');
  if (!el) return {error: 'no page-root'};
  const key = Object.keys(el).find((k) => k.startsWith('__reactFiber$'));
  if (!key) return {error: 'no fiber key'};
  let top = el[key];
  while (top.return) top = top.return;
  const names = [];
  const contexts = [];
  const seen = new Set();
  const nameOf = (t) => {
    if (t == null) return null;
    if (typeof t === 'function') return t.displayName || t.name || null;
    if (typeof t === 'object') {
      if (t.displayName) return t.displayName;
      if (t.type) return nameOf(t.type);
      if (t.render) return t.displayName || t.render.displayName || t.render.name || null;
    }
    return null;
  };
  const stack = [top];
  while (stack.length) {
    const f = stack.pop();
    if (!f || seen.has(f)) continue;
    seen.add(f);
    // SimpleMemoComponent fibers keep the memo object (with displayName) on
    // elementType while type is the inner function.
    const n = nameOf(f.elementType) || nameOf(f.type);
    if (n) names.push(n);
    const t = f.type;
    if (t && typeof t === 'object') {
      const ctx = t._context || (t.$$typeof && t._currentValue !== undefined ? t : null);
      if (ctx) contexts.push(ctx.displayName || '<unnamed>');
    }
    if (f.child) stack.push(f.child);
    if (f.sibling) stack.push(f.sibling);
  }
  return {names: [...new Set(names)], contexts: [...new Set(contexts)]};
}
"""


def fiber_walk(page):
    """Walk the fiber tree from #page-root's root."""
    return page.evaluate(FIBER_WALK_JS)


def snap(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


def wait_ready(page, timeout=30000):
    """Wait for hydration: the OwnerProbe must have rendered."""
    page.wait_for_function(
        "() => Array.isArray(window.__ownerStackCaptures) && window.__ownerStackCaptures.length > 0",
        timeout=timeout,
    )


def wait_backend(page, timeout=20000):
    """Wait until the websocket delivered initial state (clicks card shows a number)."""
    page.wait_for_function(
        "() => { const e = document.querySelector('#clicks-card .stat-value');"
        " return e && /^\\d+$/.test(e.textContent.trim()); }",
        timeout=timeout,
    )


def get_metrics(cdp):
    m = cdp.send("Performance.getMetrics")["metrics"]
    return {x["name"]: x["value"] for x in m}


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        page.on("console", lambda m: console_lines.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console_lines.append(f"[pageerror] {e}"))
        page.on(
            "response",
            lambda r: failed_requests.append(f"{r.status} {r.url}")
            if r.status >= 400
            else None,
        )
        page.on(
            "requestfailed",
            lambda r: failed_requests.append(f"FAILED {r.failure} {r.url}"),
        )
        cdp = ctx.new_cdp_session(page)
        cdp.send("Performance.enable")

        page.goto(BASE_URL + "/", wait_until="load", timeout=60000)
        wait_ready(page)
        wait_backend(page)
        snap(page, "01_index")

        # ---- index page naming ----
        walk = fiber_walk(page)
        (OUT / "fiber_index.json").write_text(json.dumps(walk, indent=2))
        names = walk.get("names", [])
        contexts = walk.get("contexts", [])
        check("index: fiber walk ok", "error" not in walk, walk.get("error"))
        check("index: page displayName Component(index)", "Component(index)" in names, names)
        check("index: memo CounterPanel named", "CounterPanel" in names, names)
        check("index: memo NavBar named", "NavBar" in names, names)
        check(
            "index: auto-memo wrapper MemoComponent_CounterPanel_* named",
            any(n.startswith("MemoComponent_CounterPanel_") for n in names),
            names,
        )
        check(
            "index: StyledUpload memo named",
            "StyledUpload" in names,
            names,
        )
        for expect in [
            "StateContext(reflex___state____state)",
            "StateContext(reflex___state____state.devtools_app___devtools_app____app_state)",
            "StateContext(reflex___state____state.devtools_app___devtools_app____app_state.devtools_app___devtools_app____chart_state)",
            "StateContext(reflex___state____state.devtools_app___devtools_app____app_state.devtools_app___devtools_app____blog_state)",
            "ColorModeContext",
            "EventLoopContext",
            "DispatchContext",
        ]:
            check(f"index: context named {expect}", expect in contexts, contexts)
        unnamed = [c for c in contexts if c == "<unnamed>"]
        record("index: unnamed contexts in tree (3rd-party ok)", f"{len(unnamed)} of {len(contexts)}")

        # interactivity sanity
        page.click("#bump-btn")
        page.wait_for_function(
            "() => document.querySelector('#clicks-card .stat-value').textContent.trim() === '1'",
            timeout=10000,
        )
        check("index: bump updates StatCard", True)
        badge = page.locator("#pulse-badge").inner_text()
        check("index: PulseBadge shows last action", "bump" in badge, badge)

        # ---- owner stack: during-render capture ----
        captures = page.evaluate("() => window.__ownerStackCaptures")
        (OUT / "owner_captures_index.json").write_text(json.dumps(captures, indent=2))
        stacks = [c["stack"] for c in captures]
        if MODE == "dev-default":
            check(
                "ownerstack: captureOwnerStack() empty in default dev",
                all(not s or not s.strip() for s in stacks if isinstance(s, (str, type(None)))),
                stacks[-3:],
            )
        elif MODE == "dev-ownerstacks":
            check(
                "ownerstack: captureOwnerStack() has frames with REFLEX_REACT_OWNER_STACKS=1",
                any(isinstance(s, str) and s.strip() for s in stacks),
                stacks[-3:],
            )
        else:
            record("ownerstack: prod captures", stacks[-3:])

        internals = page.evaluate(
            """() => {
              const R = window.__probeReact;
              if (!R) return {error: 'no probe react'};
              const I = R.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;
              if (!I) return {error: 'no client internals'};
              const v = I.recentlyCreatedOwnerStacks;
              let writable = null;
              if (typeof v === 'number') {
                try { I.recentlyCreatedOwnerStacks = v + 1;
                      writable = I.recentlyCreatedOwnerStacks === v + 1;
                      I.recentlyCreatedOwnerStacks = v; } catch (e) { writable = 'threw'; }
              }
              return {value: v, writable};
            }"""
        )
        record("ownerstack: internals probe", internals)
        if MODE == "dev-default":
            check(
                "ownerstack: recentlyCreatedOwnerStacks pinned at 1e9 (setter no-op)",
                internals.get("value") == 1e9 and internals.get("writable") is False,
                internals,
            )
        elif MODE == "dev-ownerstacks":
            check(
                "ownerstack: recentlyCreatedOwnerStacks NOT pinned",
                internals.get("value") != 1e9,
                internals,
            )

        # context module direct import (dev only; vite serves /utils/context.js)
        if MODE.startswith("dev"):
            ctxmod = page.evaluate(
                """async () => {
                  try {
                    const m = await import('/utils/context.js');
                    const out = {};
                    for (const k of ['ColorModeContext','UploadFilesContext','DispatchContext','EventLoopContext']) {
                      out[k] = m[k] && m[k].displayName;
                    }
                    out.states = Object.fromEntries(
                      Object.entries(m.StateContexts).map(([k, v]) => [k, v.displayName]));
                    return out;
                  } catch (e) { return {error: String(e)}; }
                }"""
            )
            (OUT / "context_module.json").write_text(json.dumps(ctxmod, indent=2))
            check(
                "contexts: module-level displayNames all set (incl. UploadFilesContext)",
                "error" not in ctxmod
                and ctxmod.get("UploadFilesContext") == "UploadFilesContext"
                and all(v for v in ctxmod.get("states", {}).values()),
                ctxmod,
            )
        theme_ok = "ThemeContext" in contexts
        record("index: ThemeContext provider in tree", theme_ok)

        # ---- perf: navigation to heavy page (recorded, not asserted) ----
        perf_runs = []
        for i in range(3):
            m0 = get_metrics(cdp)
            t0 = time.time()
            page.click("#nav-heavy")
            page.wait_for_selector("#heavy-title", timeout=30000)
            page.wait_for_function(
                "() => document.querySelectorAll('.cell').length >= 1440", timeout=30000
            )
            wall = (time.time() - t0) * 1000
            m1 = get_metrics(cdp)
            run = {
                "nav": i,
                "wall_ms": round(wall, 1),
                "TaskDuration_ms": round((m1["TaskDuration"] - m0["TaskDuration"]) * 1000, 1),
                "ScriptDuration_ms": round(
                    (m1["ScriptDuration"] - m0["ScriptDuration"]) * 1000, 1
                ),
                "LayoutDuration_ms": round(
                    (m1["LayoutDuration"] - m0["LayoutDuration"]) * 1000, 1
                ),
                "RecalcStyleDuration_ms": round(
                    (m1["RecalcStyleDuration"] - m0["RecalcStyleDuration"]) * 1000, 1
                ),
            }
            perf_runs.append(run)
            page.click("#nav-home")
            page.wait_for_selector("#bump-btn", timeout=30000)
            page.wait_for_timeout(400)
        (OUT / "perf_heavy_nav.json").write_text(json.dumps(perf_runs, indent=2))
        record("perf: heavy-page navigation metrics", perf_runs)

        # heavy page naming while we're here
        page.click("#nav-heavy")
        page.wait_for_selector("#heavy-title", timeout=30000)
        walk = fiber_walk(page)
        check(
            "heavy: page displayName Component(heavy)",
            "Component(heavy)" in walk.get("names", []),
            walk.get("names", [])[:30],
        )
        snap(page, "02_heavy")

        # ---- charts page: plotly ----
        page.click("#nav-charts")
        page.wait_for_selector("#chart-total", timeout=30000)
        # NoSSR: the actual Plot loads via dynamic import; wait for plotly svg.
        # NOTE: id= passed to rx.plotly does NOT reach the DOM (react-plotly.js
        # only forwards divId), so select by plotly's own class.
        page.wait_for_selector("#page-root .js-plotly-plot .main-svg", timeout=45000)
        page.wait_for_timeout(500)
        snap(page, "03_charts")
        record(
            "charts: rx.plotly(id=...) does not land on DOM (react-plotly.js wants divId)",
            page.locator("#the-plot").count() == 0,
        )
        nbars = page.locator(".js-plotly-plot .trace.bars .point").count()
        check("charts: plotly bar chart rendered with 6 bars", nbars == 6, nbars)
        walk = fiber_walk(page)
        (OUT / "fiber_charts.json").write_text(json.dumps(walk, indent=2))
        names = walk.get("names", [])
        check("charts: page displayName Component(charts)", "Component(charts)" in names, names)
        check("charts: ClientSide(Plot) in fiber tree", "ClientSide(Plot)" in names, names)
        check(
            "charts: memoized Plotly wrapper named from Python class",
            "Plotly" in names,
            names,
        )
        total0 = page.locator("#chart-total").inner_text()
        page.click("#shuffle-btn")
        try:
            page.wait_for_function(
                f"() => document.querySelector('#chart-total').textContent !== {json.dumps(total0)}",
                timeout=10000,
            )
            changed = True
        except Exception:
            changed = False
        page.wait_for_timeout(700)
        check("charts: shuffle updates figure + total", changed, total0)
        snap(page, "04_charts_shuffled")
        # plotly interaction: hover produces a hoverlabel
        try:
            box = page.locator(".js-plotly-plot .trace.bars .point path >> nth=2").bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_selector(".js-plotly-plot .hoverlayer .hovertext", timeout=5000)
            check("charts: plotly hover tooltip works", True)
        except Exception as e:
            check("charts: plotly hover tooltip works", False, e)

        # ---- blog dynamic route ----
        page.click("#nav-blog")
        page.wait_for_selector("#blog-title", timeout=30000)
        page.wait_for_function(
            "() => document.querySelector('#blog-title').textContent.includes('hello-world')",
            timeout=15000,
        )
        page.wait_for_function(
            "() => /[1-9]/.test(document.querySelector('#blog-views').textContent)",
            timeout=15000,
        )
        walk = fiber_walk(page)
        (OUT / "fiber_blog.json").write_text(json.dumps(walk, indent=2))
        names = walk.get("names", [])
        check(
            "blog: page displayName Component(blog/[slug])",
            "Component(blog/[slug])" in names,
            names,
        )
        views = page.locator("#blog-views").inner_text()
        check("blog: on_load recorded view of slug", "1" in views, views)
        snap(page, "05_blog")

        # second slug via client-side nav (direct load of dynamic routes 404s in prod)
        try:
            page.click("#next-post-link")
            page.wait_for_function(
                "() => document.querySelector('#blog-title') && document.querySelector('#blog-title').textContent.includes('second-post')",
                timeout=15000,
            )
            check("blog: second slug renders via client-side nav", True)
            page.wait_for_function(
                "() => /[1-9]/.test(document.querySelector('#blog-views').textContent)",
                timeout=15000,
            )
            check("blog: on_load re-fired for new slug", True)
        except Exception as e:
            check("blog: second slug renders via client-side nav", False, e)
        snap(page, "06_blog_second")

        # ---- final owner-stack capture count over whole session ----
        captures = page.evaluate("() => window.__ownerStackCaptures.length")
        record("ownerstack: total probe captures this session", captures)

        # ---- hygiene ----
        (OUT / "console.log").write_text("\n".join(console_lines))
        (OUT / "failed_requests.log").write_text("\n".join(failed_requests))
        surprising = [
            l
            for l in console_lines
            if not any(b in l for b in BENIGN_CONSOLE)
            and not l.startswith("[log]")
            and not l.startswith("[debug]")
            and not l.startswith("[info]")
        ]
        check("hygiene: no unexpected console errors/warnings", not surprising, surprising[:8])
        check("hygiene: no failed/4xx/5xx requests", not failed_requests, failed_requests[:8])

        browser.close()

    (OUT / "results.json").write_text(json.dumps({"mode": MODE, "results": results}, indent=2))
    fails = [r for r in results if r["status"] == "fail"]
    print(f"\n== {MODE}: {len([r for r in results if r['status'] == 'pass'])} pass, {len(fails)} fail ==")
    for f in fails:
        print("FAIL:", f["name"], f["details"][:200])


if __name__ == "__main__":
    main()
