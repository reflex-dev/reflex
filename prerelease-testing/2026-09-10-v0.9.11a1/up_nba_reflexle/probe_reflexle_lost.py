"""Isolated probe: play six guaranteed-losing guesses in reflexle and capture the websocket
frames, so we can see exactly what the frontend is told about `game_status`.

usage: probe_reflexle_lost.py <frontend_url> <out_dir>
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
WORDS = ["homes", "gawks", "bumph", "vexed", "quips", "mylar"]

frames = []


def grid_rows(page):
    return page.evaluate(
        """() => {
      const boxes=[...document.querySelectorAll('div.rt-Flex')].filter(d=>{const r=d.getBoundingClientRect();
        return Math.abs(r.width-r.height)<2 && r.width>30 && r.width<90 && d.children.length<=1;});
      boxes.sort((a,b)=>{const ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect(); return (ra.y-rb.y)||(ra.x-rb.x);});
      const t=boxes.map(d=>d.innerText.trim()); const rows=[];
      for(let i=0;i<t.length;i+=5) rows.push(t.slice(i,i+5).join(''));
      return rows;}"""
    )


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    page.on(
        "websocket",
        lambda ws: (
            ws.on("framesent", lambda pl: frames.append(("sent", str(pl)[:1500]))),
            ws.on("framereceived", lambda pl: frames.append(("recv", str(pl)[:1500]))),
        ),
    )
    page.goto(URL, wait_until="load", timeout=90_000)
    page.wait_for_timeout(4000)

    for i, w in enumerate(WORDS, 1):
        for ch in w:
            page.keyboard.press(ch)
            page.wait_for_timeout(180)
        page.wait_for_timeout(400)
        page.keyboard.press("Enter")
        page.wait_for_timeout(2200)
        print(f"after guess {i} ({w}): rows={grid_rows(page)} banner={'Word is' in page.inner_text('body')}")

    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    print("\nFINAL rows:", grid_rows(page))
    print("banner present:", "Word is" in body)
    print("body:", json.dumps(body[:400]))
    page.screenshot(path=str(OUT / "lost_probe.png"), full_page=True)

    gs = [f for f in frames if "game_status" in f[1]]
    (OUT / "ws_frames.json").write_text(json.dumps(frames, indent=1))
    print(f"\n{len(gs)} frames mentioning game_status; last 3:")
    for kind, payload in gs[-3:]:
        print(" ", kind, payload[:900])

    # after a full reload the hydrate carries the whole state
    page.reload(wait_until="load")
    page.wait_for_timeout(4500)
    print("\nafter reload: rows=", grid_rows(page), "banner=", "Word is" in page.inner_text("body"))
    page.screenshot(path=str(OUT / "lost_probe_after_reload.png"), full_page=True)
    hydrate = [f for f in frames if "game_status" in f[1]]
    print("last frame mentioning game_status after reload:")
    if hydrate:
        print(" ", hydrate[-1][0], hydrate[-1][1][:900])
    (OUT / "ws_frames.json").write_text(json.dumps(frames, indent=1))
    b.close()
