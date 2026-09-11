"""What a downstream user actually sees for three app_source header shapes.

    cd $SB/apps/verify2_testing_admin_1 && <venv with reflex[testing]>/bin/python v_e2e_errors.py
"""

import json
import sys
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


def SilentApp() -> "None":  # noqa: N802
    # body deliberately contains no "):" sequence, so the regex matches nothing
    import reflex as rx

    app = rx.App()
    app.add_page(rx.text("hi"), route="/")


out = {"reflex": reflex.constants.Reflex.VERSION, "python": sys.version.split()[0]}
for fn, key in (
    (CommentApp, "trailingcomment"),
    (StrAnnotApp, "strannot"),
    (SilentApp, "silentannot"),
):
    root = Path(tempfile.mkdtemp(prefix=f"v_ah_{key}_"))
    h = AppHarness.create(root=root, app_source=fn, app_name=key)
    try:
        h.__enter__()
        out[key] = "STARTED (no error)"
        h.stop()
    except BaseException as exc:
        out[key] = f"{type(exc).__name__}: {exc}"
        out[key + "_tb_tail"] = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )[-1200:]
    gen = root / key / f"{key}.py"
    if gen.exists():
        out[key + "_generated"] = gen.read_text()

print(json.dumps(out, indent=2))
