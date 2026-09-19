"""Probe: does deps=["router"] emit the documented deprecation?

usage: python rdvar.py <variant>
variants:
  A  explorer's exact form: deps=["router"], cache=True, body reads self.router.url.path
  B  deps=["router"], auto_deps=False, body does not read the router
  C  deps=["router"] (auto_deps default True), body does NOT read the router
  D  deps=[State.router], auto_deps=False  (the Var form; expected: no warning)
  E  deps=["router"], auto_deps=False, body DOES read self.router.url.path
"""
import os, sys
import reflex as rx

assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
print("reflex file:", rx.__file__)
print("reflex version:", rx.constants.Reflex.VERSION if hasattr(rx.constants, "Reflex") else "?")

from reflex import state as state_module

calls = []
_orig = state_module.console.deprecate
def spy(**kwargs):
    calls.append(kwargs.get("feature_name"))
    return _orig(**kwargs)
state_module.console.deprecate = spy

v = sys.argv[1]

if v == "A":
    class RD(rx.State):
        @rx.var(deps=["router"], cache=True)
        def p(self) -> str:
            return self.router.url.path
elif v == "B":
    class RD(rx.State):
        @rx.var(deps=["router"], auto_deps=False)
        def p(self) -> str:
            return "static"
elif v == "C":
    class RD(rx.State):
        @rx.var(deps=["router"], cache=True)
        def p(self) -> str:
            return "static"
elif v == "D":
    class RD(rx.State):
        @rx.var(deps=[rx.State.router], auto_deps=False)
        def p(self) -> str:
            return "static"
elif v == "E":
    class RD(rx.State):
        @rx.var(deps=["router"], auto_deps=False)
        def p(self) -> str:
            return self.router.url.path
else:
    raise SystemExit("bad variant")

cv = RD.computed_vars["p"]
print("variant:", v)
print("static_deps:", cv._static_deps)
print("raw _deps:", cv._deps(objclass=RD))
print("DEPRECATE CALLS:", calls)
root = RD.get_root_state()
regs = {k: sorted(x for x in vals if x[0] == RD.get_full_name()) for k, vals in root._var_dependencies.items() if any(x[0] == RD.get_full_name() for x in vals)}
print("registered deps:", sorted(regs))
