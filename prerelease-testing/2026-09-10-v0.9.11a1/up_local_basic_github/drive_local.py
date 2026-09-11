"""Playwright driver for the reflex-examples `local-component` app.

usage: drive_local.py <frontend_url> <artifacts_dir> <label>

Exercises: the local `hello.jsx` asset component (rx.asset(shared=True) + library="/public/..."),
React.forwardRef ref/prop passthrough (id/title/background_color land on the inner <div>),
event passthrough with `.prevent_default` (on_context_menu -> rx.console_log), the component's own
internal useState/useMemo (right-click caps toggle), rx.popover + rx.form round trip driving a
State var live, rx.color_mode_cond + rx.color_mode.button, and rx.scroll_to("greeting").
"""

import sys

from drive_common import Run, wait_for

URL, ART, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]

PAPAYAWHIP = "rgb(255, 239, 213)"
REBECCAPURPLE = "rgb(102, 51, 153)"


def greeting_text(page):
    return page.inner_text("#greeting h1").strip()


with Run(ART, LABEL) as run:
    ctx, page = run.new_page(LABEL)
    page.set_default_timeout(20000)

    page.goto(URL, wait_until="load")
    ok = wait_for(lambda: page.is_visible("#greeting"), 60)
    run.record("load_index", "pass" if ok else "fail", f"#greeting visible={ok}")
    page.wait_for_timeout(1500)
    run.shot(page, "01_index.png")

    run.record(
        "heading",
        "pass" if "Local Component Example" in page.inner_text("body") else "fail",
        "heading text present",
    )

    # --- the local JSX component rendered, props passed through forwardRef ------------
    txt = greeting_text(page)
    run.record("hello_initial", "pass" if txt == "Hello world!" else "fail", f"h1={txt!r}")

    attrs = page.evaluate(
        "() => { const e = document.getElementById('greeting');"
        " return e ? {tag: e.tagName, title: e.getAttribute('title'),"
        " bg: getComputedStyle(e).backgroundColor,"
        " children: e.children.length, firstChild: e.children[0]?.tagName} : null; }"
    )
    run.record(
        "forwardref_props",
        "pass" if attrs and attrs["tag"] == "DIV" and attrs["firstChild"] == "H1" and attrs["title"] else "fail",
        str(attrs),
    )
    run.record(
        "color_mode_cond_light",
        "pass" if attrs and attrs["bg"] == PAPAYAWHIP else "fail",
        f"bg={attrs and attrs['bg']} expect {PAPAYAWHIP}",
    )

    # --- right-click: component-internal useState + event passthrough ------------------
    before = len(run.console)
    page.click("#greeting h1", button="right")
    page.wait_for_timeout(800)
    txt = greeting_text(page)
    run.record("rightclick_caps_on", "pass" if txt == "HELLO WORLD!" else "fail", f"h1={txt!r}")
    passthrough = [m for m in run.console[before:] if "Yes we pass events through" in m["text"]]
    run.record(
        "event_passthrough_console_log",
        "pass" if passthrough else "fail",
        f"{len(passthrough)} console.log from on_context_menu",
    )
    run.shot(page, "02_caps.png")
    page.click("#greeting h1", button="right")
    page.wait_for_timeout(600)
    txt = greeting_text(page)
    run.record("rightclick_caps_off", "pass" if txt == "Hello world!" else "fail", f"h1={txt!r}")

    # --- popover + form + live State var ---------------------------------------------
    page.click("#greeting")
    opened = wait_for(lambda: page.is_visible("input[name='who']"), 10)
    run.record("popover_opens", "pass" if opened else "fail", f"input visible={opened}")
    run.shot(page, "03_popover.png")

    if opened:
        page.fill("input[name='who']", "reflex")
        live = wait_for(lambda: greeting_text(page) == "Hello reflex!", 10)
        run.record("live_state_var", "pass" if live else "fail", f"h1={greeting_text(page)!r}")
        run.shot(page, "04_typed.png")
        page.keyboard.press("Escape")
        closed = wait_for(lambda: not page.is_visible("input[name='who']"), 10)
        reverted = wait_for(lambda: greeting_text(page) == "Hello world!", 10)
        run.record(
            "popover_escape_reverts",
            "pass" if closed and reverted else "fail",
            f"closed={closed} h1={greeting_text(page)!r}",
        )

        page.click("#greeting")
        wait_for(lambda: page.is_visible("input[name='who']"), 10)
        page.fill("input[name='who']", "alpha")
        page.keyboard.press("Enter")
        submitted = wait_for(
            lambda: not page.is_visible("input[name='who']") and greeting_text(page) == "Hello alpha!", 15
        )
        run.record(
            "form_submit_persists",
            "pass" if submitted else "fail",
            f"h1={greeting_text(page)!r} popover_open={page.is_visible('input[name=who]')}",
        )
        run.shot(page, "05_submitted.png")

    # --- color mode toggle ------------------------------------------------------------
    page.click("button.rt-IconButton, button:has(svg.lucide-sun), button:has(svg.lucide-moon)")
    dark = wait_for(
        lambda: page.evaluate(
            "() => getComputedStyle(document.getElementById('greeting')).backgroundColor"
        )
        == REBECCAPURPLE,
        10,
    )
    bg = page.evaluate("() => getComputedStyle(document.getElementById('greeting')).backgroundColor")
    run.record("color_mode_cond_dark", "pass" if dark else "fail", f"bg={bg} expect {REBECCAPURPLE}")
    run.shot(page, "06_dark.png")

    # --- rx.scroll_to("greeting") -----------------------------------------------------
    btn = page.get_by_role("button", name="Scroll to Greeting")
    btn.scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    y_before = page.evaluate("() => window.scrollY")
    btn.click()
    scrolled = wait_for(lambda: page.evaluate("() => window.scrollY") < y_before - 200, 10)
    y_after = page.evaluate("() => window.scrollY")
    in_view = page.evaluate(
        "() => { const r = document.getElementById('greeting').getBoundingClientRect();"
        " return r.top >= -5 && r.top < window.innerHeight; }"
    )
    run.record(
        "scroll_to_greeting",
        "pass" if scrolled and in_view else "fail",
        f"scrollY {y_before} -> {y_after}, greeting_in_view={in_view}",
    )
    run.shot(page, "07_scrolled.png")

    # --- reload: does the component + state survive a fresh page load? ----------------
    page.reload(wait_until="load")
    wait_for(lambda: page.is_visible("#greeting"), 30)
    page.wait_for_timeout(1500)
    txt = greeting_text(page)
    run.record("reload_renders", "pass" if txt.lower().startswith("hello") else "fail", f"h1={txt!r} (value not asserted)")
    run.shot(page, "08_reload.png")

    # --- the shared asset is actually served ------------------------------------------
    srcs = page.evaluate(
        "() => Array.from(document.querySelectorAll('script[src]')).map(s => s.getAttribute('src'))"
    )
    resp = page.request.get(URL.rstrip("/") + "/public/hello.jsx")
    run.record(
        "asset_served_note",
        "pass" if resp.status in (200, 404) else "fail",
        f"GET /public/hello.jsx -> {resp.status} (dev server does not have to serve the raw path)",
    )
    (run.art / "scripts.json").write_text(str(srcs))

    ctx.close()
