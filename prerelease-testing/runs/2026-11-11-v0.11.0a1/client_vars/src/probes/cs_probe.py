"""Offline probe: what rx.client_state expressions compile to. Run: cd probes && $SB/envs/<venv>/bin/python -I cs_probe.py <venv>"""
import sys, traceback
import reflex as rx
venv = sys.argv[1]
assert f"/envs/{venv}/" in rx.__file__, rx.__file__
from reflex_base.vars.function import ArgsFunctionOperationBuilder, FunctionVar
from reflex_base.vars.base import Var

def show(label, fn):
    try:
        r = fn()
        print(f"[ok ] {label}: {type(r).__name__} :: {str(r)[:300]}")
        return r
    except Exception as e:
        print(f"[ERR] {label}: {type(e).__name__}: {str(e)[:400]}")

cs = rx.client_state
n = show("named", lambda: cs("", name="query"))
u = show("unnamed", lambda: cs(0))
show("unnamed hooks", lambda: list(u._get_all_var_data().hooks))
show("named hooks", lambda: list(n._get_all_var_data().hooks))
show("set bare", lambda: u.set)
show("set value", lambda: u.set(5))
show("set lambda", lambda: u.set(lambda v: v + 1))
show("set FunctionVar", lambda: u.set(ArgsFunctionOperationBuilder.create(args_names=("v",), return_expr=Var("v * 2"))))
show("set lambda 0 args", lambda: u.set(lambda: 7))
show("set lambda 2 args", lambda: u.set(lambda a, b: 7))
lst = cs([1, 2])
show("list lambda v+[3]", lambda: lst.set(lambda v: v + [3]))
show("list lambda v.length", lambda: lst.set(lambda v: [v.length()]))
d = cs({"a": 1})
show("dict lambda", lambda: d.set(lambda v: v.merge({"b": 2})))
s = cs("x")
show("str lambda upper", lambda: s.set(lambda v: v.upper() + "!"))
nd = cs()
show("no default", lambda: list(nd._get_all_var_data().hooks))
show("no default lambda", lambda: nd.set(lambda v: v))
show("name unicode", lambda: cs("", name="naïve"))
show("name dash", lambda: cs("", name="my-var"))
show("name reserved", lambda: list(cs("", name="class")._get_all_var_data().hooks))
show("name empty", lambda: cs("", name=""))
show("name Var", lambda: cs("", name=rx.Var.create("x")))
show("prefix $", lambda: cs("", prefix="a$b"))
show("prefix ok", lambda: list(cs("", prefix="counter")._get_all_var_data().hooks))
show("unnamed push", lambda: u.push(3))
show("unnamed retrieve", lambda: u.retrieve())
show("unnamed global_value", lambda: u.global_value)
show("named push", lambda: n.push("v"))
show("named push Var", lambda: n.push(rx.Var.create("a") + "b"))
show("named push set", lambda: n.push({1, 2}))
show("named retrieve", lambda: n.retrieve())
show("set_value (deprecated)", lambda: u.set_value(3))
show("set_value bare (deprecated)", lambda: u.set_value())
show("_x.client_state legacy", lambda: rx._x.client_state("legacy_name", default=1))
show("_x.client_state legacy positional", lambda: rx._x.client_state("legacy2", 1, False))
show("_x.client_state legacy kw global_ref", lambda: rx._x.client_state(default=1, global_ref=False))
show("_x.ClientStateVar.create", lambda: rx._x.client_state.__self__ if hasattr(rx._x.client_state, "__self__") else rx._x.client_state)
show("default is state var", lambda: None)
class S(rx.State):
    v: int = 3
    _b: int = 4
show("default=State var", lambda: list(cs(S.v)._get_all_var_data().hooks))
show("default=backend var", lambda: cs(S._b))
show("default=set", lambda: (cs({1,2})._var_type, list(cs({1,2})._get_all_var_data().hooks)))
show("bool(value)", lambda: bool(u.value))
show("value in cond", lambda: rx.cond(u.value > 1, "a", "b"))
show("named dup diff default", lambda: (cs("A", name="dup"), cs(1, name="dup")))
show("old kw var_name on new API", lambda: cs(var_name="x", default=1))
show("old positional on new API", lambda: cs("x", 1))
print("--- following the hint of the 'scoped' error literally")
hinted = show('rx.client_state("my_name")', lambda: cs("my_name"))
show('  -> its hook (name is generated, "my_name" is the DEFAULT)', lambda: list(hinted._get_all_var_data().hooks))
show('  -> .push(1) on it', lambda: hinted.push(1))
show('rx.client_state("", name="my_name").push(1)', lambda: cs("", name="my_name").push(1) and "ok")
print("docstring:", [l.strip() for l in rx.client_state.__doc__.splitlines() if "my_name" in l])
