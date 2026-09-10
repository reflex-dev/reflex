"""Exercise the Safari dev-server cache-busting plugin (#7048) against a running `reflex run` dev server.

Loads /, /about (emoji, CJK, accents) and /long (>64KB of text) with a Safari UA and a Chrome UA,
in a real Chromium page and through raw HTTP, and checks that the HTML is real HTML (not
comma-separated byte values), that non-ASCII text is intact (no U+FFFD), that modulepreload hrefs
were rewritten with __reflex_ts for Safari only, and that the two UA variants are otherwise equal.

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python safari_test.py \
        --url http://localhost:3100 --out $SB/apps/hmr_runtime/logs/safari
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
SAFARI_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
CHROME_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]
TS_RE = re.compile(r"[?&]__reflex_ts=\d+")
BYTES_RE = re.compile(r"^\s*(\d{1,3},){20,}")

PAGES = {
    "/": ["#heading", "HMR Runtime App"],
    "/about": ["#about-heading", "About — café über naïve"],
    "/long": ["#long-end", "END OF LONG PAGE \U0001F3C1"],
}
EXPECTED_TEXT = {
    "/about": {
        "#emoji-text": "Emoji: \U0001F389 \U0001F680 \U0001F60E \U0001F1EF\U0001F1F5 \U0001F468‍\U0001F469‍\U0001F467",
        "#cjk-text": "CJK: 日本語のテスト 中文测试文本 한국어 테스트",
        "#accent-text": "Accents: éèêë àâ ñ ø å ß ıİ șț",
    },
}


def analyze_html(body: bytes, headers: dict) -> dict:
    text = body.decode("utf-8", errors="replace")
    return {
        "bytes": len(body),
        "starts_with": text[:60],
        "is_html": text.lstrip().lower().startswith("<!doctype html") or text.lstrip().startswith("<html"),
        "looks_like_byte_list": bool(BYTES_RE.match(text)),
        "has_replacement_char": "�" in text,
        "modulepreload_links": len(re.findall(r'<link\s+rel="modulepreload"', text)),
        "reflex_ts_occurrences": len(TS_RE.findall(text)),
        "x_modified_by": headers.get("x-modified-by"),
        "content_type": headers.get("content-type"),
        "transfer_encoding": headers.get("transfer-encoding"),
        "content_length": headers.get("content-length"),
        "has_cjk": "日本語" in text,
        "has_emoji": "\U0001F389" in text,
        "has_accents": "café" in text or "naïve" in text,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--render-timeout", type=float, default=60, help="seconds to wait for the page to render")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"url": args.url, "browser": {}, "raw": {}, "compare": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for ua_name, ua in [("safari", SAFARI_UA), ("chrome", CHROME_UA)]:
            ctx = browser.new_context(user_agent=ua, viewport={"width": 1100, "height": 800})
            page = ctx.new_page()
            console, errors, failed, bad = [], [], [], []
            page.on("console", lambda m: console.append((m.type, m.text)))
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("requestfailed", lambda r: failed.append(f"{r.url} {r.failure}"))
            page.on("response", lambda r: r.status >= 400 and bad.append(f"{r.status} {r.url}"))
            ts_requests = []
            page.on("request", lambda r: TS_RE.search(r.url) and ts_requests.append(r.url))
            per_page = {}
            for route, (sel, expected) in PAGES.items():
                t0 = time.time()
                resp = page.goto(args.url + route, wait_until="networkidle")
                body = resp.body()
                info = analyze_html(body, resp.headers)
                info["status"] = resp.status
                rendered = True
                try:
                    page.wait_for_selector(sel, timeout=args.render_timeout * 1000)
                except Exception as e:  # noqa: BLE001
                    rendered = False
                    info["render_error"] = f"{type(e).__name__}: {str(e)[:160]}"
                    info["visible_text_head"] = page.evaluate("document.body ? document.body.innerText.slice(0, 200) : null")
                info["rendered"] = rendered
                info["load_ms"] = round((time.time() - t0) * 1000)
                texts = {}
                if rendered:
                    info["sel_text"] = page.inner_text(sel).strip()
                    info["sel_text_ok"] = info["sel_text"] == expected
                    for tsel, texp in EXPECTED_TEXT.get(route, {}).items():
                        got = page.inner_text(tsel).strip()
                        texts[tsel] = {"ok": got == texp, "got": got}
                info["texts"] = texts
                if route == "/long" and rendered:
                    info["long_para_count"] = page.evaluate("document.querySelectorAll('.long-para').length")
                    info["body_text_len"] = page.evaluate("document.body.innerText.length")
                    info["body_text_has_fffd"] = page.evaluate("document.body.innerText.includes('\\ufffd')")
                # do a client-side interaction on / to prove the app is alive
                if route == "/" and rendered:
                    page.click("#inc-btn")
                    page.wait_for_timeout(800)
                    info["count_after_click"] = page.inner_text("#memo-count").strip()
                (out / f"{ua_name}{route.replace('/', '_') or '_index'}.html").write_bytes(body)
                page.screenshot(path=str(out / f"{ua_name}{route.replace('/', '_') or '_index'}.png"))
                per_page[route] = info
                print(f"[{ua_name}] {route}: {json.dumps({k: v for k, v in info.items() if k != 'texts'})}")
                for tsel, r in texts.items():
                    print(f"      {tsel}: ok={r['ok']} got={r['got']!r}")
            report["browser"][ua_name] = {
                "pages": per_page,
                "console_errors": [f"{k}: {t}" for k, t in console if k in ("error", "warning") and not any(b.search(t) for b in BENIGN)],
                "console_all": [f"{k}: {t[:160]}" for k, t in console],
                "page_errors": errors,
                "failed_requests": failed,
                "bad_responses": bad,
                "requests_with_reflex_ts": len(ts_requests),
                "sample_ts_requests": ts_requests[:5],
            }
            print(f"[{ua_name}] console errors/warnings: {report['browser'][ua_name]['console_errors']}")
            print(f"[{ua_name}] page errors: {errors}; failed: {failed}; bad: {bad}; requests with __reflex_ts: {len(ts_requests)}")
            ctx.close()
        # Raw HTTP fetches (Accept: text/html) with each UA via Playwright's request context.
        for ua_name, ua in [("safari", SAFARI_UA), ("chrome", CHROME_UA)]:
            rc = p.request.new_context(user_agent=ua, extra_http_headers={"Accept": "text/html,application/xhtml+xml"})
            raws = {}
            for route in PAGES:
                r = rc.get(args.url + route)
                body = r.body()
                info = analyze_html(body, r.headers)
                info["status"] = r.status
                (out / f"raw_{ua_name}{route.replace('/', '_') or '_index'}.html").write_bytes(body)
                raws[route] = info
                print(f"[raw {ua_name}] {route}: {json.dumps(info)}")
            report["raw"][ua_name] = raws
            rc.dispose()
        browser.close()
    # Compare safari vs chrome raw bodies after stripping the cache-bust param.
    for route in PAGES:
        s = (out / f"raw_safari{route.replace('/', '_') or '_index'}.html").read_text(encoding="utf-8", errors="replace")
        c = (out / f"raw_chrome{route.replace('/', '_') or '_index'}.html").read_text(encoding="utf-8", errors="replace")
        s2 = TS_RE.sub("", s)
        # React streaming may emit different hydration ids; compare lengths and text content coarse-grained.
        same = s2 == c
        report["compare"][route] = {"identical_after_strip": same, "safari_len": len(s), "chrome_len": len(c), "stripped_len": len(s2)}
        if not same:
            # find first difference
            i = next((i for i in range(min(len(s2), len(c))) if s2[i] != c[i]), min(len(s2), len(c)))
            report["compare"][route]["first_diff_at"] = i
            report["compare"][route]["safari_ctx"] = s2[max(0, i - 80) : i + 80]
            report["compare"][route]["chrome_ctx"] = c[max(0, i - 80) : i + 80]
        print(f"[compare] {route}: {report['compare'][route]}")
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("report:", out / "report.json")


if __name__ == "__main__":
    main()
