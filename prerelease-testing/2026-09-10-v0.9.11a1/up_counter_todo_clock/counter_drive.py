"""Drive the counter example: increment/decrement/randomize/color-mode/reload.

Usage: python counter_drive.py <url> <shot_prefix> <report_json>
"""

import re

from drive_common import run


def driver(page, cap):
    SHOT = cap.shot
    page.goto(cap.url, wait_until="networkidle", timeout=60000)
    heading = page.locator("h1")
    try:
        heading.wait_for(state="visible", timeout=30000)
        page.wait_for_function(
            "document.querySelector('h1') && /^\\d+$/.test(document.querySelector('h1').innerText.trim())",
            timeout=30000,
        )
        initial = heading.inner_text().strip()
        cap.step("initial_render", initial == "0", f"heading={initial!r}")
    except Exception as e:
        cap.step("initial_render", False, repr(e))
    page.screenshot(path=f"{SHOT}-initial.png")

    def wait_count(expected, timeout=10000):
        page.wait_for_function(
            f"document.querySelector('h1').innerText.trim() === '{expected}'",
            timeout=timeout,
        )

    try:
        page.get_by_role("button", name="Increment").click()
        wait_count(1)
        page.get_by_role("button", name="Increment").click()
        wait_count(2)
        cap.step("increment_x2", True, "0 -> 1 -> 2")
    except Exception as e:
        cap.step("increment_x2", False, repr(e))

    try:
        page.get_by_role("button", name="Decrement").click()
        wait_count(1)
        cap.step("decrement", True, "2 -> 1")
    except Exception as e:
        cap.step("decrement", False, repr(e))

    rand_val = None
    try:
        page.get_by_role("button", name="Randomize").click()
        page.wait_for_function(
            "/^\\d+$/.test(document.querySelector('h1').innerText.trim())",
            timeout=10000,
        )
        page.wait_for_timeout(500)
        val = heading.inner_text().strip()
        ok = bool(re.fullmatch(r"\d+", val)) and 0 <= int(val) <= 100
        cap.step("randomize", ok, f"value={val}")
        rand_val = int(val) if ok else None
    except Exception as e:
        cap.step("randomize", False, repr(e))

    if rand_val is not None:
        try:
            page.get_by_role("button", name="Decrement").click()
            wait_count(rand_val - 1)
            cap.step("decrement_after_random", True, f"{rand_val} -> {rand_val - 1}")
        except Exception as e:
            cap.step("decrement_after_random", False, repr(e))

    # rapid clicks: 5 quick increments must all land (event queue ordering)
    try:
        before = int(heading.inner_text().strip())
        btn = page.get_by_role("button", name="Increment")
        for _ in range(5):
            btn.click(delay=10)
        wait_count(before + 5, timeout=15000)
        cap.step("rapid_increment_x5", True, f"{before} -> {before + 5}")
    except Exception as e:
        cap.step("rapid_increment_x5", False, f"heading={heading.inner_text()!r} {e!r}")

    try:
        before = page.evaluate("document.documentElement.className")
        page.locator("button").first.click()  # color-mode icon button (top-right)
        page.wait_for_timeout(800)
        after = page.evaluate("document.documentElement.className")
        cap.step("color_mode_toggle", before != after, f"{before!r} -> {after!r}")
    except Exception as e:
        cap.step("color_mode_toggle", False, repr(e))
    page.screenshot(path=f"{SHOT}-final.png")

    try:
        pre = heading.inner_text().strip()
        page.reload(wait_until="networkidle")
        page.wait_for_function(
            "document.querySelector('h1') && /^-?\\d+$/.test(document.querySelector('h1').innerText.trim())",
            timeout=30000,
        )
        page.wait_for_timeout(1000)
        val = heading.inner_text().strip()
        cap.step("reload_rehydrate", val == pre, f"pre={pre} post={val} (state persists per tab token)")
    except Exception as e:
        cap.step("reload_rehydrate", False, repr(e))
    page.screenshot(path=f"{SHOT}-reload.png")


run(driver)
