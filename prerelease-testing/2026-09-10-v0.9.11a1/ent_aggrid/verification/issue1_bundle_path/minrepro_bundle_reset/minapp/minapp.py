"""Minimal repro: a module-level bundle_library() call is wiped before pages compile.

reflex/compiler/compiler.py calls reset_bundled_libraries() inside compile_app(),
which runs AFTER the app module has been imported. Anything user code bundled at
import time is therefore gone by the time pages are evaluated/compiled.
"""

import json
import pathlib

import reflex as rx

assert "/envs/verify2_ent_aggrid_0" in rx.__file__, rx.__file__

from reflex.components.dynamic import bundle_library
from reflex_base.registry import RegistrationContext

MARKER = "$/app_components/minapp/minapp"
OUT = pathlib.Path(__file__).resolve().parent.parent / "bundle_reset_report.json"

# 1. bundle at import time, exactly as the "not bundled" error message tells you to.
bundle_library(MARKER)
AT_IMPORT = list(RegistrationContext.ensure_context().bundled_libraries)


def index() -> rx.Component:
    """Page that records the bundled-library list as seen during page evaluation."""
    at_page_eval = list(RegistrationContext.ensure_context().bundled_libraries)
    OUT.write_text(
        json.dumps(
            {
                "marker": MARKER,
                "at_import_time": AT_IMPORT,
                "at_page_eval": at_page_eval,
                "marker_present_at_import": MARKER in AT_IMPORT,
                "marker_present_at_page_eval": MARKER in at_page_eval,
            },
            indent=2,
        )
    )
    if MARKER not in at_page_eval:
        msg = (
            f"REPRO: {MARKER!r} was bundled at import time but is missing during "
            f"page evaluation. bundled_libraries={at_page_eval}"
        )
        raise RuntimeError(msg)
    return rx.text("bundled survived")


app = rx.App()
app.add_page(index, route="/")
