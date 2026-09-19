"""Playwright driver for the reflex-enterprise dnd demo.

Usage: python drive_dnd.py <base_url> <out_dir> <label>

Exercises: index page, /basic and /foreach (real HTML5 drag-and-drop of the
card between drop targets via mouse down/move/up, is_over highlight check,
on_drop toast + state update), /kanban (create columns/items via forms, drag
item between columns, drag column reorder, localStorage persistence).
Prints a RESULT line per check.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import Harness

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)


def bgcolor(loc):
    return loc.evaluate("el => getComputedStyle(el).backgroundColor")


def drag(page, src_loc, dst_loc, h=None, shotname=None, steps=15, expect_bg=None):
    """Real mouse-down/move/up HTML5 drag from src to dst center.

    While holding over the target, polls its background-color for up to 2.5s
    (react-dnd is_over highlight); returns the last observed value.
    """
    sb = src_loc.bounding_box()
    db = dst_loc.bounding_box()
    sx, sy = sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] / 2
    dx, dy = db["x"] + db["width"] / 2, db["y"] + db["height"] / 2
    page.mouse.move(sx, sy)
    page.mouse.down()
    # small initial move to trigger dragstart
    page.mouse.move(sx + 8, sy + 8, steps=3)
    page.mouse.move(dx, dy, steps=steps)
    page.mouse.move(dx + 2, dy + 2, steps=2)  # extra move so react-dnd registers hover
    over_bg = bgcolor(dst_loc)
    deadline = time.time() + 2.5
    while expect_bg is not None and over_bg != expect_bg and time.time() < deadline:
        time.sleep(0.2)
        page.mouse.move(dx - 2, dy - 2, steps=2)
        over_bg = bgcolor(dst_loc)
    if h and shotname:
        h.shot(shotname)
    page.mouse.up()
    time.sleep(0.6)
    return over_bg


def basic_like_page(h, page, route, label, toast_pos=2):
    h.goto(route)
    page.wait_for_selector(".rt-Grid", timeout=20000)
    time.sleep(1.5)
    targets = page.locator(".rt-Grid > div")
    n = targets.count()
    card = page.locator('[draggable="true"]')
    check(f"{label}_renders", n == 4 and card.count() == 1, f"targets={n} draggables={card.count()}")
    h.shot(f"{label}_initial")
    if n != 4 or card.count() != 1:
        return

    bg_before = bgcolor(targets.nth(toast_pos))
    over_bg = drag(
        page,
        card.first,
        targets.nth(toast_pos),
        h,
        f"{label}_mid_drag",
        expect_bg="rgb(0, 128, 0)",
    )
    check(
        f"{label}_is_over_highlight",
        over_bg != bg_before and "0, 128, 0" in over_bg,
        f"before={bg_before} during={over_bg}",
    )
    # toast
    try:
        page.wait_for_selector(f"text=Dropped in position {toast_pos}", timeout=6000)
        toast_ok = True
    except Exception:
        toast_ok = False
    check(f"{label}_drop_toast", toast_ok)
    # card moved into the target cell
    time.sleep(1)
    moved = targets.nth(toast_pos).locator('[draggable="true"]').count() == 1
    check(f"{label}_card_moved", moved)
    h.shot(f"{label}_after_drop")

    # drag it back to position 0
    card = page.locator('[draggable="true"]')
    drag(page, card.first, targets.nth(0))
    time.sleep(1)
    back = targets.nth(0).locator('[draggable="true"]').count() == 1
    check(f"{label}_drag_back", back)
    h.shot(f"{label}_after_drag_back")


def kanban(h, page):
    h.goto("/kanban")
    page.wait_for_selector('input[placeholder="New Column"]', timeout=20000)
    time.sleep(1.5)
    h.shot("kanban_empty")

    # create two columns
    for name in ("Todo", "Done"):
        page.locator('input[placeholder="New Column"]').fill(name)
        page.locator('input[placeholder="New Column"]').press("Enter")
        time.sleep(1.2)
    cols_ok = (
        page.locator("h1,h2,h3,h4,h5,h6", has_text="Todo").count() >= 1
        and page.locator("h1,h2,h3,h4,h5,h6", has_text="Done").count() >= 1
    )
    check("kanban_create_columns", cols_ok)
    h.shot("kanban_two_columns")
    if not cols_ok:
        return

    # add two items to Todo (first column card's New Item form)
    item_inputs = page.locator('input[placeholder="New Item"]')
    check("kanban_item_forms", item_inputs.count() == 2, f"count={item_inputs.count()}")
    for title in ("Task A", "Task B"):
        item_inputs.nth(0).fill(title)
        item_inputs.nth(0).press("Enter")
        time.sleep(1.2)
    # leaf draggables only: the whole column is itself wrapped in a draggable
    leaf = '[draggable="true"]:not(:has([draggable="true"]))'
    a = page.locator(leaf, has_text="Task A")
    b = page.locator(leaf, has_text="Task B")
    check("kanban_create_items", a.count() == 1 and b.count() == 1, f"A={a.count()} B={b.count()}")
    h.shot("kanban_items_added")

    # drag Task A into the Done column (drop on its heading drop target)
    done_heading = page.locator("h1,h2,h3,h4,h5,h6", has_text="Done").first
    drag(page, a.first, done_heading, h, "kanban_mid_item_drag", steps=25)
    time.sleep(1.5)
    h.shot("kanban_after_item_drag")
    # verify Task A now lives in the Done column card
    done_col_card = page.locator(".rt-Card", has=page.locator("h1,h2,h3,h4,h5,h6", has_text="Done")).first
    moved = done_col_card.locator(leaf, has_text="Task A").count() >= 1
    check("kanban_item_moved_to_done", moved)
    # on_end toast
    toast = page.locator("text=/You dropped/").count() > 0
    check("kanban_on_end_toast", toast)

    # drag the Done column before Todo. Grab the Done *heading* (inside the
    # column draggable but not inside any item draggable) so we don't pick up
    # an item card, and drop onto the Todo heading (bubbles to the enclosing
    # column_drop_target with replace_position=0).
    done_drag_handle = page.locator("h1,h2,h3,h4,h5,h6", has_text="Done").first
    todo_heading = page.locator("h1,h2,h3,h4,h5,h6", has_text="Todo").first
    if done_drag_handle.count():
        drag(page, done_drag_handle, todo_heading, h, "kanban_mid_col_drag", steps=25)
        time.sleep(1.5)
        h.shot("kanban_after_col_drag")
        headings = page.locator(".rt-Card h1, .rt-Card h2, .rt-Card h3, .rt-Card h4, .rt-Card h5").all_inner_texts()
        texts = [t for t in headings if t in ("Todo", "Done")]
        check("kanban_column_reorder", texts[:2] == ["Done", "Todo"], f"order={texts}")
    else:
        check("kanban_column_reorder", False, "no draggable column handle found")

    # persistence: reload, on_load should restore from localStorage
    page.reload()
    time.sleep(3)
    persisted = (
        page.locator("h1,h2,h3,h4,h5,h6", has_text="Done").count() >= 1
        and page.locator("text=Task A").count() >= 1
    )
    check("kanban_localstorage_persist", persisted)
    h.shot("kanban_after_reload")


def main():
    base_url, out_dir, label = sys.argv[1], sys.argv[2], sys.argv[3]
    with Harness(base_url, out_dir, label) as h:
        page = h.page

        h.goto("/")
        try:
            page.wait_for_selector('a[href="/basic"]', timeout=20000)
            check("index_renders_cards", True)
        except Exception as e:
            check("index_renders_cards", False, repr(e))
        h.shot("index")

        try:
            basic_like_page(h, page, "/basic", "basic")
        except Exception as e:
            check("basic_page", False, repr(e))
            h.shot("basic_error")

        try:
            basic_like_page(h, page, "/foreach", "foreach")
        except Exception as e:
            check("foreach_page", False, repr(e))
            h.shot("foreach_error")

        try:
            kanban(h, page)
        except Exception as e:
            check("kanban_page", False, repr(e))
            h.shot("kanban_error")

        unexpected = h.unexpected_console()
        print(f"UNEXPECTED_CONSOLE {len(unexpected)}", flush=True)
        for c in unexpected[:20]:
            print("  CONSOLE", c["type"], c["text"][:300], flush=True)
        print(f"NET_FAIL {len(h.net_fail)}", flush=True)
        for nf in h.net_fail[:20]:
            print("  NET", nf, flush=True)
        print(f"PAGE_ERRORS {len(h.page_errors)}", flush=True)
        for e in h.page_errors[:10]:
            print("  PAGEERROR", e[:300], flush=True)

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"SUMMARY {len(results) - n_fail}/{len(results)} passed", flush=True)
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
