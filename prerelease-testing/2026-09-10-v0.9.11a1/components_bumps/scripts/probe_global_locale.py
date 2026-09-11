"""Read moment's global locale from the running app page (Vite dep module)."""
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(4000)
    res = pg.evaluate("""async () => {
        const urls = performance.getEntriesByType('resource')
            .map(e => e.name)
            .filter(n => /moment/.test(n) && /\\.js($|\\?)/.test(n));
        const out = {resources: urls.slice(0, 12)};
        for (const u of urls) {
            try {
                const m = await import(/* @vite-ignore */ u);
                const mom = m.default ?? m;
                if (typeof mom === 'function' && mom.locale) { out.locale = mom.locale(); out.from = u; break; }
            } catch (e) { out.err = String(e); }
        }
        return out;
    }""")
    print(res)
    b.close()
