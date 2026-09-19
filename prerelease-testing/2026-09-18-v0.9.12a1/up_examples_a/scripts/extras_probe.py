"""Drive /extras on the counter app and record the websocket deltas.

usage: extras_probe.py <base_url> <tag> <outdir>
"""
import json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

base, tag, outdir = sys.argv[1:4]
out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
console, errs, bad, frames = [], [], [], []
rec = {"tag": tag}

BENIGN = [r"Hey developer", r"\[vite\] (connecting|connected)", r"Download the React DevTools",
          r"Disconnect websocket"]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1280, "height": 1000})
    page = ctx.new_page()
    page.on("console", lambda m: console.append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.on("websocket", lambda ws: ws.on("framereceived",
            lambda pl: frames.append(pl if isinstance(pl, str) else str(pl))))

    page.goto(base + "extras", timeout=90000)
    page.wait_for_selector("#bump", timeout=60000)
    page.wait_for_timeout(1500)

    def txt(sel):
        try:
            return page.locator(sel).inner_text().strip()
        except Exception as e:
            return f"<ERR {e}>"

    rec["initial"] = {k: txt("#" + k) for k in
                      ["clicks", "bucket-uncached", "bucket-cached", "clicks-uncached",
                       "counter-count", "bg-ticks", "legacy-path", "raw-path", "cs-value"]}
    # 7 bumps: uncached bucket changes at 3 and 6 only
    marks = []
    for i in range(7):
        n0 = len(frames)
        page.click("#bump")
        page.wait_for_timeout(450)
        marks.append({"i": i + 1,
                      "clicks": txt("#clicks"),
                      "bucket_uncached": txt("#bucket-uncached"),
                      "bucket_cached": txt("#bucket-cached"),
                      "frames": [f for f in frames[n0:] if "delta" in f]})
    rec["bump_marks"] = [{**m, "frames": [f[:900] for f in m["frames"]]} for m in marks]
    rec["after_bumps"] = {k: txt("#" + k) for k in ["clicks", "bucket-uncached", "bucket-cached", "clicks-uncached"]}
    rec["cond_many"] = page.locator("#many").count()
    page.screenshot(path=str(out / f"extras-{tag}-bumped.png"))

    # client state
    page.click("#cs-set"); page.wait_for_timeout(500)
    rec["cs_after_set"] = txt("#cs-value")

    # ComponentState toggles are independent
    page.click("#toggle-a"); page.wait_for_timeout(500)
    rec["toggle_a"] = txt("#togglestate-a"); rec["toggle_b"] = txt("#togglestate-b")

    # event chain -> other state handler + background task
    page.click("#chain"); page.wait_for_timeout(2500)
    rec["counter_after_chain"] = txt("#counter-count")
    rec["bg_after_chain"] = txt("#bg-ticks")
    rec["log_entries"] = page.locator(".logentry").all_inner_texts()

    # memoized rx.upload (#7176): provider must reach the app root
    f = out / f"memo-{tag}.txt"; f.write_text("memo upload payload\n")
    page.set_input_files("#memo_upload input[type=file]", [str(f)])
    page.wait_for_timeout(500)
    page.click("#memo-upload-btn")
    page.wait_for_timeout(2500)
    rec["log_after_memo_upload"] = page.locator(".logentry").all_inner_texts()
    page.screenshot(path=str(out / f"extras-{tag}-memoupload.png"))

    # client-side navigation to / and back
    page.click("#home-link"); page.wait_for_timeout(1500)
    rec["home_heading"] = page.locator("h1,h2,h3").first.inner_text().strip()
    page.go_back(); page.wait_for_timeout(1800)
    rec["clicks_after_nav_back"] = txt("#clicks")
    rec["cs_after_nav_back"] = txt("#cs-value")
    rec["raw_path_after_nav_back"] = txt("#raw-path")
    page.screenshot(path=str(out / f"extras-{tag}-navback.png"))

    # direct load of /extras (SSR path)
    page.goto(base + "extras", timeout=60000)
    page.wait_for_selector("#bump", timeout=60000); page.wait_for_timeout(1500)
    rec["clicks_after_direct_load"] = txt("#clicks")
    rec["raw_path_direct"] = txt("#raw-path")
    ctx.close(); b.close()

rec["console_notable"] = [c for c in console if not any(re.search(p, c) for p in BENIGN)]
rec["page_errors"] = errs
rec["bad_responses"] = bad
(out / f"extras-{tag}.json").write_text(json.dumps(rec, indent=2))
printable = {k: v for k, v in rec.items() if k != "bump_marks"}
print(json.dumps(printable, indent=2)[:5000])
print("=== bump deltas ===")
for m in rec["bump_marks"]:
    for fr in m["frames"]:
        i = fr.find("delta")
        print(f"  bump {m['i']} clicks={m['clicks']} bkt={m['bucket_uncached']} :: {fr[i:i+450]}")
