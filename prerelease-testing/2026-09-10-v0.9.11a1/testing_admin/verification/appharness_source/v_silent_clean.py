import pathlib

import reflex

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, (
    reflex.__file__
)

from reflex.testing import AppHarness  # noqa: E402

H = AppHarness.create(root=pathlib.Path("/tmp/_v_probe_unused2"), app_source=None)


def CleanSilentApp() -> "None":
    import reflex as rx

    app = rx.App()
    app.add_page(rx.text("hi"), route="/")


src = H._get_source_from_app_source(CleanSilentApp)
print("reflex", reflex.constants.Reflex.VERSION)
print("--- generated module ---")
print(src)
print("--- compiles? ---")
try:
    ns = {}
    exec(compile(src, "<gen>", "exec"), ns)
    print("compiles=True, module-level names:", sorted(k for k in ns if not k.startswith("__")))
    print("has 'app' at module level:", "app" in ns)
except SyntaxError as e:
    print("SyntaxError:", e)
