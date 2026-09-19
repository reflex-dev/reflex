import os, reflex as rx
assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
class RD(rx.State):
    @rx.var(deps=["router"], cache=True)
    def p(self) -> str:
        return self.router.url.path
print("class created")
RD._init_var_dependency_dicts()
print("deps inited; _var_dependencies:", {k: dict(v) for k, v in list(RD._var_dependencies.items())[:4]})
