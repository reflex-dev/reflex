"""Print the compiled .web layout of one AppHarness app."""
import sys, tempfile, pathlib
from reflex.testing import AppHarness

def AppOne():
    import reflex as rx

    class S1(rx.State):
        items: list[str] = ["a", "b"]

    @rx.memo
    def card(v: rx.Var[str]) -> rx.Component:
        return rx.text(f"ONE-{v}")

    def row(v: rx.Var[str]) -> rx.Component:
        return rx.hstack(rx.text(v), card(v=v))

    def index() -> rx.Component:
        return rx.vstack(rx.foreach(S1.items, row))

    app = rx.App()
    app.add_page(index)

with tempfile.TemporaryDirectory() as td:
    with AppHarness.create(root=pathlib.Path(td) / "one", app_source=AppOne) as h:
        web = h.app_path / ".web"
        hits = []
        for p in web.rglob("*"):
            if p.is_file() and "node_modules" not in p.parts and p.suffix in (".js", ".jsx", ".ts", ".tsx"):
                try: t = p.read_text(errors="replace")
                except OSError: continue
                if "ONE-" in t or "memo(" in t:
                    hits.append((str(p.relative_to(web)), "ONE-" in t, "memo(" in t))
        print("candidate files:", hits[:20])
        print("total generated js under .web/app:", len(list((web / 'app').rglob('*.js*'))) if (web/'app').exists() else 'no app dir')
        print("top-level of .web:", sorted(x.name for x in web.iterdir())[:20])
