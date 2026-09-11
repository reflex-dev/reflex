"""Drive the nested-theme repro app and dump the .radix-themes classes."""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1]
outdir = pathlib.Path(sys.argv[2])
outdir.mkdir(parents=True, exist_ok=True)
url = base + (sys.argv[3] if len(sys.argv) > 3 else "/")

console = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1100, "height": 1400})
    pg = ctx.new_page()
    pg.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(2500)
    info = pg.evaluate(
        """() => {
      const themes = Array.from(document.querySelectorAll('.radix-themes')).map(e => ({
        className: e.className,
        isRoot: e.getAttribute('data-is-root-theme'),
        hasBackground: e.getAttribute('data-has-background'),
        accentColor: e.getAttribute('data-accent-color'),
        firstHeading: (e.querySelector('h3') || {}).textContent || null,
      }));
      const cards = Array.from(document.querySelectorAll('[id^="card-"]')).map(e => {
        const cs = getComputedStyle(e);
        return {id: e.id, bg: cs.backgroundColor, color: cs.color};
      });
      return {themes, cards, localStorageTheme: localStorage.getItem('theme'),
              htmlClass: document.documentElement.className,
              htmlStyle: document.documentElement.getAttribute('style')};
    }"""
    )
    pg.screenshot(path=str(outdir / "page.png"), full_page=True)
    (outdir / "dom.json").write_text(json.dumps(info, indent=2))
    (outdir / "console.txt").write_text("\n".join(console))
    b.close()
print(json.dumps(info, indent=2))
print("\nCONSOLE:")
print("\n".join(console) or "(none)")
