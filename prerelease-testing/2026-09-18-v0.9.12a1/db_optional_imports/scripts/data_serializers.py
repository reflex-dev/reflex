import sys, json
import reflex as rx, reflex
assert "/envs/" in reflex.__file__, reflex.__file__
print("VERSION:", reflex.constants.Reflex.VERSION)
WATCH = {"sqlalchemy","sqlmodel","alembic","pandas","PIL","plotly","numpy"}
def loaded():
    return sorted({m.split(".")[0] for m in sys.modules if m.split(".")[0] in WATCH})
print("A. after import reflex:", loaded())

from reflex_base.utils import serializers as S
import pandas as pd
print("B. after import pandas:", loaded())
df = pd.DataFrame({"a":[1,2],"b":["x","y"]})
print("   pandas.DataFrame module:", pd.DataFrame.__module__, "| identity in vars(pandas):", vars(pd).get("DataFrame") is pd.DataFrame)
print("   _get_optional_type_name(DataFrame):", S._get_optional_type_name(pd.DataFrame))
print("   get_serializer(DataFrame):", S.get_serializer(pd.DataFrame))
try:
    out = rx.utils.format.json_dumps(S.serialize(df))
    print("   serialize(df) OK, len:", len(out), "head:", out[:120])
except Exception as e:
    import traceback; traceback.print_exc()

import plotly.graph_objects as go
print("C. after import plotly:", loaded())
fig = go.Figure(data=[go.Bar(x=[1,2],y=[3,4])])
print("   go.Figure module:", go.Figure.__module__)
print("   'plotly.graph_objs._figure' in sys.modules:", "plotly.graph_objs._figure" in sys.modules)
import plotly.graph_objs as gobjs
print("   vars(plotly.graph_objs._figure)['Figure'] is go.Figure:", vars(sys.modules.get("plotly.graph_objs._figure", type("x",(),{"__dict__":{}}))).get("Figure") is go.Figure if "plotly.graph_objs._figure" in sys.modules else "MODULE NOT LOADED")
print("   _get_optional_type_name(go.Figure):", S._get_optional_type_name(go.Figure))
print("   get_serializer(go.Figure):", S.get_serializer(go.Figure))
try:
    ser = S.serialize(fig)
    print("   serialize(fig) OK type:", type(ser).__name__, "keys:", list(ser)[:5] if isinstance(ser, dict) else str(ser)[:80])
except Exception as e:
    import traceback; traceback.print_exc()

# Template
tmpl = go.layout.Template()
print("   go.layout.Template module:", type(tmpl).__module__)
print("   _get_optional_type_name(Template):", S._get_optional_type_name(type(tmpl)))
print("   get_serializer(Template):", S.get_serializer(type(tmpl)))

from PIL import Image
print("D. after import PIL:", loaded())
im = Image.new("RGB", (4,4), (255,0,0))
print("   Image class:", type(im).__name__, type(im).__module__)
print("   _get_optional_type_name(Image.Image):", S._get_optional_type_name(Image.Image))
print("   get_serializer(type(im)):", S.get_serializer(type(im)))
try:
    ser = S.serialize(im)
    print("   serialize(im) OK:", str(ser)[:60])
except Exception as e:
    import traceback; traceback.print_exc()
