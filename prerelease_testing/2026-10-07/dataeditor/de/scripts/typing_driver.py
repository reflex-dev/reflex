"""Measure first-typing loss at human and automation typing speeds."""
import json
import sys
from pathlib import Path
import focused_driver
from driver import Run, grid_canvas_box, cell_xy, MAIN_W, text, sync_playwright

base,out,label=sys.argv[1:]
run=Run(base,Path(out),label)
state="""() => {const x=document.querySelector('#portal textarea, #portal input'); return {active: document.activeElement?.tagName, editor:x ? {value:x.value,start:x.selectionStart,end:x.selectionEnd,focused:x===document.activeElement}:null};}"""
with sync_playwright() as p:
    browser=p.chromium.launch()
    for delay in [0,40,120]:
        run.start_group(f"typing_delay_{delay}")
        ctx=browser.new_context(viewport={"width":1280,"height":900})
        pg=ctx.new_page();run.attach(pg)
        run.goto(pg,"/de","#de-main-box canvas")
        focused_driver.cell_click(pg,0,1)
        pg.wait_for_timeout(500)
        pg.keyboard.type("Slow",delay=delay)
        pg.wait_for_timeout(800)
        before=pg.evaluate(state)
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(800)
        result=json.loads(text(pg,"#last-edit") or "{}")
        run.check("typed_value_preserved",result.get("cell",{}).get("data")=="Slow",{"delay":delay,"before_commit":before,"event":result})
        ctx.close()
    run.start_group("first_key_selection")
    ctx=browser.new_context(viewport={"width":1280,"height":900})
    pg=ctx.new_page();run.attach(pg)
    run.goto(pg,"/de","#de-main-box canvas")
    focused_driver.cell_click(pg,0,1)
    pg.wait_for_timeout(500)
    pg.keyboard.press("S")
    pg.wait_for_timeout(800)
    first=pg.evaluate(state)
    run.note({"after_first_key":first})
    run.shot(pg,"after-first-key")
    pg.keyboard.type("low",delay=120)
    pg.wait_for_timeout(300)
    second=pg.evaluate(state)
    pg.keyboard.press("Enter");pg.wait_for_timeout(800)
    result=json.loads(text(pg,"#last-edit") or "{}")
    run.check("first_letter_not_selected_for_replacement",first.get("editor",{}).get("start")==first.get("editor",{}).get("end"),first)
    run.check("delayed_remainder_preserves_first_letter",result.get("cell",{}).get("data")=="Slow",{"after_remaining_keys":second,"event":result})
    ctx.close();browser.close()
(run.out/"results.json").write_text(json.dumps(run.results,indent=1))
