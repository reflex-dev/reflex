import os, reflex as rx
assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
class RD(rx.State):
    @rx.var(deps=["router"], cache=True)
    def p(self) -> str:
        return self.router.url.path
cv = RD.computed_vars["p"]
print("raw _deps:", cv._deps(objclass=RD))
RD._init_var_dependency_dicts()
root = RD.get_root_state()
print("root _var_dependencies keys:", [k for k in root._var_dependencies if "router" in k])
for k in root._var_dependencies:
    if "router" in k:
        print(" ", k, "->", root._var_dependencies[k])
