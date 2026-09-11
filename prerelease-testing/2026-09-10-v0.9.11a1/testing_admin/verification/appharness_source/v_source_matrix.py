"""Independent probe: which `def AppFactory(...)` header shapes survive
AppHarness._get_source_from_app_source + compile?

Run from a NEUTRAL cwd:
    cd $SB/apps/verify2_testing_admin_1 && <venv>/bin/python v_source_matrix.py
"""

import json
import pathlib

import reflex

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, (
    reflex.__file__
)

from reflex.testing import AppHarness  # noqa: E402

H = AppHarness.create(root=pathlib.Path("/tmp/_v_probe_unused"), app_source=None)


def f_plain():
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def f_trailing_comment():  # noqa: N802
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def f_trailing_comment_plain_words():  # a note about the app
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def f_annot_none() -> None:
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def f_annot_str() -> "None":
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def f_annot_subscript() -> "tuple[int, str] | None":
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def f_annot_none_and_comment() -> None:  # noqa: N802
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def f_multiline_sig(
    a=1,
):
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def f_docstring():
    """Doc."""
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def _decorator(fn):
    return fn


@_decorator
def f_decorated():
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


CASES = [
    f_plain,
    f_trailing_comment,
    f_trailing_comment_plain_words,
    f_annot_none,
    f_annot_str,
    f_annot_subscript,
    f_annot_none_and_comment,
    f_multiline_sig,
    f_docstring,
    f_decorated,
]

results = {}
for fn in CASES:
    src = H._get_source_from_app_source(fn)
    try:
        compile(src, "<generated>", "exec")
        status = "compiles"
    except SyntaxError as exc:
        status = f"{type(exc).__name__}: {exc.msg} (line {exc.lineno})"
    results[fn.__name__] = {
        "status": status,
        "body_has_index_def": "def index()" in src,
        "generated": src,
    }

print(
    json.dumps(
        {"reflex": reflex.constants.Reflex.VERSION, "python": __import__("sys").version.split()[0], "results": results},
        indent=2,
    )
)
