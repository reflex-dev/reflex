"""Playwright driver for the memo cluster test app (reflex 0.9.9a1).

Usage:
    BASE_URL=http://localhost:3140 OUT=out_dev MODE=dev \
        $SB/envs/driver/bin/python drive_memo.py

Checks re-render scoping via globalThis.__renders counters (see probe.py in
the app), DOM correctness, RestProp CSS classification, runtime React
displayNames (fiber walk), and console/network cleanliness.

Writes: <OUT>/results.json, <OUT>/console.log, <OUT>/*.png
"""

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3140")
OUT = Path(os.environ.get("OUT", "out_dev"))
MODE = os.environ.get("MODE", "dev")
OUT.mkdir(parents=True, exist_ok=True)

results = []
console_lines = []
failed_requests = []


def check(name, ok, details=""):
    results.append({"name": name, "ok": bool(ok), "details": str(details)})
    print(("PASS " if ok else "FAIL ") + name + (" | " + str(details) if details else ""))


def get_renders(page):
    return page.evaluate("() => Object.assign({}, globalThis.__renders || {})")


def wait_counts_stable(page, ms=700, timeout=8000):
    """Wait until __renders stops changing for `ms` millis."""
    deadline = time.time() + timeout / 1000
    prev = get_renders(page)
    stable_since = time.time()
    while time.time() < deadline:
        time.sleep(0.15)
        cur = get_renders(page)
        if cur != prev:
            prev = cur
            stable_since = time.time()
        elif (time.time() - stable_since) * 1000 >= ms:
            return prev
    return prev


def delta(before, after):
    keys = set(before) | set(after)
    return {k: after.get(k, 0) - before.get(k, 0) for k in sorted(keys)}


FIBER_WALK_JS = """
() => {
  const el = document.getElementById('page-root') || document.getElementById('about-root');
  if (!el) return {error: 'no root el'};
  const key = Object.keys(el).find((k) => k.startsWith('__reactFiber$'));
  if (!key) return {error: 'no fiber key'};
  let fiber = el[key];
  // walk to the top of the fiber tree
  let top = fiber;
  while (top.return) top = top.return;
  const names = [];
  const contexts = [];
  const seen = new Set();
  const nameOf = (t) => {
    if (t == null) return null;
    if (typeof t === 'function') return t.displayName || t.name || null;
    if (typeof t === 'object') {
      if (t.displayName) return t.displayName;
      if (t.type) return nameOf(t.type);          // memo wraps
      if (t.render) return t.displayName || t.render.displayName || t.render.name || null; // forwardRef
      if (t._context) return (t._context.displayName || null) && ('Ctx:' + t._context.displayName);
      if (t.Provider && t.displayName === undefined && t._currentValue !== undefined) {
        return 'Ctx:' + (t.displayName || 'anon');
      }
    }
    return null;
  };
  const stack = [top];
  while (stack.length) {
    const f = stack.pop();
    if (!f || seen.has(f)) continue;
    seen.add(f);
    const t = f.type;
    // SimpleMemoComponent fibers keep the memo object (with displayName) on
    // elementType while type is the inner (possibly anonymous) function.
    const n = nameOf(f.elementType) || nameOf(t);
    if (n) names.push(n);
    // context providers: React 19 uses the context object itself as type
    if (t && typeof t === 'object') {
      const ctx = t._context || (t.$$typeof && t._currentValue !== undefined ? t : null);
      if (ctx && ctx.displayName) contexts.push(ctx.displayName);
    }
    if (f.child) stack.push(f.child);
    if (f.sibling) stack.push(f.sibling);
  }
  return {names, contexts};
}
"""


def snap(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = browser.new_context(viewport={"width": 1280, "height": 1400})
        page = ctx.new_page()

        page.on(
            "console",
            lambda m: console_lines.append(f"[{m.type}] {m.text}"),
        )
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

        page.goto(BASE_URL + "/", wait_until="load")
        page.wait_for_function(
            "() => { const t = document.getElementById('token'); return t && t.value && t.value.length > 8; }",
            timeout=30000,
        )
        base = wait_counts_stable(page)
        snap(page, "01_initial")

        # ---- initial DOM ----
        def text(sel):
            return page.locator(sel).inner_text()

        check("initial: memo_one text", text("#one-text") == "a0", text("#one-text"))
        check("initial: memo_two text", text("#two-text") == "b0", text("#two-text"))
        check("initial: last-event empty", text("#last-event") == "", repr(text("#last-event")))
        labels = page.locator("#rows .row-label").all_inner_texts()
        check("initial: foreach rows", labels == ["red", "green", "blue"], labels)
        check("initial: cs-count", text("#cs-count") == "0", text("#cs-count"))
        check("initial: ccs-count", text("#ccs-count") == "0", text("#ccs-count"))
        check("initial: island title", text("#island-title") == "a0", text("#island-title"))
        check("initial: unwrapped value", text("#unwrapped-value") == "a0", text("#unwrapped-value"))
        badges = page.locator("#badges span").all_inner_texts()
        check(
            "initial: cross-module same-name badges",
            badges == ["A:a0", "B:b0"],
            badges,
        )
        moment_txt = text("#moment")
        check("initial: NoSSR moment rendered", moment_txt == "2026", moment_txt)

        # ---- #6605 RestProp CSS classification ----
        note = page.locator("#styled-note")
        cls = note.get_attribute("class") or ""
        title = note.get_attribute("title")
        styles = page.evaluate(
            """() => { const e = document.getElementById('styled-note');
                 const cs = getComputedStyle(e);
                 return {fw: cs.fontWeight, pad: cs.padding, fs: cs.fontStyle}; }"""
        )
        check("restprop: class forwarded", "note-extra" in cls, cls)
        check("restprop: title attr forwarded", title == "notetitle", title)
        check("restprop: font_weight -> CSS 700", styles["fw"] == "700", styles)
        check("restprop: explicit style merged (padding)", styles["pad"] == "10px", styles)
        check("restprop: explicit style merged (font-style)", styles["fs"] == "italic", styles)
        check(
            "restprop: note text rendered",
            page.locator("#styled-note .note-text").inner_text() == "styled!",
        )

        # ---- render scoping: bump a ----
        page.click("#bump-a")
        page.wait_for_function("() => document.getElementById('one-text').innerText === 'a1'")
        r1 = wait_counts_stable(page)
        d1 = delta(base, r1)
        check("bump_a: page does NOT re-render", d1.get("page", 0) == 0, d1)
        check("bump_a: memo_one body re-renders", d1.get("body_one", 0) >= 1, d1)
        check("bump_a: wrapper_one re-renders", d1.get("wrapper_one", 0) >= 1, d1)
        check(
            "bump_a: wrapper_two re-renders (same state ctx)",
            d1.get("wrapper_two", 0) >= 1,
            d1,
        )
        check(
            "bump_a: memo_two body does NOT re-render (memo stops propagation)",
            d1.get("body_two", 0) == 0,
            d1,
        )
        check("bump_a: status body stable", d1.get("body_status", 0) == 0, d1)
        check("bump_a: rows stable", d1.get("body_row", 0) == 0, d1)
        check("bump_a: cs body stable", d1.get("body_cs", 0) == 0, d1)
        check("bump_a: island body re-renders (title prop)", d1.get("body_island", 0) >= 1, d1)
        check("bump_a: unwrapped label re-renders", d1.get("body_unwrapped", 0) >= 1, d1)
        check("bump_a: ccs count unchanged", text("#ccs-count") == "0")
        b2 = page.locator("#badges span").all_inner_texts()
        check("bump_a: badge A updated, badge B not", b2 == ["A:a1", "B:b0"], b2)

        # ---- bump b ----
        page.click("#bump-b")
        page.wait_for_function("() => document.getElementById('two-text').innerText === 'b1'")
        r2 = wait_counts_stable(page)
        d2 = delta(r1, r2)
        check("bump_b: page stable", d2.get("page", 0) == 0, d2)
        check("bump_b: memo_two body re-renders", d2.get("body_two", 0) >= 1, d2)
        check("bump_b: memo_one body stable", d2.get("body_one", 0) == 0, d2)
        snap(page, "02_after_bumps")

        # ---- event handler prop from inside memo ----
        page.click("#one-btn")
        page.wait_for_function(
            "() => document.getElementById('last-event').innerText === 'pinged-from-one'"
        )
        r3 = wait_counts_stable(page)
        d3 = delta(r2, r3)
        check("ping: status body re-renders", d3.get("body_status", 0) >= 1, d3)
        check("ping: memo_one body stable (props unchanged)", d3.get("body_one", 0) == 0, d3)
        check("ping: page stable", d3.get("page", 0) == 0, d3)

        # ---- foreach reverse / append ----
        page.click("#reverse")
        page.wait_for_function(
            "() => document.querySelector('#rows .row-label').innerText === 'blue'"
        )
        r4 = wait_counts_stable(page)
        d4 = delta(r3, r4)
        labels = page.locator("#rows .row-label").all_inner_texts()
        check("reverse: order flipped", labels == ["blue", "green", "red"], labels)
        check("reverse: page stable", d4.get("page", 0) == 0, d4)
        check("reverse: rows re-rendered", d4.get("body_row", 0) >= 2, d4)

        page.click("#append")
        page.wait_for_function(
            "() => document.querySelectorAll('#rows .row-label').length === 4"
        )
        r5 = wait_counts_stable(page)
        d5 = delta(r4, r5)
        labels = page.locator("#rows .row-label").all_inner_texts()
        check("append: new row present", labels == ["blue", "green", "red", "item3"], labels)
        check("append: page stable", d5.get("page", 0) == 0, d5)
        # existing rows keep identical props -> only the new row should render
        # (dev StrictMode double-invokes new mounts, so allow 2)
        check(
            "append: only new row rendered",
            1 <= d5.get("body_row", 0) <= 2,
            d5,
        )

        # ---- client_state var into memo ----
        page.click("#cs-btn")
        page.wait_for_function("() => document.getElementById('cs-count').innerText === '1'")
        r6 = wait_counts_stable(page)
        d6 = delta(r5, r6)
        check("client_state: memo body re-renders", d6.get("body_cs", 0) >= 1, d6)
        check("client_state: page stable", d6.get("page", 0) == 0, d6)
        check("client_state: unrelated memo bodies stable",
              d6.get("body_one", 0) == 0 and d6.get("body_two", 0) == 0, d6)

        # ---- ComponentState inside memo body ----
        page.click("#ccs-btn")
        page.wait_for_function("() => document.getElementById('ccs-count').innerText === '1'")
        r7 = wait_counts_stable(page)
        d7 = delta(r6, r7)
        check("component_state: count updated", text("#ccs-count") == "1")
        check("component_state: page stable", d7.get("page", 0) == 0, d7)
        results.append(
            {
                "name": "component_state: island body delta (informational)",
                "ok": True,
                "details": str(d7),
            }
        )
        snap(page, "03_after_interactions")

        # ---- runtime displayName via fiber walk ----
        fib = page.evaluate(FIBER_WALK_JS)
        names = set(fib.get("names", []))
        (OUT / "fiber_names.json").write_text(json.dumps(fib, indent=2))
        expected_names = [
            "Component(index)",
            "MemoOne",
            "MemoTwo",
            "MemoStatus",
            "MemoRow",
            "MemoCs",
            "CounterIsland",
            "StyledNote",
            "UnwrappedLabel",
            "TokenDisplay",
            "Badge",
            "Foreach",
            "Button",
            "ClientSide(Moment)",
        ]
        for n in expected_names:
            check(f"fiber displayName: {n}", n in names, "")
        wrapper_names = [n for n in names if n.startswith("MemoComponent_")]
        check(
            "fiber displayName: auto-memo wrappers named",
            len(wrapper_names) >= 5,
            wrapper_names,
        )
        ctx_names = page.evaluate(
            """() => {
                 const el = document.getElementById('page-root');
                 const key = Object.keys(el).find((k) => k.startsWith('__reactFiber$'));
                 let f = el[key]; const out = [];
                 while (f) {
                   const t = f.type;
                   if (t && typeof t === 'object') {
                     const ctx = t._context || (t._currentValue !== undefined ? t : null);
                     if (ctx) {
                       if (ctx.displayName) {
                         out.push(ctx.displayName);
                       } else {
                         // identify anonymous contexts by their provided value
                         let hint = '';
                         try {
                           const v = f.memoizedProps && f.memoizedProps.value;
                           if (v && typeof v === 'object') {
                             hint = Object.keys(v).slice(0, 5).join(',');
                           } else {
                             hint = String(v).slice(0, 60);
                           }
                         } catch (e) { hint = 'err'; }
                         out.push('(anon ctx: ' + hint + ')');
                       }
                     }
                   }
                   f = f.return;
                 }
                 return out;
               }"""
        )
        (OUT / "context_names.json").write_text(json.dumps(ctx_names, indent=2))
        check(
            "context displayNames present",
            any("StateContext(" in c for c in ctx_names)
            and "EventLoopContext" in ctx_names
            and "ColorModeContext" in ctx_names,
            ctx_names,
        )
        anon_ctx = [c for c in ctx_names if c.startswith("(anon ctx")]
        results.append(
            {
                "name": "anonymous contexts above page (informational)",
                "ok": True,
                "details": str(anon_ctx),
            }
        )

        # ---- /about page ----
        page.click("body")  # noop, keep focus
        page.goto(BASE_URL + "/about", wait_until="load")
        page.wait_for_selector("#about-marker")
        time.sleep(1.0)
        fib2 = page.evaluate(FIBER_WALK_JS)
        names2 = set(fib2.get("names", []))
        check("about: page displayName", "Component(about)" in names2, sorted(names2)[:20])
        two_txt = page.locator("#two-text").inner_text()
        check("about: memo_two shows current state b", two_txt == "b1", two_txt)
        r_about = get_renders(page)
        check(
            "about: wrapper_two_about probe ran",
            r_about.get("wrapper_two_about", 0) >= 1,
            r_about,
        )
        snap(page, "04_about")

        # ---- console / network hygiene ----
        benign = (
            "HydrateFallback",
            "[vite] connecting",
            "[vite] connected",
            "React DevTools",
            "Download the React DevTools",
        )
        noisy = [
            l
            for l in console_lines
            if l.startswith(("[error]", "[warning]", "[pageerror]"))
            and not any(b in l for b in benign)
        ]
        check("console: no unexpected errors/warnings", not noisy, noisy[:10])
        hydration = [
            l
            for l in console_lines
            if "hydrat" in l.lower() and "hydratefallback" not in l.lower()
        ]
        check("console: no hydration mismatches", not hydration, hydration[:5])
        bad_net = [
            r
            for r in failed_requests
            if "favicon" not in r and "net::ERR_ABORTED" not in r
        ]
        check("network: no failed requests", not bad_net, bad_net[:10])

        (OUT / "console.log").write_text("\n".join(console_lines))
        (OUT / "failed_requests.log").write_text("\n".join(failed_requests))
        (OUT / "results.json").write_text(json.dumps({"mode": MODE, "results": results}, indent=2))

        browser.close()

    fails = [r for r in results if not r["ok"]]
    print(f"\n{MODE}: {len(results) - len(fails)}/{len(results)} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
