"""Dynamic route args across several pages and substates: does any framework path reach add_var / the #7516 guard?
Run: cd <area>/probes/dynroute && EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_dynroute.py"""
import os
import sys
import traceback

sys.path.insert(0, os.getcwd())
import reflex as rx  # noqa: E402

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

import reflex.state as rs  # noqa: E402

calls = []
orig = rs.BaseState.add_var.__func__


def spy(cls, name, *a, **k):
    calls.append((cls.__name__, name))
    return orig(cls, name, *a, **k)


rs.BaseState.add_var = classmethod(spy)
print(f"reflex {version('reflex')}")


class Blog(rx.State):
    title: str = "t"


class Post(Blog):
    body: str = "b"


app = rx.App()
try:
    app.add_page(lambda: rx.text(Blog.title), route="/a/[slug]")
    app.add_page(lambda: rx.text(Post.body), route="/b/[slug]")

    class Late(Post):  # substate defined after the route arg was installed
        z: int = 0

    app.add_page(lambda: rx.text(Late.z), route="/c/[slug]/[[...splat]]")
    app.add_page(lambda: rx.text(Late.z), route="/d/[id]")
    root = rx.State
    print("route args installed:", {k: type(v).__name__ for k, v in root.computed_vars.items() if k in ("slug", "splat", "id")})
    print("Late sees slug:", "slug" in Late.vars, "| Late.slug js:", getattr(getattr(Late, "slug", None), "_js_expr", None))
    print("add_var calls during add_page:", calls)
    app._compile(prerender_routes=False) if hasattr(app, "_compile") else None
    print("compile ok")
except Exception as e:  # noqa: BLE001
    traceback.print_exc()
    print("EXC", type(e).__name__, e)
