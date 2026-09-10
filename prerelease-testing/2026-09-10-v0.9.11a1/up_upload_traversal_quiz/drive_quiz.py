"""Playwright driver for the reflex-examples `quiz` app (rx.code_block / shiki + rx.table focus).

Usage:
    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_quiz.py <frontend_url> <artifacts_dir> <label> [<app_dir>]

<app_dir> (optional) lets the driver record the npm package versions actually installed under
<app_dir>/.web/node_modules (shiki, @shikijs/transformers, react-syntax-highlighter, sonner, ...).

Flows: index render (heading, 3 questions), shiki-highlighted code block (text, token spans,
theme), radio / checkbox interactions, Submit -> redirect to /result -> score heading, radix
progress, rx.table rows with lucide check/x icons, "Take Quiz Again" -> on_load resets answers,
partial-answer score, direct /result load in a fresh context, color-mode toggle (code block theme
switch), console / page errors / failed requests / screenshots.

/shiki page (ADDED to the app copy for this upgrade test, see quiz/quiz/shiki_page.py): rx._x.code_block
(shiki 4.3.1 -> 4.4.3 in this train) - tokenized spans, transformers notation ([!code highlight],
[!code ++]/[!code --]) stripped + classes applied, CSS-counter line numbers, default theme following
color mode (one-light -> one-dark-pro), explicit github-dark theme, copy button -> clipboard,
state-driven code re-highlighting, state-driven language switch, rx.table.
"""

import json
import sys
from pathlib import Path

from drive_common import Run, wait_for

FRONTEND = sys.argv[1].rstrip("/")
ART = sys.argv[2]
LABEL = sys.argv[3]
APP_DIR = Path(sys.argv[4]) if len(sys.argv) > 4 else None

CODE = "a = [10, 20]\nb = a\nb += [30, 40]\nprint(a)"


def code_block_info(page):
    return page.evaluate(
        """() => {
          const pre = document.querySelector('pre.shiki, pre[class*=shiki], pre code, pre');
          if (!pre) return null;
          const root = pre.tagName === 'CODE' ? pre.closest('pre') : pre;
          const spans = root.querySelectorAll('span[style*=color], span[class*=line] span');
          const colors = new Set(Array.from(spans).map(s => s.style.color).filter(Boolean));
          return {
            tag: root.tagName, cls: root.className, text: root.innerText.replace(/\\n+$/, ''),
            spans: spans.length, distinct_colors: colors.size,
            bg: getComputedStyle(root).backgroundColor, fg: getComputedStyle(root).color,
            style: root.getAttribute('style'),
          };
        }"""
    )


def result_rows(page):
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('tbody tr')).map(tr => ({
            cells: Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim()),
            icon: tr.querySelector('svg')?.getAttribute('class') || null,
        }))"""
    )


with Run(ART, LABEL) as run:
    ctx, page = run.new_page()
    page.goto(FRONTEND, wait_until="networkidle")
    page.wait_for_timeout(1000)
    run.record("page_title", "pass" if page.title() == "Quiz - Reflex" else "fail", f"title={page.title()!r}")
    run.record("heading", "pass" if page.get_by_role("heading", name="Python Quiz").count() == 1 else "fail",
               "Python Quiz heading")
    for q in ("Question #1", "Question #2", "Question #3"):
        run.record(f"heading_{q[-2:].strip('#')}", "pass" if page.get_by_role("heading", name=q).count() == 1 else "fail", q)

    # shiki code block: wait for tokenized spans (highlighting is async on the client)
    ok = wait_for(lambda: (code_block_info(page) or {}).get("spans", 0) > 3, 20)
    info = code_block_info(page)
    run.shot(page, "01_index.png", full_page=True)
    text_ok = bool(info) and info["text"].replace(" ", " ") == CODE
    run.record("code_block_text", "pass" if text_ok else "fail", f"text={info and info['text']!r}")
    run.record("code_block_shiki_tokens", "pass" if ok and info["distinct_colors"] >= 3 else "fail",
               f"spans={info and info['spans']} distinct_colors={info and info['distinct_colors']} "
               f"tag={info and info['tag']} class={info and info['cls']!r}")
    light_bg = info and info["bg"]
    run.record("code_block_light_theme_bg", "pass" if light_bg and light_bg != "rgba(0, 0, 0, 0)" else "anomaly",
               f"bg={light_bg} fg={info and info['fg']} style={info and info['style']!r}")

    radios = page.get_by_role("radio")
    run.record("radio_count", "pass" if radios.count() == 4 else "fail", f"radios={radios.count()}")
    checks = page.get_by_role("checkbox")
    run.record("checkbox_count", "pass" if checks.count() == 5 else "fail", f"checkboxes={checks.count()}")

    # answer everything correctly: Q1 False, Q2 [10, 20, 30, 40], Q3 boxes 3,4,5
    page.get_by_role("radio", name="False").click()
    page.get_by_role("radio", name="[10, 20, 30, 40]").click()
    for i in (2, 3, 4):
        checks.nth(i).click()
    page.wait_for_timeout(300)
    states = [checks.nth(i).get_attribute("aria-checked") or checks.nth(i).get_attribute("data-state") for i in range(5)]
    run.record("checkboxes_checked", "pass" if states[2:] == ["true"] * 3 or states[2:] == ["checked"] * 3 else "fail",
               f"states={states}")
    run.shot(page, "02_answered.png", full_page=True)
    page.get_by_role("button", name="Submit").click()
    wait_for(lambda: page.get_by_role("heading", name="Results").count() == 1, 15)
    ok = wait_for(lambda: page.url.rstrip("/").endswith("/result"), 10)
    page.wait_for_timeout(800)
    run.shot(page, "03_results_100.png", full_page=True)
    run.record("submit_redirects_to_result", "pass" if ok else "fail", f"url={page.url}")
    run.record("result_page_title", "pass" if page.title() == "Quiz Results" else "fail", f"title={page.title()!r}")
    score = page.get_by_role("heading", name="100%").count()
    prog = page.locator("[role=progressbar]").first.get_attribute("aria-valuenow")
    run.record("score_100_percent", "pass" if score == 1 and prog == "100" else "fail",
               f"heading 100%={score} progress aria-valuenow={prog}")
    rows = result_rows(page)
    all_check = len(rows) == 3 and all(r["icon"] and "check" in r["icon"] for r in rows)
    run.record("table_rows_all_check_icons", "pass" if all_check else "fail", f"rows={rows}")
    if len(rows) == 3:
        run.record("table_answer_texts", "pass" if rows[0]["cells"][2:] == ['"False"', '"False"']
                   and rows[1]["cells"][2] == '"[10, 20, 30, 40]"'
                   and rows[2]["cells"][2] == "[false,false,true,true,true]" else "anomaly",
                   f"cells={[r['cells'] for r in rows]}")

    # Take Quiz Again -> on_load resets answers -> submit without answering -> 0%
    page.get_by_role("link", name="Take Quiz Again").click()
    wait_for(lambda: page.get_by_role("heading", name="Python Quiz").count() == 1, 10)
    page.wait_for_timeout(500)
    radio_states = [page.get_by_role("radio").nth(i).get_attribute("aria-checked") for i in range(4)]
    run.record("quiz_again_radios_unchecked_ui", "pass" if "true" not in radio_states else "anomaly",
               f"radio aria-checked={radio_states} (uncontrolled radix radios: UI state may not reset)")
    page.get_by_role("button", name="Submit").click()
    wait_for(lambda: page.get_by_role("heading", name="Results").count() == 1, 10)
    page.wait_for_timeout(600)
    rows = result_rows(page)
    prog = page.locator("[role=progressbar]").first.get_attribute("aria-valuenow")
    run.shot(page, "04_results_0.png", full_page=True)
    run.record("onload_reset_gives_0_percent",
               "pass" if page.get_by_role("heading", name="0%").count() == 1 and prog == "0" else "fail",
               f"progress={prog} rows={rows}")
    x_icons = len(rows) == 3 and all(r["icon"] and "lucide-x" in r["icon"] for r in rows)
    run.record("table_rows_all_x_icons", "pass" if x_icons else "fail", f"icons={[r['icon'] for r in rows]}")

    # partial: only Q1 correct -> 33%
    page.get_by_role("link", name="Take Quiz Again").click()
    wait_for(lambda: page.get_by_role("radio").count() == 4, 10)
    page.wait_for_timeout(400)
    page.get_by_role("radio", name="False").click()
    page.get_by_role("button", name="Submit").click()
    wait_for(lambda: page.get_by_role("heading", name="Results").count() == 1, 10)
    page.wait_for_timeout(600)
    prog = page.locator("[role=progressbar]").first.get_attribute("aria-valuenow")
    run.record("partial_score_33", "pass" if page.get_by_role("heading", name="33%").count() == 1 and prog == "33" else "fail",
               f"progress={prog} rows={result_rows(page)}")

    # color mode toggle on the results page then back on index: code block theme switches
    page.get_by_role("link", name="Take Quiz Again").click()
    wait_for(lambda: (code_block_info(page) or {}).get("spans", 0) > 3, 20)
    before = code_block_info(page)
    page.locator("button").filter(has=page.locator("svg")).first.click()  # color-mode button
    ok = wait_for(lambda: "dark" in page.evaluate("document.documentElement.className"), 5)
    page.wait_for_timeout(800)
    after = code_block_info(page)
    run.shot(page, "05_index_dark.png", full_page=True)
    run.record("color_mode_toggle", "pass" if ok else "fail",
               f"html.class={page.evaluate('document.documentElement.className')!r}")
    run.record("code_block_dark_theme_switch", "pass" if after and before and after["bg"] != before["bg"] else "anomaly",
               f"bg {before and before['bg']} -> {after and after['bg']} fg {before and before['fg']} -> {after and after['fg']}")
    ctx.close()

    # fresh context: direct load of /result with default state
    ctx2, page2 = run.new_page("ctx2")
    page2.goto(FRONTEND + "/result", wait_until="networkidle")
    wait_for(lambda: page2.get_by_role("heading", name="Results").count() == 1, 10)
    page2.wait_for_timeout(600)
    rows = result_rows(page2)
    run.shot(page2, "06_result_direct.png", full_page=True)
    run.record("direct_result_load", "pass" if page2.get_by_role("heading", name="0%").count() == 1 and len(rows) == 3 else "anomaly",
               f"rows={rows}")
    # shiki / table module URLs actually served (dev server)
    page2.goto(FRONTEND, wait_until="networkidle")
    wait_for(lambda: (code_block_info(page2) or {}).get("spans", 0) > 3, 20)
    urls = page2.evaluate(
        """() => performance.getEntriesByType('resource').map(e => e.name).filter(n => /shiki/.test(n)).map(n => n.replace(/^.*?\\/node_modules\\//, '')).slice(0, 8)"""
    )
    run.record("shiki_module_urls", "pass", f"{urls}")
    ctx2.close()

    # /shiki page: rx._x.code_block coverage (fresh context, light mode)
    ctx3, page3 = run.new_page("shiki")
    ctx3.grant_permissions(["clipboard-read", "clipboard-write"], origin=FRONTEND)
    page3.goto(FRONTEND + "/shiki", wait_until="networkidle")

    def block(sel):
        return page3.evaluate(
            """(sel) => {
              const pre = document.querySelector(sel + ' pre');
              if (!pre) return null;
              const lines = Array.from(pre.querySelectorAll('.line'));
              const spans = pre.querySelectorAll('span[style*=color]');
              const first = lines[0];
              const before = first ? getComputedStyle(first, '::before') : null;
              return {
                cls: pre.className, bg: getComputedStyle(pre).backgroundColor, fg: getComputedStyle(pre).color,
                lines: lines.length, spans: spans.length,
                distinct_colors: new Set(Array.from(spans).map(s => s.style.color)).size,
                text: pre.innerText, highlighted: pre.querySelectorAll('.line.highlighted').length,
                diff_add: pre.querySelectorAll('.line.diff.add').length,
                diff_remove: pre.querySelectorAll('.line.diff.remove').length,
                ln_content: before ? before.content : null, ln_width: before ? before.width : null,
                last_line: lines.length ? lines[lines.length - 1].innerText : null,
                last_line_spans: lines.length ? lines[lines.length - 1].querySelectorAll('span[style*=color]').length : 0,
              };
            }""",
            sel,
        )

    ok = wait_for(lambda: all((block(b) or {}).get("spans", 0) >= 5 for b in ("#block-a", "#block-b", "#block-c")), 40)
    page3.wait_for_timeout(500)
    a, b, c = block("#block-a"), block("#block-b"), block("#block-c")
    run.shot(page3, "07_shiki_light.png", full_page=True)
    run.record("shiki_blocks_highlighted", "pass" if ok else "fail",
               f"A={a and (a['cls'], a['spans'], a['distinct_colors'])} B={b and (b['cls'], b['spans'])} C={c and (c['cls'], c['spans'])}")
    if a:
        # Compiled memo prop for block A (grounds the DOM result in what reflex actually emitted).
        block_a_memo = ""
        if APP_DIR:
            mp = APP_DIR / ".web" / "app_components" / "quiz" / "shiki_page.jsx"
            if mp.exists():
                import re as _re
                mm = _re.search(r"transformers:(\[[^\]]*\])\},\)\n\s*\)\n\}\);\nShikicodeblock_code", mp.read_text())
                block_a_memo = mm.group(1) if mm else ""
        applied = a["highlighted"] == 1 and a["diff_add"] == 1 and a["diff_remove"] == 1 and "[!code" not in a["text"]
        run.record("shiki_transformers_notation",
                   "pass" if applied else "anomaly",
                   f"applied={applied} lines={a['lines']} highlighted={a['highlighted']} diff_add={a['diff_add']} "
                   f"diff_remove={a['diff_remove']} marker_left_in_text={'[!code' in a['text']} "
                   f"compiled_block_a_transformers_prop={block_a_memo!r} "
                   "(use_transformers=True drops the shikijs transformer fns -> transformers:[] in compiled output; "
                   "notation not applied. Compare across versions.)")
        run.record("shiki_line_numbers_css_counter",
                   "pass" if a["ln_content"] and "counter" in a["ln_content"] and a["ln_width"] == "16px" else "anomaly",
                   f"::before content={a['ln_content']!r} width={a['ln_width']}")
        run.record("shiki_default_theme_light", "pass" if "one-light" in a["cls"] and a["bg"] == "rgb(250, 250, 250)" else "anomaly",
                   f"class={a['cls']!r} bg={a['bg']} fg={a['fg']}")
    if b:
        run.record("shiki_explicit_theme_github_dark", "pass" if "github-dark" in b["cls"] and b["bg"] == "rgb(36, 41, 46)" else "anomaly",
                   f"class={b['cls']!r} bg={b['bg']} lines={b['lines']} (notation markers kept as text: {'[!code' in b['text']})")
    rows3 = page3.locator("#pins-table tbody tr").count()
    run.record("shiki_page_table_rows", "pass" if rows3 == 3 else "fail", f"rows={rows3}")

    # copy button (block A) -> clipboard gets the code with the notation markers stripped
    try:
        page3.locator("#block-a button").first.click()
        page3.wait_for_timeout(500)
        clip = page3.evaluate("navigator.clipboard.readText()")
        run.record("shiki_copy_button_clipboard",
                   "pass" if "def greet" in clip and "[!code" not in clip else "fail",
                   f"clipboard={clip[:160]!r}")
    except Exception as e:  # noqa: BLE001
        run.record("shiki_copy_button_clipboard", "skipped", f"clipboard unavailable in this browser context: {str(e)[:120]}")

    # state-driven code: Add line -> extra_lines increments -> block B re-highlights with one more line.
    lines_before = (block("#block-b") or {}).get("lines")
    page3.locator("#add-line").click()
    ok = wait_for(lambda: page3.locator("#extra-lines").inner_text().strip() == "extra lines: 1", 15)
    grew = wait_for(lambda: (block("#block-b") or {}).get("lines", 0) > (lines_before or 0), 15)
    b2 = block("#block-b")
    # the last rendered .line is shiki's trailing blank; the newly added code line ("print(0)") is the one before it
    code_lines = [ln for ln in (b2["text"].splitlines() if b2 else []) if ln.strip()]
    last_code_line = code_lines[-1].strip() if code_lines else None
    run.record("shiki_dynamic_code_rehighlights",
               "pass" if ok and grew and last_code_line == "print(0)" else "fail",
               f"extra_lines_text={page3.locator('#extra-lines').inner_text()!r} lines {lines_before}->{b2 and b2['lines']} "
               f"last_code_line={last_code_line!r}")

    # state-driven language switch: python -> javascript
    page3.locator("#toggle-language").click()
    ok = wait_for(lambda: "export function add" in ((block("#block-c") or {}).get("text") or "")
                  and (block("#block-c") or {}).get("spans", 0) >= 5, 20)
    c2 = block("#block-c")
    run.record("shiki_language_switch", "pass" if ok and page3.locator("#language").inner_text().strip() == "language: javascript" else "fail",
               f"language_text={page3.locator('#language').inner_text()!r} spans={c2 and c2['spans']} lines={c2 and c2['lines']}")

    # color mode -> dark: block A switches to one-dark-pro, block B stays github-dark
    page3.locator("button:has(.lucide-sun), button:has(.lucide-moon)").first.click()
    ok = wait_for(lambda: "one-dark-pro" in ((block("#block-a") or {}).get("cls") or ""), 15)
    page3.wait_for_timeout(500)
    a3, b3 = block("#block-a"), block("#block-b")
    run.shot(page3, "08_shiki_dark.png", full_page=True)
    run.record("shiki_default_theme_follows_dark_mode",
               "pass" if ok and a3 and a3["bg"] == "rgb(40, 44, 52)" else "fail",
               f"class={a3 and a3['cls']!r} bg={a3 and a3['bg']} html.class={page3.evaluate('document.documentElement.className')!r}")
    run.record("shiki_explicit_theme_unaffected_by_dark_mode",
               "pass" if b3 and "github-dark" in b3["cls"] and b3["bg"] == "rgb(36, 41, 46)" else "fail",
               f"class={b3 and b3['cls']!r} bg={b3 and b3['bg']}")
    ctx3.close()

    if APP_DIR:
        versions = {}
        for pkg in ("shiki", "@shikijs/transformers", "@shikijs/core", "react-syntax-highlighter", "sonner",
                    "@radix-ui/themes", "react-router", "vite", "react", "lucide-react"):
            pj = APP_DIR / ".web" / "node_modules" / pkg / "package.json"
            versions[pkg] = json.loads(pj.read_text())["version"] if pj.exists() else None
        run.record("installed_npm_versions", "pass", json.dumps(versions))

