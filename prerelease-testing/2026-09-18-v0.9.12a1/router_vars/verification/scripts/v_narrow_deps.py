import reflex as rx
assert "/envs/" in rx.__file__, rx.__file__
import importlib.metadata as md
print("reflex", md.version("reflex"))

print("field_dependencies of State.router.url :", rx.State.router.url._get_all_var_data().field_dependencies)
print("field_dependencies of State.router.session.client_ip :", rx.State.router.session.client_ip._get_all_var_data().field_dependencies)
print("field_dependencies of State.router :", rx.State.router._get_all_var_data().field_dependencies)

class S(rx.State):
    @rx.var(deps=[rx.State.router.url], auto_deps=False)
    def narrow_url(self) -> str:
        return self.router.url.path
    @rx.var(deps=[rx.State.router.session], auto_deps=False)
    def narrow_session(self) -> str:
        return self.router.session.client_ip

for n in ["narrow_url", "narrow_session"]:
    cv = S.computed_vars[n]
    print(n, "auto_deps=", cv._auto_deps, "deps=", {k: sorted(v) for k, v in cv._deps(objclass=S).items()})

# who is registered as dirtying what, on the root state
root = rx.State
for f in ["rx_router_url", "rx_router_session", "rx_router_headers", "rx_router_page", "rx_router_route_id"]:
    regs = sorted(n for st, n in root._var_dependencies.get(f, set()) if st == S.get_full_name())
    print(f"{f:20s} -> invalidates S vars {regs}")
