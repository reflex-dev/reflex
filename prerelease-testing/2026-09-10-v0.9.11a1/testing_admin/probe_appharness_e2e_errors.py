"""End-to-end user-visible failures for the two AppHarness source-extraction shapes.

    cd /tmp && <venv with reflex[testing]>/bin/python <this>/probe_appharness_e2e_errors.py
"""

import json
import tempfile
import traceback
from pathlib import Path

import reflex

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, (
    reflex.__file__
)

from reflex.testing import AppHarness  # noqa: E402


def CommentApp():  # noqa: N802
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


def StrAnnotApp() -> "None":  # noqa: N802
    import reflex as rx

    def index():
        return rx.text("hi")

    app = rx.App()
    app.add_page(index, route="/")


out = {"reflex": reflex.constants.Reflex.VERSION}
for fn, key in ((CommentApp, "trailing_comment"), (StrAnnotApp, "string_return_annotation")):
    root = Path(tempfile.mkdtemp(prefix=f"ah_{key}_"))
    h = AppHarness.create(root=root, app_source=fn, app_name=key.replace("_", ""))
    try:
        h.__enter__()
        out[key] = "STARTED"
        h.stop()
    except BaseException as exc:
        out[key] = f"{type(exc).__name__}: {exc}"
        out[key + "_tb"] = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )[-900:]
        gen = root / key.replace("_", "") / f"{key.replace('_', '')}.py"
        if gen.exists():
            out[key + "_generated_head"] = gen.read_text().split("\n")[:6]

print(json.dumps(out, indent=2))
