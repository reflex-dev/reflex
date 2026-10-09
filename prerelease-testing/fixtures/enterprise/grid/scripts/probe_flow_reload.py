"""Probe: does controlled React Flow state (State.nodes / State.emoji) survive a reload?

Usage: probe_flow_reload.py <base_url> <out_dir> <expected_venv> <label>
Moves a node, sets the emoji, deletes a node, then reloads (same tab), capturing the boot
websocket frames and the rendered node positions after reload, and again after a 2nd reload
and after client-side navigation away and back.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
info = assert_driver_and_server(venv)


def tr(p, nid):
    loc = p.locator(f'.react-flow__node[data-id="{nid}"]')
    if not loc.count():
        return None
    m = re.search(r"translate\(([-\d.]+)px, ([-\d.]+)px\)", loc.get_attribute("style") or "")
    return (float(m.group(1)), float(m.group(2))) if m else None


def snap(p):
    return {"1-2": tr(p, "1-2"), "1-3 present": p.locator('.react-flow__node[data-id="1-3"]').count(),
            "emoji": p.locator('.react-flow__node[data-id="2-2"]').inner_text().strip()[:4], "nodes": p.locator(".react-flow__node").count()}


with Session(f"probe_flow_reload-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    p = s.new_page(label="flow-reload")
    frames, sent = [], []

    def on_ws(ws):
        ws.on("framereceived", lambda f: frames.append(str(f)))
        ws.on("framesent", lambda f: sent.append(str(f)))

    p.on("websocket", on_ws)

    def sent_set_nodes():
        outl = []
        for f in sent:
            if "set_nodes" in f:
                m = re.search(r'\{[^{}]*"id":"1-2"[^{}]*"position":\{"x":([-\d.]+),"y":([-\d.]+)', f) or re.search(r'"id":"1-2".{0,400}', f)
                outl.append({"1-2 sent": (m.groups() if m and m.groups() else (m.group(0)[:300] if m else None)), "len": len(f)})
            elif "hydrate" in f or '"name"' in f:
                outl.append(re.search(r'"name":"([^"]+)"', f).group(1) if re.search(r'"name":"([^"]+)"', f) else f[:80])
        return outl
    p.goto(base + "/overview", wait_until="networkidle")
    p.wait_for_selector(".react-flow__node")
    p.wait_for_timeout(1500)
    b = p.locator('.react-flow__node[data-id="1-2"]').bounding_box()
    x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    p.mouse.move(x, y); p.mouse.down(); p.mouse.move(x + 3, y + 3, steps=2); p.mouse.move(x - 120, y + 60, steps=20); p.mouse.up()
    p.wait_for_timeout(800)
    p.click("button[aria-label='Select emoji 🔥']")
    p.wait_for_timeout(800)
    res = {"before reload": snap(p)}
    for i in range(2):
        frames.clear()
        sent.clear()
        p.reload(wait_until="networkidle")
        p.wait_for_selector(".react-flow__node")
        p.wait_for_timeout(2500)
        res[f"after reload {i + 1}"] = snap(p)
        hyd = [f for f in frames if "overview_state" in f]
        res[f"reload {i + 1}: frames mentioning overview_state"] = len(hyd)
        res[f"reload {i + 1}: frame sample"] = (hyd[0][:600] if hyd else [f[:300] for f in frames[:3]])
        res[f"reload {i + 1}: events sent during boot"] = sent_set_nodes()
        s.shot(p, f"after-reload-{i + 1}")
    p.goto(base + "/", wait_until="networkidle")
    p.wait_for_timeout(800)
    p.click("a:has-text('Feature Overview')")
    p.wait_for_selector(".react-flow__node")
    p.wait_for_timeout(2000)
    res["after client-side nav back"] = snap(p)
    s.check("flow overview: moved node position survives reload", res["after reload 1"]["1-2"] == res["before reload"]["1-2"], res)
    s.check("flow overview: emoji (State.emoji) survives reload", res["after reload 1"]["emoji"] == res["before reload"]["emoji"], res)
    for k, v in res.items():
        print(f"{k}: {json.dumps(v, ensure_ascii=False)[:700]}")
    s.note(json.dumps(res, ensure_ascii=False)[:5000])
