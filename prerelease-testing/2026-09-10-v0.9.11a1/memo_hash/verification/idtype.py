import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
from reflex.vars.base import Var

i = rx.Var("i_rx_state_", _var_type=int)

fstr = rx.el.div("x", id=f"row-{i}")
print("fstring id  :", type(fstr.id).__name__, repr(fstr.id))
print("  get_ref   :", fstr.get_ref())

varid = rx.el.div("x", id=rx.Var("some_var", _var_type=str))
print("Var id      :", type(varid.id).__name__)
print("  get_ref   :", varid.get_ref())

# f-string with an actual state var
class S(rx.State):
    name: str = ""

fs2 = rx.el.div("x", id=f"row-{S.name}")
print("state fstr  :", type(fs2.id).__name__, repr(fs2.id))
print("  get_ref   :", fs2.get_ref())

# concatenation form
cat = rx.el.div("x", id="row-" + S.name)
print("concat id   :", type(cat.id).__name__)
print("  get_ref   :", cat.get_ref())

# static
st = rx.el.div("x", id="row-static")
print("static id   :", type(st.id).__name__, "get_ref:", st.get_ref())

# f-string with .to_string()
fs3 = rx.el.div("x", id=rx.Var.create("row-").to_string() + S.name)
print("rxstr id    :", type(fs3.id).__name__, "get_ref:", fs3.get_ref())
