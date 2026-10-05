import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
import importlib.metadata as md
print("reflex", md.version("reflex"), rx.__file__)

from reflex import state as state_module
seen = []
orig = state_module.console.deprecate
def spy(*, feature_name, **kw):
    seen.append(feature_name)
    return orig(feature_name=feature_name, **kw)
state_module.console.deprecate = spy

class A(rx.State):
    @rx.var(deps=["router"], auto_deps=False)
    def a_body_reads_router(self) -> str:
        return self.router.url.path

class B(rx.State):
    @rx.var(deps=["router"], auto_deps=False)
    def b_body_no_router(self) -> str:
        return ""

class C(rx.State):
    @rx.var(deps=["router"])
    def c_auto_body_reads_router(self) -> str:
        return self.router.url.path

class D(rx.State):
    @rx.var(deps=["router"])
    def d_auto_body_no_router(self) -> str:
        return ""

class E(rx.State):
    @rx.var(deps=[rx.State.router], auto_deps=False)
    def e_var_form(self) -> str:
        return ""

for cls, name in [(A,"a_body_reads_router"),(B,"b_body_no_router"),(C,"c_auto_body_reads_router"),(D,"d_auto_body_no_router"),(E,"e_var_form")]:
    cv = cls.computed_vars[name]
    print(f"{name:26s} auto_deps={cv._auto_deps!s:5s} static={ {k: sorted(v) for k,v in cv._static_deps.items()} }")
    print(f"{'':26s} deps={ {k: sorted(v) for k,v in cv._deps(objclass=cls).items()} }")

print("DEPRECATIONS SEEN:", seen)
