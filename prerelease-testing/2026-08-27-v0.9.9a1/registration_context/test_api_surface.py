"""Breaking-API surface probes for reflex 0.9.9a1 RegistrationContext changes (PR #6382).

Run with any reflex venv python:
    REFLEX_TELEMETRY_ENABLED=false <venv>/bin/python test_api_surface.py

Prints exact downstream-visible behavior for each probe. Exit code 0 always;
read the output.
"""

import sys
import traceback


def probe(name, fn):
    print(f"\n=== PROBE: {name} ===")
    try:
        result = fn()
        print(f"OK -> {result!r}")
    except Exception as e:
        print(f"RAISED {type(e).__module__}.{type(e).__name__}: {e}")
        tb = traceback.format_exc().strip().splitlines()
        print("  last tb line:", tb[-2] if len(tb) > 1 else tb[-1])


import importlib.metadata as md

print("reflex version:", md.version("reflex"))
print("python:", sys.version)

import reflex as rx  # noqa: E402

probe("reflex.config.get_config() plain", lambda: type(rx.config.get_config()).__name__)

probe("reflex.config.get_config(reload=True)  [OLD API]",
      lambda: rx.config.get_config(reload=True))

probe("from reflex import config; config.get_config(True) positional [OLD API]",
      lambda: rx.config.get_config(True))

def _reload_config():
    from reflex.config import reload_config
    cfg = reload_config()
    return type(cfg).__name__ + " app_name=" + repr(cfg.app_name)

probe("reflex.config.reload_config()  [NEW API]", _reload_config)

def _reload_config_base():
    from reflex_base.config import reload_config
    return type(reload_config()).__name__

probe("reflex_base.config.reload_config()", _reload_config_base)

def _bundled_attr_reflex():
    import reflex.components.dynamic as dyn
    return dyn.bundled_libraries

probe("reflex.components.dynamic.bundled_libraries  [OLD module attr]", _bundled_attr_reflex)

def _bundled_attr_base():
    import reflex_base.components.dynamic as dyn
    return dyn.bundled_libraries

probe("reflex_base.components.dynamic.bundled_libraries  [OLD module attr]", _bundled_attr_base)

def _bundle_library_str():
    from reflex.components.dynamic import bundle_library
    bundle_library("some-lib@1.2.3")
    from reflex_base.registry import RegistrationContext
    return RegistrationContext.ensure_context().bundled_libraries

probe("bundle_library('some-lib@1.2.3') then read ctx.bundled_libraries", _bundle_library_str)

def _reset_bundled():
    from reflex.components.dynamic import reset_bundled_libraries
    reset_bundled_libraries()
    from reflex_base.registry import RegistrationContext
    return RegistrationContext.ensure_context().bundled_libraries

probe("reset_bundled_libraries()", _reset_bundled)

def _rx_namespace():
    # things third-party libs commonly touch
    out = {}
    out["rx.App"] = bool(rx.App)
    from reflex.page import page as _p  # noqa: F401
    out["reflex.page.page"] = True
    try:
        from reflex.page import DECORATED_PAGES  # noqa: F401
        out["reflex.page.DECORATED_PAGES"] = repr(DECORATED_PAGES)[:80]
    except ImportError as e:
        out["reflex.page.DECORATED_PAGES"] = f"ImportError: {e}"
    try:
        from reflex.app import UnevaluatedPage  # noqa: F401
        out["reflex.app.UnevaluatedPage"] = True
    except ImportError as e:
        out["reflex.app.UnevaluatedPage"] = f"ImportError: {e}"
    return out

probe("misc third-party touchpoints", _rx_namespace)

def _registration_context_public():
    from reflex_base.registry import RegistrationContext
    ctx = RegistrationContext.ensure_context()
    info = {
        "type": type(ctx).__name__,
        "has_fork": callable(getattr(ctx, "fork", None)),
        "app_prop_before_app": None,
    }
    try:
        ctx.app
    except Exception as e:
        info["app_prop_before_app"] = f"{type(e).__name__}: {e}"
    # is it exported from reflex or reflex.utils anywhere?
    import reflex
    info["reflex.RegistrationContext"] = hasattr(reflex, "RegistrationContext")
    return info

probe("RegistrationContext public surface", _registration_context_public)

def _get_config_signature():
    import inspect
    from reflex.config import get_config
    return str(inspect.signature(get_config))

probe("inspect.signature(get_config)", _get_config_signature)
