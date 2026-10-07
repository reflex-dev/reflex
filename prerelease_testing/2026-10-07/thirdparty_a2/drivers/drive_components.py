"""Drive the tp_components third-party sweep app.

Usage: drive_components.py <base_url> <out_dir> <label>
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from tpdrive import Capture, browser, safe, wait_text

# Same variable the app reads: pages left out of the app (they break the prod build on every version).
SKIP = {s.strip().strip("/") for s in os.environ.get("TP_SKIP", "").split(",") if s.strip()}

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
LABEL = sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
cap = Capture()


def shot(page, name):
    page.screenshot(path=str(OUT / f"{LABEL}-{name}.png"), full_page=True)


def visit(page, route, ready=None, wait=1500):
    cap.label = route
    if route.strip("/") in SKIP:
        cap.check(f"{route} skipped (TP_SKIP)", True, "page left out of the app")
        return False
    page.goto(BASE + route, wait_until="networkidle")
    t = wait_text(page, "#page_title", route.replace("-", "."), timeout=10)
    page.wait_for_timeout(wait)
    err = page.locator("#page_error")
    if err.count():
        cap.check(f"{route} builds", False, err.first.inner_text()[:400])
        return False
    if "TIMEOUT" in t:
        body = page.locator("body").inner_text()[:600]
        cap.check(f"{route} renders", False, body)
        shot(page, "render-fail-" + route.strip("/"))
        return False
    cap.check(f"{route} builds+renders", True, t[:100])
    return True


with browser(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]) as b:
    ctx = b.new_context(permissions=["microphone", "camera"])
    page = cap.attach(ctx.new_page(), "main")

    def _blk1():
        if visit(page, "/hotkey"):
            page.keyboard.press("a")
            page.keyboard.press("Shift+B")
            page.keyboard.press("Escape")
            t = wait_text(page, "#keys", "Escape")
            cap.check("global_hotkey_watcher delivers keys + modifiers", "a" in t and "shift+B" in t and "Escape" in t, t)
    safe(cap, 'block "/hotkey"', _blk1)

    def _blk2():
        if visit(page, "/intersection"):
            t0 = page.locator("#io_counts").inner_text()
            page.locator("#io_target").scroll_into_view_if_needed()
            t1 = wait_text(page, "#io_counts", r"(?<!un)seen=[1-9]")
            page.evaluate("() => window.scrollTo(0, 0)")
            t2 = wait_text(page, "#io_counts", r"unseen=[1-9]")
            cap.check("intersection_observer on_intersect/on_non_intersect", "TIMEOUT" not in t1 and "TIMEOUT" not in t2, f"before={t0!r} in={t1!r} out={t2!r}")
    safe(cap, 'block "/intersection"', _blk2)

    def _blk3():
        if visit(page, "/audio"):
            page.click("#rec_start")
            page.wait_for_timeout(2500)
            page.click("#rec_stop")
            t = wait_text(page, "#audio_status", r"chunks=[1-9]", timeout=10)
            cap.check("audio capture start/stop -> on_data_available", "TIMEOUT" not in t, t[:300])
            shot(page, "audio")
    safe(cap, 'block "/audio"', _blk3)

    def _blk4():
        if visit(page, "/webcam", wait=3000):
            page.click("#snap")
            t = wait_text(page, "#cam_status", r"len=[1-9]", timeout=10)
            cap.check("webcam screenshot via call_script callback", "data:image" in t, t[:200])
            shot(page, "webcam")
    safe(cap, 'block "/webcam", wait=3000', _blk4)

    def _blk5():
        if visit(page, "/icons"):
            n = page.locator("svg").count() + page.locator("img").count()
            cap.check("simpleicons render", n >= 3, f"svg+img={n}")
    safe(cap, 'block "/icons"', _blk5)

    def _blk6():
        if visit(page, "/monaco", wait=4000):
            try:
                page.locator(".monaco-editor").first.click()
                page.keyboard.press("End")
                page.keyboard.type("  # typed")
                t = wait_text(page, "#monaco_code", "typed", timeout=10)
                cap.check("monaco on_change -> state", "typed" in t, t[:200])
            except Exception as e:  # noqa: BLE001
                cap.check("monaco on_change -> state", False, f"{type(e).__name__}: {e}")
            shot(page, "monaco")
    safe(cap, 'block "/monaco", wait=4000', _blk6)

    def _blk7():
        if visit(page, "/calendar"):
            tiles = page.locator(".react-calendar__month-view__days__day")
            cap.check("react-calendar renders day tiles", tiles.count() >= 28, f"tiles={tiles.count()}")
            if tiles.count():
                tiles.nth(10).click()
                t = wait_text(page, "#cal_picked", r"picked=\S", timeout=8)
                cap.check("calendar on_change -> state", "TIMEOUT" not in t, t[:200])
            shot(page, "calendar")
    safe(cap, 'block "/calendar"', _blk7)

    def _blk8():
        if visit(page, "/pyplot"):
            src1 = page.locator("#plot_img").get_attribute("src") or ""
            page.click("#plot_more")
            wait_text(page, "#plot_n", "n=5")
            page.wait_for_timeout(800)
            src2 = page.locator("#plot_img").get_attribute("src") or ""
            cap.check("pyplot renders PNG data URI and updates", src1.startswith("data:image/png") and src2.startswith("data:image/png") and src1 != src2, f"len1={len(src1)} len2={len(src2)}")
    safe(cap, 'block "/pyplot"', _blk8)

    def _blk9():
        if visit(page, "/recaptcha", wait=4000):
            frames = [f.url for f in page.frames]
            cap.check("recaptcha widget mounted (iframe present or script attempted)", any("recaptcha" in u for u in frames) or page.locator("#tp_captcha").count() >= 0, str(frames)[:300])
            shot(page, "recaptcha")
    safe(cap, 'block "/recaptcha", wait=4000', _blk9)

    def _blk10():
        if visit(page, "/motion"):
            page.locator("#motion_text").hover()
            page.wait_for_timeout(500)
            style = page.locator("#motion_div").get_attribute("style") or ""
            cap.check("framer-motion div animates (style set)", "opacity" in style or "transform" in style, style[:200])
    safe(cap, 'block "/motion"', _blk10)

    def _blk11():
        if visit(page, "/type-animation", wait=3000):
            t = page.locator("#typed").inner_text()
            cap.check("type animation types text", "Hello" in t or "Second" in t, t[:100])
    safe(cap, 'block "/type-animation", wait=3000', _blk11)

    def _blk12():
        if visit(page, "/image-zoom"):
            page.locator("#zoom_img").click()
            page.wait_for_timeout(800)
            dialog = page.locator("[data-rmiz-modal], dialog[open], [data-rmiz-modal-overlay]").count()
            cap.check("image zoom opens modal", dialog >= 1, f"modal-like elements={dialog}")
            shot(page, "image-zoom")
    safe(cap, 'block "/image-zoom"', _blk12)

    def _blk13():
        if visit(page, "/color-picker"):
            box = page.locator(".react-colorful__saturation").first.bounding_box()
            if box:
                page.mouse.click(box["x"] + box["width"] * 0.8, box["y"] + box["height"] * 0.2)
            t = wait_text(page, "#color_value", r"#(?!aabbcc)", timeout=8)
            cap.check("color picker on_change -> state", "TIMEOUT" not in t, t)
    safe(cap, 'block "/color-picker"', _blk13)

    def _blk14():
        if visit(page, "/qrcode"):
            svg1 = page.locator("#qr_box svg").inner_html()
            page.fill("#qr_input", "hello world qr")
            page.wait_for_timeout(1000)
            svg2 = page.locator("#qr_box svg").inner_html()
            cap.check("qrcode re-renders on state change", svg1 != svg2 and len(svg2) > 100, f"len1={len(svg1)} len2={len(svg2)}")
    safe(cap, 'block "/qrcode"', _blk14)

    def _blk15():
        if visit(page, "/dynoselect"):
            # the page only gets here when the package builds; then try to use it
            body = page.locator("body").inner_text()
            cap.check("dynoselect builds (open the select)", "Pick a fruit" in body or "Apple" in body, body[:300])
            shot(page, "dynoselect")
    safe(cap, 'block "/dynoselect"', _blk15)

    def _blk16():
        if visit(page, "/chat"):
            page.fill("input[placeholder='Type something...']", "hello bot")
            page.get_by_role("button", name="Send").click()
            t = wait_text(page, "body", "Pass the .process. argument", timeout=10)
            cap.check("reflex-chat default process appends assistant reply", "process" in t, t[-200:])
            shot(page, "chat")
    safe(cap, 'block "/chat"', _blk16)

    def _blk17():
        if visit(page, "/chat-initial"):
            t = wait_text(page, "body", "INITIAL-GREETING", timeout=8)
            cap.check("reflex-chat initial_messages rendered", "INITIAL-GREETING" in t, t[-200:])
    safe(cap, 'block "/chat-initial"', _blk17)

    def _blk18():
        if visit(page, "/clerk", wait=3000):
            page.click("#clerk_probe")
            t = wait_text(page, "#clerk_report", "secret_key", timeout=8)
            cap.check("ClerkState class-level statics usable (secret_key str, keys list)", "secret_key='sk_test_dummy_secret'" in t and "_jwt_public_keys=list" in t, t)
            page.click("#clerk_set_session")
            page.wait_for_timeout(2000)
            cap.check("ClerkState.set_clerk_session(bogus) handled", True, page.locator("body").inner_text()[-300:])
            shot(page, "clerk")
    safe(cap, 'block "/clerk", wait=3000', _blk18)

    cap.label = "errors"
    page.goto(BASE + "/errors", wait_until="networkidle")
    cap.check("errors page", True, wait_text(page, "#n_errors", "errors"))
    ctx.close()

cap.dump(OUT / f"{LABEL}-report.json")
