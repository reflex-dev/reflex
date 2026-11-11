"""Drive the enterprise dnd demo (react-dnd HTML5 backend) with real pointer drags.

Usage: drive_dnd.py <base_url> <out_dir> <expected_venv> <label>
Pages: / (index cards), /basic, /foreach, /kanban (LocalStorage persistence, column + item drags).
"""
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
info = assert_driver_and_server(venv)


def pointer_drag(p, src, dst, steps=15, hover_ms=300, probe=None):
    """Drag src locator to dst locator with real mouse events; optionally evaluate `probe` mid-hover."""
    sb, db = src.bounding_box(), dst.bounding_box()
    p.mouse.move(sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] / 2)
    p.mouse.down()
    p.mouse.move(sb["x"] + sb["width"] / 2 + 5, sb["y"] + sb["height"] / 2 + 5, steps=3)
    p.mouse.move(db["x"] + db["width"] / 2, db["y"] + db["height"] / 2, steps=steps)
    # jiggle inside the target so the HTML5 backend gets several dragover events
    for dx in (4, -4, 2):
        p.wait_for_timeout(120)
        p.mouse.move(db["x"] + db["width"] / 2 + dx, db["y"] + db["height"] / 2 + dx)
    p.wait_for_timeout(hover_ms)
    mid = p.evaluate(probe) if probe else None
    p.mouse.up()
    return mid


def toasts(p):
    return p.locator("[data-sonner-toast]").all_inner_texts()


def targets_state(p):
    return p.evaluate("""() => [...document.querySelectorAll('[role=tabpanel] .rt-Grid > div')].map(d => ({
        has_card: !!d.querySelector('[draggable=true]'), bg: getComputedStyle(d).backgroundColor}))""")


def grid_page(s, p, route, name):
    p.goto(base + route, wait_until="networkidle")
    p.wait_for_timeout(1500)
    st = targets_state(p)
    s.check(f"{name}: 4 drop targets, card in target 0, blue backgrounds", len(st) == 4 and st[0]["has_card"] and all(t["bg"] == "rgb(0, 0, 255)" for t in st), st)
    card = p.locator("[role=tabpanel] [draggable=true]").first
    tgt = p.locator("[role=tabpanel] .rt-Grid > div").nth(2)
    mid = pointer_drag(p, card, tgt, probe="""() => [...document.querySelectorAll('[role=tabpanel] .rt-Grid > div')].map(d => getComputedStyle(d).backgroundColor)""")
    s.check(f"{name}: hovered target turns green while dragging (collected_params.is_over)", mid and mid[2] == "rgb(0, 128, 0)" and mid[0] == "rgb(0, 0, 255)", mid)
    p.wait_for_timeout(1200)
    st = targets_state(p)
    s.check(f"{name}: drop moves card to target 2 (State.card_pos)", [t["has_card"] for t in st] == [False, False, True, False], st)
    s.check(f"{name}: on_drop toast 'Dropped in position 2'", any("Dropped in position 2" in t for t in toasts(p)), toasts(p))
    s.shot(p, f"{name}-after-drop")
    # drag onto a target that has nothing, then back to 0 via keyboard-less pointer again
    pointer_drag(p, p.locator("[role=tabpanel] [draggable=true]").first, p.locator("[role=tabpanel] .rt-Grid > div").nth(3))
    p.wait_for_timeout(1000)
    s.check(f"{name}: second drag to target 3", [t["has_card"] for t in targets_state(p)] == [False, False, False, True], targets_state(p))
    # drop outside any target: card must stay
    card = p.locator("[role=tabpanel] [draggable=true]").first
    pointer_drag(p, card, p.locator("h1").first)
    p.wait_for_timeout(800)
    s.check(f"{name}: drop outside a target leaves the card in place", [t["has_card"] for t in targets_state(p)] == [False, False, False, True], targets_state(p))
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(1500)
    s.check(f"{name}: card position survives reload (same tab state)", [t["has_card"] for t in targets_state(p)] == [False, False, False, True], targets_state(p))


def kanban(s, ctx, p):
    p.goto(base + "/kanban", wait_until="networkidle")
    p.wait_for_timeout(2000)
    ls0 = p.evaluate("() => Object.fromEntries(Object.entries(localStorage))")
    s.note(f"kanban localStorage after first load: {json.dumps(ls0)[:400]}")
    s.check("kanban: first load does not write the LocalStorage default (F-002 class)", not any("kanban_data_json" in k for k in ls0), ls0)

    def add_column(name):
        inp = p.locator("input[placeholder='New Column']")
        inp.fill(name)
        inp.press("Enter")
        p.wait_for_timeout(700)

    def add_item(col_idx, name):
        inp = p.locator("input[placeholder='New Item']").nth(col_idx)
        inp.click()
        inp.fill(name)
        inp.press("Enter")
        p.wait_for_timeout(700)

    def board():
        return p.evaluate("""() => [...document.querySelectorAll('.rt-Card h1, .rt-Card .rt-Heading')].filter(h => h.closest('[draggable=true]')).map(h => {
            const card = h.closest('.rt-Card');
            return {col: h.innerText, items: [...card.querySelectorAll('.rt-Card .rt-Card')].map(c => c.querySelector('p')?.innerText)};
        })""")

    add_column("Todo")
    add_column("Done")
    s.check("kanban: two columns created via form", [c["col"] for c in board()] == ["Todo", "Done"], board())
    add_item(0, "Alpha")
    add_item(0, "Beta")
    add_item(1, "Gamma")
    b = board()
    s.check("kanban: items added to columns", b and b[0]["items"] == ["Alpha", "Beta"] and b[1]["items"] == ["Gamma"], b)
    ls1 = p.evaluate("() => Object.entries(localStorage).filter(([k]) => k.includes('kanban_data_json')).map(([k, v]) => v)")
    s.check("kanban: on_save wrote kanban_data_json to localStorage", bool(ls1) and "Alpha" in ls1[0], [x[:200] for x in ls1])
    s.shot(p, "kanban-before-drag")
    # item drag: Alpha -> Done column (drop on the Done heading drop target)
    alpha = p.locator("[draggable=true] [draggable=true]:has-text('Alpha')").first
    done_head = p.locator(".rt-Heading:text-is('Done')").first
    mid = pointer_drag(p, alpha, done_head, probe="() => document.body.innerText.includes('Alpha')")
    p.wait_for_timeout(1200)
    b = board()
    s.check("kanban: drag item Alpha onto Done column header moves it to Done (position 0)", b and b[0]["items"] == ["Beta"] and b[1]["items"][:1] == ["Alpha"], b)
    s.check("kanban: draggable on_end toast 'You dropped <id>'", any("You dropped" in t for t in toasts(p)), toasts(p))
    # reorder within a column: Beta (Todo) -> after Gamma in Done is a cross-column; do same-column reorder in Done: Gamma above Alpha
    gamma = p.locator("[draggable=true] [draggable=true]:has-text('Gamma')").first
    pointer_drag(p, gamma, p.locator(".rt-Heading:text-is('Done')").first)
    p.wait_for_timeout(1200)
    b = board()
    s.check("kanban: same-column reorder (Gamma to top of Done)", b and b[1]["items"][:2] == ["Gamma", "Alpha"], b)
    # column drag: Done -> before Todo
    done_col = p.locator("[draggable=true]:has(.rt-Heading:text-is('Done'))").first
    todo_col = p.locator("[draggable=true]:has(.rt-Heading:text-is('Todo'))").first
    tb = todo_col.bounding_box()
    db = done_col.bounding_box()
    p.mouse.move(db["x"] + db["width"] / 2, db["y"] + 10)
    p.mouse.down()
    p.mouse.move(db["x"] + db["width"] / 2 - 5, db["y"] + 15, steps=3)
    p.mouse.move(tb["x"] + 20, tb["y"] + tb["height"] / 2, steps=20)
    p.wait_for_timeout(400)
    p.mouse.up()
    p.wait_for_timeout(1200)
    b = board()
    s.check("kanban: dragging column Done onto Todo reorders columns", [c["col"] for c in b] == ["Done", "Todo"], b)
    s.shot(p, "kanban-after-drags")
    before = board()
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(2000)
    after = board()
    s.check("kanban: board restored from LocalStorage after reload (on_load)", after == before, {"before": before, "after": after})
    # a second tab in the same context shares localStorage -> same board
    p2 = s.new_page(ctx, "kanban-tab2")
    p2.goto(base + "/kanban", wait_until="networkidle")
    p2.wait_for_timeout(2000)
    b2 = p2.evaluate("""() => [...document.querySelectorAll('.rt-Card .rt-Heading')].filter(h => h.closest('[draggable=true]')).map(h => h.innerText)""")
    s.check("kanban: second tab loads the same board from LocalStorage", b2 == [c["col"] for c in before], b2)
    s.shot(p2, "kanban-tab2")
    p2.close()


with Session(f"dnd-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    ctx = s.new_context("dnd")
    p = s.new_page(ctx, "dnd")
    p.goto(base + "/", wait_until="networkidle")
    p.wait_for_timeout(1500)
    links = p.locator("[role=tabpanel] a").all_inner_texts()
    s.check("index lists the 3 demo pages", len(links) == 3, links)
    for route, name in (("/basic", "basic"), ("/foreach", "foreach")):
        try:
            grid_page(s, p, route, name)
        except Exception:
            s.check(f"{name}: scenario completed", False, traceback.format_exc()[-600:])
    # second tab (new context = new session token): basic card back at 0
    try:
        ctx2 = s.new_context("dnd-tab2")
        q = s.new_page(ctx2, "dnd-tab2")
        q.goto(base + "/basic", wait_until="networkidle")
        q.wait_for_timeout(1500)
        s.check("basic: a new browser context starts with card at target 0", [t["has_card"] for t in targets_state(q)] == [True, False, False, False], targets_state(q))
        # navigation through the demo dropdown
        q.click("button[role=combobox]")
        q.click("[role=option]:has-text('Kanban')")
        q.wait_for_url("**/kanban**", timeout=10000)
        s.check("demo dropdown navigates to /kanban", "/kanban" in q.url, q.url)
    except Exception:
        s.check("second context scenario completed", False, traceback.format_exc()[-600:])
    try:
        kanban(s, ctx, p)
    except Exception:
        s.check("kanban: scenario completed", False, traceback.format_exc()[-800:])
        s.shot(p, "kanban-exception")
