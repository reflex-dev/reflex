"""Drive the todo example: add items (button/Enter), empty submit, special chars, finish, reload.

Usage: python todo_drive.py <url> <shot_prefix> <report_json>
"""

from drive_common import run


def driver(page, cap):
    SHOT = cap.shot

    def items():
        return page.locator("ol li").evaluate_all(
            "els => els.map(e => e.querySelector('span') ? e.querySelector('span').innerText.trim() : e.innerText.trim())"
        )

    def wait_items(expected, timeout=10000):
        page.wait_for_function(
            "exp => JSON.stringify(Array.from(document.querySelectorAll('ol li')).map("
            "e => (e.querySelector('span')||e).innerText.trim())) === JSON.stringify(exp)",
            arg=expected,
            timeout=timeout,
        )

    page.goto(cap.url, wait_until="networkidle", timeout=60000)
    initial_expected = ["Write Code", "Sleep", "Have Fun"]
    try:
        wait_items(initial_expected, timeout=30000)
        cap.step("initial_render", True, f"items={items()}")
    except Exception as e:
        cap.step("initial_render", False, f"items={items()} err={e!r}")
    page.screenshot(path=f"{SHOT}-initial.png")

    inp = page.get_by_placeholder("Add a todo...")

    try:
        inp.fill("Buy milk")
        page.get_by_role("button", name="Add").click()
        wait_items([*initial_expected, "Buy milk"])
        input_val = inp.input_value()
        cap.step("add_item_button", input_val == "", f"items={items()} input_after={input_val!r} (reset_on_submit)")
    except Exception as e:
        cap.step("add_item_button", False, f"items={items()} err={e!r}")

    try:
        inp.fill("Walk dog")
        inp.press("Enter")
        wait_items([*initial_expected, "Buy milk", "Walk dog"])
        cap.step("add_item_enter", True, f"items={items()}")
    except Exception as e:
        cap.step("add_item_enter", False, f"items={items()} err={e!r}")

    try:
        before = items()
        page.get_by_role("button", name="Add").click()
        page.wait_for_timeout(1500)
        after = items()
        cap.step("empty_submit_noop", before == after, f"before={before} after={after}")
    except Exception as e:
        cap.step("empty_submit_noop", False, repr(e))

    special = "Café <b>&amp;</b> 50%"
    try:
        inp.fill(special)
        inp.press("Enter")
        wait_items([*initial_expected, "Buy milk", "Walk dog", special])
        cap.step("add_item_special_chars", True, f"items={items()}")
    except Exception as e:
        cap.step("add_item_special_chars", False, f"items={items()} err={e!r}")
    page.screenshot(path=f"{SHOT}-added.png")

    try:
        page.locator("ol li", has_text="Sleep").locator("button").click()
        wait_items(["Write Code", "Have Fun", "Buy milk", "Walk dog", special])
        cap.step("finish_middle_item", True, f"items={items()}")
    except Exception as e:
        cap.step("finish_middle_item", False, f"items={items()} err={e!r}")

    try:
        page.locator("ol li", has_text="Write Code").locator("button").click()
        wait_items(["Have Fun", "Buy milk", "Walk dog", special])
        cap.step("finish_first_item", True, f"items={items()}")
    except Exception as e:
        cap.step("finish_first_item", False, f"items={items()} err={e!r}")
    page.screenshot(path=f"{SHOT}-after-finish.png")

    # check icons rendered inside the finish buttons (lucide 'check')
    try:
        n_btn = page.locator("ol li button").count()
        n_svg = page.locator("ol li button svg").count()
        cap.step("finish_buttons_have_icons", n_btn == n_svg and n_btn > 0, f"buttons={n_btn} svgs={n_svg}")
    except Exception as e:
        cap.step("finish_buttons_have_icons", False, repr(e))

    try:
        pre = items()
        page.reload(wait_until="networkidle")
        page.wait_for_function("document.querySelectorAll('ol li').length > 0", timeout=30000)
        page.wait_for_timeout(1000)
        post = items()
        cap.step("reload_state", pre == post, f"pre={pre} post={post} persisted={pre == post}")
    except Exception as e:
        cap.step("reload_state", False, repr(e))
    page.screenshot(path=f"{SHOT}-reload.png")


run(driver)
