"""Measure import cost / optional-module leakage / RSS with optional libs INSTALLED."""
import os, resource, sys, time
t0 = time.perf_counter()
import reflex, reflex as rx
t_import = time.perf_counter() - t0
assert "/envs/" in reflex.__file__, reflex.__file__
WATCH = {"pandas","PIL","plotly","numpy","sqlalchemy","sqlmodel","alembic","starlette_admin"}
def opt(): return sorted({m.split(".")[0] for m in sys.modules if m.split(".")[0] in WATCH})
rss_after_import = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
print(f"VERSION={reflex.constants.Reflex.VERSION}")
print(f"IMPORT_REFLEX_SEC={t_import:.3f}")
print(f"OPT_AFTER_IMPORT={opt()}")
print(f"NUM_MODULES_AFTER_IMPORT={len(sys.modules)}")
print(f"RSS_AFTER_IMPORT_MB={rss_after_import:.1f}")

# Build a small non-data, non-db app the way reflex does at startup.
t1 = time.perf_counter()
class S(rx.State):
    v: str = "x"
    n: int = 0
    items: list[str] = ["a","b"]
    def bump(self): self.n += 1
def page():
    return rx.vstack(
        rx.heading(S.v), rx.button("go", on_click=S.bump),
        rx.foreach(S.items, lambda i: rx.text(i)),
        rx.cond(S.n > 0, rx.text(S.n.to_string()), rx.text("zero")),
    )
app = rx.App()
app.add_page(page, route="/")
t_app = time.perf_counter() - t1
rss_after_app = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
print(f"BUILD_APP_SEC={t_app:.3f}")
print(f"OPT_AFTER_APP={opt()}")
print(f"NUM_MODULES_AFTER_APP={len(sys.modules)}")
print(f"RSS_AFTER_APP_MB={rss_after_app:.1f}")
