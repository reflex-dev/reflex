"""Minimal probe: is a module-level bundle_library() visible at page-eval time?

Pure reflex (no reflex-enterprise): prints the bundled-library list and the id()
of the active RegistrationContext at module import and again while the page is
being evaluated by the compiler.
"""

import reflex as rx
from reflex.components import dynamic
from reflex.components.dynamic import bundle_library

try:
    from reflex_base.registry import RegistrationContext
except Exception:  # pragma: no cover - older reflex
    RegistrationContext = None


def _ctx_id():
    if RegistrationContext is None:
        return "n/a"
    return hex(id(RegistrationContext.ensure_context()))


def _bundled():
    if RegistrationContext is not None:
        ctx = RegistrationContext.ensure_context()
        if hasattr(ctx, "bundled_libraries"):
            return sorted(ctx.bundled_libraries)
    return sorted(dynamic.bundled_libraries)


bundle_library("d3-format")
print("PROBE import      ctx=", _ctx_id(), "bundled=", _bundled(), flush=True)


@rx.page(route="/")
def index() -> rx.Component:
    print("PROBE page_eval   ctx=", _ctx_id(), "bundled=", _bundled(), flush=True)
    return rx.text("hi")


app = rx.App()
print("PROBE after_app   ctx=", _ctx_id(), "bundled=", _bundled(), flush=True)
