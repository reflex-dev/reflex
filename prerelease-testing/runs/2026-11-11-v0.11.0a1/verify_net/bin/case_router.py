"""Backend route resolution for case-colliding pages. usage: <venv-python> case_router.py <venv>"""
import sys
import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
app = rx.App()
app.add_page(lambda: rx.text("U"), route="/Foo", on_load=rx.console_log("U"))
app.add_page(lambda: rx.text("L"), route="/foo", on_load=rx.console_log("L"))
print("version", rx.__version__ if hasattr(rx, "__version__") else "?")
print("unevaluated routes:", list(app._unevaluated_pages))
for p in ["/Foo", "/foo", "/FOO"]:
    r = app.router(p)
    print(p, "->", r, "load:", [str(e) [:60] for e in app.get_load_events(p)])
