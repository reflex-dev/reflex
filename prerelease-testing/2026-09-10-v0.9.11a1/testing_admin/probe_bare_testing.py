"""Probe: `import reflex.testing` and AppHarness.__enter__ in a bare (no-extra) install.

Run from a neutral cwd:
    cd /tmp && <venv>/bin/python <this>/probe_bare_testing.py
"""

import importlib
import json
import sys
import tempfile
import traceback
from pathlib import Path

import reflex

assert "/envs/" in reflex.__file__ and "/home/user/reflex/reflex" not in reflex.__file__, (
    reflex.__file__
)

out = {"reflex_file": reflex.__file__, "reflex_version": reflex.constants.Reflex.VERSION}

# 1. Bare importability of reflex.testing
try:
    importlib.import_module("reflex.testing")
    out["import_reflex_testing"] = "OK"
except BaseException as exc:
    out["import_reflex_testing"] = f"{type(exc).__name__}: {exc}"

# 2. Which test-only deps are actually absent?
for mod in ("psutil", "selenium", "uvicorn"):
    try:
        importlib.import_module(mod)
        out[f"has_{mod}"] = True
    except ImportError:
        out[f"has_{mod}"] = False
for mod in ("pydantic", "sqlmodel", "alembic"):
    try:
        importlib.import_module(mod)
        out[f"has_{mod}"] = True
    except ImportError:
        out[f"has_{mod}"] = False

# 3. AppHarness.create(...).__enter__() on a tiny app
TINY = '''
def TinyApp():
    import reflex as rx

    class TState(rx.State):
        n: int = 0

    def index():
        return rx.text(f"n={TState.n}", id="n")

    app = rx.App()
    app.add_page(index, route="/")
'''


def tiny_app():
    import reflex as rx

    class TState(rx.State):
        n: int = 0

    def index():
        return rx.text(f"n={TState.n}", id="n")

    app = rx.App()
    app.add_page(index, route="/")


try:
    from reflex.testing import AppHarness

    root = Path(tempfile.mkdtemp(prefix="bare_harness_"))
    h = AppHarness.create(root=root, app_source=tiny_app)
    try:
        h.__enter__()
        out["apphARNESS_enter"] = "STARTED (unexpected without the extra)"
        h.stop()
    except BaseException as exc:
        out["appharness_enter_type"] = type(exc).__name__
        out["appharness_enter_msg"] = str(exc)
        out["appharness_enter_tb_tail"] = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )[-1500:]
except BaseException as exc:
    out["appharness_import"] = f"{type(exc).__name__}: {exc}"

print(json.dumps(out, indent=2))
