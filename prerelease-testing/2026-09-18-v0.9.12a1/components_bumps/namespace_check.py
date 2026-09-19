import reflex as rx
assert "/envs/cb/" in rx.__file__, rx.__file__
print("reflex:", rx.__file__)

import reflex_components_core.datadisplay as dd
print("dir(datadisplay):", dir(dd))
try:
    dd.code_block
    print("FAIL: dd.code_block resolved ->", dd.code_block)
except Exception as e:
    print("dd.code_block ->", type(e).__name__, e)
try:
    dd.data_editor
    print("FAIL: dd.data_editor resolved")
except Exception as e:
    print("dd.data_editor ->", type(e).__name__, e)

from reflex.components.datadisplay import code, dataeditor
print("reflex.components.datadisplay.code ->", code.__name__)
print("reflex.components.datadisplay.dataeditor ->", dataeditor.__name__)

for name in ["code_block", "data_editor", "data_table", "logo", "markdown", "toast", "plotly", "segmented_control"]:
    try:
        print(f"rx.{name} -> OK", type(getattr(rx, name)))
    except Exception as e:
        print(f"rx.{name} -> {type(e).__name__}: {e}")

print("rx.recharts.sankey_chart ->", rx.recharts.sankey_chart)
print("rx.recharts.use_chart_width ->", rx.recharts.use_chart_width)
print("rx.recharts.SankeyNodeProps ->", rx.recharts.SankeyNodeProps)
print("rx.recharts.SankeyLinkProps ->", rx.recharts.SankeyLinkProps)
print("rx.vars.use_hook_var ->", rx.vars.use_hook_var)
print("rx.vars.use_id ->", rx.vars.use_id)
print("sankey_chart.node ->", rx.recharts.sankey_chart.node)
print("sankey_chart.link ->", rx.recharts.sankey_chart.link)

# CommonTag base
from reflex_base.components.tag import Tag
print("Tag MRO:", [c.__name__ for c in type(Tag).__mro__][:3] if not isinstance(Tag, type) else [c.__name__ for c in Tag.__mro__])
