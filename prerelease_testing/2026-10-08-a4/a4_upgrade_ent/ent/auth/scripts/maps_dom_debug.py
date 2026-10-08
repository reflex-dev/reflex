"""Dump the Leaflet DOM of mapsapp pages (debug helper). Usage: maps_dom_debug.py <base>"""
import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, attach  # noqa: E402
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page()
    d = {}
    attach(page, d)
    for path in ("/", "/layers"):
        page.goto(BASE + path)
        page.wait_for_timeout(8000)
        info = page.evaluate("""() => {
          const c = document.querySelector('.leaflet-container');
          return {container: c ? {id: c.id, cls: c.className.slice(0,120), parentId: c.parentElement && c.parentElement.id} : null,
                  ids: [...document.querySelectorAll('[id]')].map(e => e.id).filter(i => i.includes('map')),
                  paths: document.querySelectorAll('.leaflet-overlay-pane path').length,
                  tiles: document.querySelectorAll('.leaflet-tile-pane img').length,
                  markers: document.querySelectorAll('.leaflet-marker-icon').length,
                  controls: [...document.querySelectorAll('.leaflet-control')].map(e => e.className.slice(0,60))}
        }""")
        print(path, json.dumps(info))
    print("console errors", [c["text"][:120] for c in d["console"] if c["type"] == "error"][:6])
    print("page errors", d["page_errors"][:3])
    b.close()
