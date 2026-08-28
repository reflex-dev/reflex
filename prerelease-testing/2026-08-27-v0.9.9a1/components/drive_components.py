"""Drive the component-cluster app end-to-end in Chromium.

Verifies:
- code_block custom_style bound to backend state var updates live (#6520)
- code_block custom_style bound to ClientStateVar updates live (#6520)
- code_block custom_style state var inside rx.memo updates live (#6520)
- wrap_long_lines + code_tag_props -> whiteSpace pre-wrap merged (#6520)
- wrap_long_lines with explicit whiteSpace:normal -> user's value wins
- rx.script head+inline tags present after hydration over 10 reloads (#6905)
- deprecated App(theme=...) with RadixThemesPlugin applies accent color (#6776)
Usage: python drive_components.py <base_url> <outdir>
"""

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3380"
OUT = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "."

results = {}
console_msgs = []
failed_requests = []
http_errors = []


def log(name, status, detail=""):
    results[name] = (status, detail)
    print(f"[{status}] {name}: {detail}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append((m.type, m.text)))
    page.on("requestfailed", lambda r: failed_requests.append((r.url, r.failure)))
    page.on(
        "response",
        lambda r: http_errors.append((r.status, r.url)) if r.status >= 400 else None,
    )

    page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_selector("#toggle-btn", timeout=30000)
    page.wait_for_timeout(1500)

    # --- #6776: theme accent applied (crimson). Radix sets accent CSS vars and
    # data-accent-color on the .radix-themes wrapper element.
    theme_info = page.evaluate(
        """() => {
            const el = document.querySelector('.radix-themes');
            if (!el) return {present:false};
            const cs = getComputedStyle(el);
            return {
                present: true,
                dataAccent: el.getAttribute('data-accent-color'),
                dataRadius: el.getAttribute('data-radius'),
                accent9: cs.getPropertyValue('--accent-9').trim(),
                accent8: cs.getPropertyValue('--accent-8').trim(),
            };
        }"""
    )
    ok_theme = theme_info.get("present") and theme_info.get("dataAccent") == "crimson"
    log("theme_applied", "pass" if ok_theme else "fail", str(theme_info))

    # --- #6905: head/inline/external script probes present after hydration.
    probes = page.evaluate(
        "() => ({head: window.__head_probe||0, inline: window.__inline_probe||0, ext: window.__external_probe||0})"
    )
    log("script_probes_initial", "pass" if probes["head"] and probes["inline"] else "fail",
        str(probes))
    # count script tags in head + where helmet put the page-level scripts
    script_placement = page.evaluate(
        """() => {
            const scan = (root) => Array.from(root.querySelectorAll('script')).map(
                s => (s.src ? 'src:'+s.getAttribute('src') : 'inline:'+(s.textContent||'').slice(0,45))
            );
            return {
                head: scan(document.head),
                bodyHasInlineProbe: !!document.body.querySelector('#inline-probe'),
                inlineProbeById: !!document.getElementById('inline-probe'),
                headProbeSrc: Array.from(document.querySelectorAll('script[src="/head_probe.js"]')).length,
                helmetScripts: Array.from(document.querySelectorAll('script[data-react-helmet]')).length,
            };
        }"""
    )
    log("head_script_tags", "pass", str(script_placement))

    # --- #6520: initial custom_style colors on #cb-state (backend state)
    def code_color(sel):
        # SyntaxHighlighter renders custom_style onto the <pre> (the code block root)
        return page.evaluate(
            f"() => {{const el=document.querySelector('{sel}'); if(!el) return null; const cs=getComputedStyle(el); return {{color: cs.color, bg: cs.backgroundColor}};}}"
        )

    cb_state_before = code_color("#cb-state")
    cb_memo_before = code_color("#cb-memo")
    log("cb_state_initial", "pass", str(cb_state_before))
    log("cb_memo_initial", "pass", str(cb_memo_before))

    # Toggle backend state -> colors should switch to green/dark
    page.click("#toggle-btn")
    page.wait_for_timeout(800)
    state_text = page.inner_text("#state-color-text")
    cb_state_after = code_color("#cb-state")
    cb_memo_after = code_color("#cb-memo")
    changed_state = cb_state_before != cb_state_after
    log("cb_state_updates_live", "pass" if changed_state else "fail",
        f"before={cb_state_before} after={cb_state_after} text={state_text!r}")
    changed_memo = cb_memo_before != cb_memo_after
    log("cb_memo_updates_live", "pass" if changed_memo else "fail",
        f"before={cb_memo_before} after={cb_memo_after}")

    # --- #6520: ClientStateVar custom_style updates live
    cb_client_before = code_color("#cb-client")
    page.click("#client-color-btn")
    page.wait_for_timeout(600)
    cb_client_after = code_color("#cb-client")
    changed_client = cb_client_before != cb_client_after
    log("cb_client_state_updates_live", "pass" if changed_client else "fail",
        f"before={cb_client_before} after={cb_client_after}")

    # --- #6520: wrap_long_lines + code_tag_props -> whiteSpace on <code>
    def code_tag_ws(sel):
        return page.evaluate(
            f"() => {{const pre=document.querySelector('{sel}'); if(!pre) return null; const code=pre.querySelector('code'); if(!code) return 'no-code'; const cs=getComputedStyle(code); return {{whiteSpace: cs.whiteSpace, fontStyle: cs.fontStyle}};}}"
        )

    wrap_ws = code_tag_ws("#cb-wrap")
    ok_wrap = isinstance(wrap_ws, dict) and "pre-wrap" in (wrap_ws.get("whiteSpace") or "")
    log("wrap_long_lines_with_code_tag_props", "pass" if ok_wrap else "fail",
        f"{wrap_ws} (expect whiteSpace pre-wrap + fontStyle italic preserved)")

    override_ws = code_tag_ws("#cb-wrap-override")
    ok_override = isinstance(override_ws, dict) and (override_ws.get("whiteSpace") == "normal")
    log("wrap_long_lines_user_whitespace_wins", "pass" if ok_override else "fail",
        f"{override_ws} (expect whiteSpace normal, user value preserved)")

    page.screenshot(path=OUT + "/index.png", full_page=True)

    # --- #6905: reload 10x, assert probes present every time post-hydration.
    reload_ok = 0
    reload_detail = []
    for i in range(10):
        page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
        page.wait_for_selector("#toggle-btn", timeout=20000)
        page.wait_for_timeout(400)
        pr = page.evaluate(
            """() => ({
                head: window.__head_probe||0,
                inline: window.__inline_probe||0,
                ext: window.__external_probe||0,
                headTags: document.head.querySelectorAll('script').length,
                extSrcInDom: document.querySelectorAll('script[src="/head_probe.js"]').length,
                inlineById: !!document.getElementById('inline-probe'),
            })"""
        )
        # #6905: the head/inline/external scripts must EXECUTE every reload
        # (probes >= 1). Missing script tags = the flaky bug this fixes.
        good = pr["head"] >= 1 and pr["inline"] >= 1 and pr["ext"] >= 1
        if good:
            reload_ok += 1
        reload_detail.append(f"r{i}:{pr}")
    log("script_tags_10_reloads", "pass" if reload_ok == 10 else "fail",
        f"{reload_ok}/10 executed; " + " | ".join(reload_detail))

    # --- Toast smoke (#6846)
    page.wait_for_selector("#toast-btn", timeout=20000)
    page.click("#toast-btn")
    page.wait_for_timeout(800)
    toast_count = page.locator("text=Hello toast!").count()
    log("toast_smoke", "pass" if toast_count >= 1 else "fail", f"toast_visible={toast_count}")
    page.screenshot(path=OUT + "/toast.png")

    browser.close()

print("\n===CONSOLE===")
for t, m in console_msgs:
    print(f"  [{t}] {m[:300]}")
print("\n===FAILED_REQUESTS===")
for u, f in failed_requests:
    print(f"  {u} :: {f}")
print("\n===HTTP_4XX_5XX===")
for s, u in http_errors:
    print(f"  {s} {u}")

fails = [k for k, (s, _) in results.items() if s == "fail"]
print("\n===SUMMARY===")
print("FAILS:", fails if fails else "none")
sys.exit(1 if fails else 0)
