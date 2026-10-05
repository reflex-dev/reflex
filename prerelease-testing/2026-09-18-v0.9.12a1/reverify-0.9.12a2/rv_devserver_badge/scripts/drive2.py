"""Second pass: sticky badge a11y at 360px, real upload, SSR HTML, use_id duplicates."""

import json
import sys
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
PHASE = sys.argv[3] if len(sys.argv) > 3 else "dev"
BACKEND = sys.argv[4] if len(sys.argv) > 4 else BASE
OUT.mkdir(parents=True, exist_ok=True)

console: list[dict] = []
pageerrors: list[str] = []
bad: list[dict] = []
res: dict = {}

upfile = OUT.parent / "up.txt"
upfile.write_text("hello upload\n")

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: pageerrors.append(str(e)))
    page.on(
        "response",
        lambda r: bad.append({"url": r.url, "status": r.status})
        if r.status >= 400
        else None,
    )

    page.goto(f"{BASE}/misc", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)

    def badge_info():
        return page.evaluate(
            """() => Array.from(document.querySelectorAll('a')).filter(
                a => (a.href || '').includes('reflex.dev')
            ).map(a => {
                const label = a.querySelector('span');
                return {
                    aria: a.getAttribute('aria-label'),
                    text: a.innerText,
                    textContent: a.textContent.trim(),
                    labelDisplay: label ? getComputedStyle(label).display : null,
                    labelVisible: label ? !!(label.offsetWidth || label.offsetHeight) : null,
                    pos: getComputedStyle(a).position,
                };
            })"""
        )

    res["badge_1280"] = badge_info()
    page.screenshot(path=str(OUT / f"{PHASE}-badge-1280.png"))
    page.set_viewport_size({"width": 360, "height": 780})
    page.wait_for_timeout(1500)
    res["badge_360"] = badge_info()
    page.screenshot(path=str(OUT / f"{PHASE}-badge-360.png"))
    page.set_viewport_size({"width": 1280, "height": 900})
    page.wait_for_timeout(600)

    # duplicate DOM ids from use_id inside foreach
    res["dup_id_check"] = page.evaluate(
        """() => {
            const ids = Array.from(document.querySelectorAll('[id]')).map(e => e.id);
            const seen = {}; const dups = [];
            for (const i of ids) { if (seen[i]) { dups.push(i); } seen[i] = true; }
            return {total: ids.length, dups: Array.from(new Set(dups))};
        }"""
    )
    res["label_resolution"] = page.evaluate(
        """() => Array.from(document.querySelectorAll('#ids-box label')).map(l => {
            const t = document.getElementById(l.getAttribute('for'));
            return {for: l.getAttribute('for'), text: l.textContent,
                    targetValue: t ? t.value : null};
        })"""
    )

    # real upload through the browser
    page.goto(f"{BASE}/upload", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    fi = page.locator("input[type=file]")
    res["file_input_count"] = fi.count()
    if fi.count():
        fi.first.set_input_files(str(upfile))
        page.wait_for_timeout(2500)
    res["upload_files_text"] = page.locator("#upload-files").inner_text()
    page.screenshot(path=str(OUT / f"{PHASE}-upload.png"))

    browser.close()

res["console_err_warn"] = [m for m in console if m["type"] in ("error", "warning")]
res["pageerrors"] = pageerrors
res["bad_responses"] = bad

# SSR HTML for the code page (no JS)
with httpx.Client(timeout=30.0, trust_env=False) as c:
    for path in ("/code", "/misc", "/sankey"):
        r = c.get(f"{BASE}{path}")
        html = r.text
        res.setdefault("ssr", {})[path] = {
            "status": r.status_code,
            "len": len(html),
            "has_greet": "def greet" in html,
            "has_below_fold": "below the fold" in html,
            "has_builtwith_aria": 'aria-label="Built with Reflex"' in html,
            "has_sankey_svg": "recharts" in html.lower(),
        }
    # upload 400s
    files = {"files": ("a.txt", b"hello", "text/plain")}
    r = c.post(
        f"{BACKEND}/_upload",
        files=files,
        headers={
            "reflex-client-token": "tok",
            "reflex-event-handler": "no.such.Handler",
        },
    )
    res["upload_unknown_handler"] = {"status": r.status_code, "body": r.text[:200]}

(OUT / f"{PHASE}-results2.json").write_text(json.dumps(res, indent=2, default=str))
print(json.dumps(res, indent=2, default=str))
