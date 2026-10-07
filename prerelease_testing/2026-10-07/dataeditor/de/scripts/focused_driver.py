"""Re-run unfinished data-editor checks with macOS-aware keyboard and geometry."""
import json
import sys
from pathlib import Path

import driver


def cell_click(page, col, row, double=False):
    """Click a current cell after re-reading grid geometry."""
    box = driver.grid_canvas_box(page, "#de-main-box")
    x, y = driver.cell_xy(box, driver.MAIN_W, col, row, 60, marker=32)
    (page.mouse.dblclick if double else page.mouse.click)(x, y)


def edit(run, page):
    """Exercise typing, boolean changes and delete selection without stale bounds."""
    run.goto(page, "/de", "#de-main-box canvas")
    page.wait_for_timeout(1000)
    cell_click(page, 0, 1)
    page.wait_for_timeout(400)
    page.keyboard.type("Zed")
    page.wait_for_timeout(700)
    run.note({"first_edit_overlay_before_commit": page.locator("#portal textarea").all_text_contents(), "overlay_values": page.locator("#portal textarea").evaluate_all("els => els.map(e => e.value)")})
    page.keyboard.press("Enter")
    driver.wait_text(page, "#edits", lambda s: s != "edits:0", timeout=2000)
    page.wait_for_timeout(500)
    first = json.loads(driver.text(page, "#last-edit") or "{}")
    run.check("first_edit_fast_typing_keeps_all_chars", first.get("cell", {}).get("data") == "Zed", first)
    for col, row, value, expected in [(0, 0, "MacEdit", "MacEdit"), (1, 2, "42", 42), (2, 3, "9.5", 9.5)]:
        cell_click(page, col, row)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        page.locator("#portal textarea, #portal input").first.wait_for(timeout=5000)
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.type(value, delay=60)
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        data = json.loads(driver.text(page, "#last-edit") or "{}")
        run.check(f"explicit_editor_col_{col}", data.get("pos") == [col,row] and data.get("cell",{}).get("data") == expected, data)
    before = driver.text(page, "#edits")
    cell_click(page, 3, 0)
    page.wait_for_timeout(700)
    after1 = driver.text(page, "#edits")
    value1 = driver.text(page, "#last-edit")
    run.check("bool_single_click_toggles", after1 != before and '"kind": "boolean"' in value1, {"before":before,"after":after1,"last_edit":value1})
    cell_click(page, 3, 0)
    page.wait_for_timeout(700)
    run.check("bool_second_click_toggles", driver.text(page,"#edits") != after1 and '"kind": "boolean"' in driver.text(page,"#last-edit"), {"after":driver.text(page,"#edits"),"last_edit":driver.text(page,"#last-edit")})
    cell_click(page, 0, 4, double=True)
    page.wait_for_timeout(400)
    run.check("text_overlay_open", page.locator("#portal textarea").count() == 1)
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    run.check("text_overlay_escape_closes", page.locator("#portal textarea").count() == 0)
    cell_click(page, 0, 5)
    page.wait_for_timeout(350)
    errors_before = len(run.group["pageerrors"])
    edits_before = driver.text(page,"#edits")
    page.keyboard.press("Delete")
    page.wait_for_timeout(1000)
    run.check("delete_selection_delivered", '"cell": [0, 5]' in driver.text(page,"#deleted"), driver.text(page,"#deleted"))
    run.check("delete_no_javascript_error", len(run.group["pageerrors"]) == errors_before, run.group["pageerrors"][errors_before:])
    run.check("delete_clears_cell", driver.text(page,"#edits") != edits_before, driver.text(page,"#last-edit"))
    run.shot(page,"edit-delete",full=True)


def overlay(run,page):
    """Test a local carousel, then Escape without an outside-click fallback."""
    run.goto(page,"/de","#de-main-box canvas")
    box=driver.grid_canvas_box(page,"#de-main-box")
    st=driver.open_image_overlay(run,page,box,1,"multi-local")
    run.check("image_overlay_styled", st.get("has_carousel") and st.get("n_visible_imgs")==1 and st.get("slider_display")=="flex",st)
    nxt=page.locator(".carousel .control-next").first
    nxt.click()
    page.wait_for_timeout(600)
    st2=driver.overlay_state(page)
    run.check("carousel_next_changes_slide", st2.get("visible_srcs") != st.get("visible_srcs") and st2.get("n_visible_imgs")==1,st2)
    page.keyboard.press("Escape")
    page.wait_for_timeout(600)
    st3=driver.overlay_state(page)
    run.check("image_overlay_escape_after_arrow_closes", not st3.get("has_carousel"),st3)
    run.shot(page,"overlay-after-escape")
    page.mouse.click(1200,120)
    page.wait_for_timeout(300)
    box=driver.grid_canvas_box(page,"#de-main-box")
    driver.open_image_overlay(run,page,box,0,"single-local")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    st4=driver.overlay_state(page)
    run.check("image_overlay_escape_without_arrow_closes",not st4.get("has_carousel"),st4)
    run.shot(page,"single-overlay-after-escape")


_original_attach = driver.Run.attach

def attach_with_frames(self,page):
    """Capture short websocket transcripts and JavaScript error stacks."""
    _original_attach(self,page)
    self.group["ws_frames"] = []
    frames=self.group["ws_frames"]
    def add(direction,frame):
        if len(frames)<200:
            frames.append({"direction":direction,"payload":str(frame)[:2200]})
    def ws(sock):
        sock.on("framesent",lambda frame:add("sent",frame))
        sock.on("framereceived",lambda frame:add("received",frame))
    page.on("websocket",ws)


driver.Run.attach=attach_with_frames
driver.GROUPS["de_edit"]=edit
driver.GROUPS["de_overlay"]=overlay
if __name__=="__main__":
    sys.exit(driver.main())
