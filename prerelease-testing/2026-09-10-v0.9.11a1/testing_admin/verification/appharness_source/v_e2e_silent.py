"""The fully SILENT variant: the regex matches nothing, so the generated module
is the *function definition itself* and no `app` is ever created."""

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


def CleanSilentApp() -> "None":  # noqa: N802
    import reflex as rx

    app = rx.App()
    app.add_page(rx.text("hi"), route="/")


out = {"reflex": reflex.constants.Reflex.VERSION, "python": sys.version.split()[0]}
root = Path(tempfile.mkdtemp(prefix="v_ah_cleansilent_"))
h = AppHarness.create(root=root, app_source=CleanSilentApp, app_name="cleansilent")
try:
    h.__enter__()
    out["cleansilent"] = "STARTED (no error)"
    h.stop()
except BaseException as exc:
    out["cleansilent"] = f"{type(exc).__name__}: {exc}"
    out["cleansilent_tb_tail"] = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )[-900:]
gen = root / "cleansilent" / "cleansilent.py"
if gen.exists():
    out["cleansilent_generated"] = gen.read_text()
print(json.dumps(out, indent=2))
