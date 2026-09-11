"""Probe: which `def MyApp(...)` signature shapes survive AppHarness source extraction?

AppHarness copies the *body* of app_source into the generated app module by
regex-stripping the `def ...:` header and then textwrap.dedent()ing what is left.
Anything left on the header line (a trailing comment) becomes the first "line",
so dedent computes the wrong common indent.

    cd /tmp && <venv>/bin/python <this>/probe_appharness_source.py
"""

import json

import reflex

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, (
    reflex.__file__
)

from reflex.testing import AppHarness  # noqa: E402

H = AppHarness.create(root=__import__("pathlib").Path("/tmp/_ah_probe"), app_source=None)


def plain():
    import reflex as rx

    app = rx.App()


def noqa_comment():  # noqa: N802
    import reflex as rx

    app = rx.App()


def annotated() -> None:
    import reflex as rx

    app = rx.App()


def annotated_comment() -> None:  # a comment
    import reflex as rx

    app = rx.App()


def annotated_str() -> "None":
    import reflex as rx

    app = rx.App()


def multiline_sig(
    a=1,
):
    import reflex as rx

    app = rx.App()


def with_docstring():
    """Doc."""
    import reflex as rx

    app = rx.App()


results = {}
for fn in (
    plain,
    noqa_comment,
    annotated,
    annotated_comment,
    annotated_str,
    multiline_sig,
    with_docstring,
):
    src = H._get_source_from_app_source(fn)
    try:
        compile(src, "<generated>", "exec")
        status = "compiles"
    except SyntaxError as exc:
        status = f"{type(exc).__name__}: {exc.msg} (line {exc.lineno})"
    results[fn.__name__] = {
        "status": status,
        "first_two_lines": src.split("\n")[:3],
    }

print(json.dumps({"reflex": reflex.constants.Reflex.VERSION, "results": results}, indent=2))
