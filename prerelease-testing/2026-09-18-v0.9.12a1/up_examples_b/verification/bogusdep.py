import os, reflex as rx
assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__
try:
    class B(rx.State):
        @rx.var(deps=["no_such_var"], auto_deps=False)
        def p(self) -> str:
            return "x"
    print("accepted; deps:", B.computed_vars["p"]._deps(objclass=B))
except Exception as e:
    print("RAISED:", type(e).__name__, e)
