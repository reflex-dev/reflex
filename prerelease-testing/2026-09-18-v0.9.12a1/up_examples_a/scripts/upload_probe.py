"""Focused probe of the upload example: DOM around the Files: heading + ws deltas."""
import json, sys, time, re
from pathlib import Path
from playwright.sync_api import sync_playwright

url, tag, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
frames = []
rec = {"tag": tag}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1100, "height": 950})
    page = ctx.new_page()
    console = []
    page.on("console", lambda m: console.append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: console.append(f"[pageerror] {e}"))
    page.on("websocket", lambda ws: ws.on("framereceived", lambda pl: frames.append(pl.payload if hasattr(pl, "payload") else str(pl))))
    page.goto(url, timeout=90000)
    page.wait_for_selector("text=Select File(s)", timeout=60000)
    rec["files_before"] = page.locator("a").all_inner_texts()
    d = out / "probefiles"; d.mkdir(exist_ok=True)
    f1 = d / f"probe-{tag}.txt"; f1.write_text("probe " + tag + "\n")
    page.set_input_files("input[type=file]", [str(f1)])
    page.wait_for_timeout(500)
    page.click("button:has-text('Upload')")
    page.wait_for_timeout(3000)
    rec["a_count_after_upload"] = page.locator("a").count()
    rec["a_texts_after_upload"] = page.locator("a").all_inner_texts()
    html = page.content()
    m = html.find("Files:")
    rec["html_around_files"] = re.sub(r"\s+", " ", html[m-200:m+1500]) if m >= 0 else "NOT FOUND"
    page.screenshot(path=str(out / f"upload-probe-{tag}-afterupload.png"))
    page.reload(); page.wait_for_selector("text=Select File(s)", timeout=60000); page.wait_for_timeout(2500)
    rec["a_count_after_reload"] = page.locator("a").count()
    rec["a_texts_after_reload"] = page.locator("a").all_inner_texts()
    html2 = page.content(); m2 = html2.find("Files:")
    rec["html_around_files_reload"] = re.sub(r"\s+", " ", html2[m2-200:m2+1500]) if m2 >= 0 else "NOT FOUND"
    page.screenshot(path=str(out / f"upload-probe-{tag}-afterreload.png"))
    ctx.close(); b.close()
rec["console"] = console
rec["ws_frames_with_files"] = [f[:600] for f in frames if '"files"' in f or "files" in f][:12]
(out / f"upload-probe-{tag}.json").write_text(json.dumps(rec, indent=2))
print(json.dumps({k: v for k, v in rec.items() if k != "ws_frames_with_files"}, indent=2)[:4000])
print("WS FRAMES MENTIONING files:", len(rec["ws_frames_with_files"]))
for f in rec["ws_frames_with_files"][:6]:
    print("  ", f[:400])
