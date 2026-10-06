"""Construction probes for the dataeditor_components cluster (no server).

Run with each cluster venv's python from a neutral cwd:
  $SB/envs/dataeditor_components-alpha/bin/python probe_construct.py
"""
import importlib.metadata as md
import json
import sys
import traceback

import reflex as rx

assert "/scratchpad/envs/dataeditor_components-" in rx.__file__, rx.__file__
VER = md.version("reflex")
results = {"reflex": VER, "file": rx.__file__}


def probe(name, fn):
    try:
        out = fn()
        results[name] = {"ok": True, "out": out}
    except Exception as e:  # noqa: BLE001
        results[name] = {"ok": False, "err": f"{type(e).__name__}: {e}"[:600]}


class S(rx.State):
    currency: str = "$"
    fmt: str = "(v) => v"
    items: list[dict] = [{"name": "a", "qty": 1}]
    text: str = "x"
    lst: list[dict] = []


def tick(fmt):
    ax = rx.recharts.x_axis(data_key="x", tick_formatter=fmt)
    return str(ax.render()["props"])[:300]


from reflex_base.vars.function import ArgsFunctionOperation, FunctionStringVar  # noqa: E402

probe("recharts_literal_str", lambda: tick("(v) => 'n' + v"))
probe("recharts_Var_create_str", lambda: tick(rx.Var.create("(v) => 'n' + v")))
probe("recharts_untyped_rx_Var", lambda: tick(rx.Var("(v) => 'raw' + v")))
probe("recharts_FunctionStringVar", lambda: tick(FunctionStringVar.create("((v) => v + 'u')")))
probe("recharts_FunctionStringVar_partial_state", lambda: tick(FunctionStringVar.create("((c, v) => c + v)").partial(S.currency)))
probe("recharts_ArgsFunctionOperation_state", lambda: tick(ArgsFunctionOperation.create(("v",), S.currency + rx.Var("v").to(str))))
probe("recharts_state_str_var", lambda: tick(S.fmt))
probe("recharts_typed_str_rawvar", lambda: tick(rx.Var("(v) => v", _var_type=str)))
probe("Var_create_python_lambda", lambda: str(rx.Var.create(lambda v: v)))
probe("arrayvar_foreach_list", lambda: str(S.items.foreach(lambda p: [p["name"], p["qty"]])))
probe("match_mixed_branches", lambda: str(rx.match(True, (S.text == "a", rx.text("A")), (S.text == "b", "lit"), rx.text("d"))))
probe("match_literal_only", lambda: str(rx.match(True, (S.text == "a", "A"), "D")))
probe("download_var_str", lambda: str(rx.download(data=S.text, filename="x.txt").args))
probe("download_var_list", lambda: str(rx.download(data=S.lst, filename="x.json").args))


def doc_import():
    from reflex.components.datadisplay.dataeditor import DataEditorTheme  # noqa: PLC0415
    return DataEditorTheme.__module__


probe("doc_import_DataEditorTheme", doc_import)
probe("rx_data_editor_theme", lambda: str(rx.data_editor_theme(accent_color="#f00", bg_cell="#000")))


def de_get_cell_content():
    import logging  # noqa: PLC0415
    records = []
    h = logging.Handler()
    h.emit = lambda r: records.append(r.getMessage())
    logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(logging.DEBUG)
    rx.data_editor(columns=[{"title": "A", "type": "str"}], data=[["x"]], get_cell_content="foo")
    return records


probe("de_get_cell_content_warning", de_get_cell_content)


def de_foreach_item_data():
    c = rx.foreach(S.items, lambda it: rx.data_editor(columns=[{"title": "A", "type": "str"}], data=it["rows"]))
    return str(c)[:200]


probe("de_foreach_untyped_item_data", de_foreach_item_data)
json.dump(results, sys.stdout, indent=1, default=str)
