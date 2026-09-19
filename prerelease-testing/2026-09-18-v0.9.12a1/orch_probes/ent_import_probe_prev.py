import importlib, traceback, sys
import reflex
assert "/envs/entprev/" in reflex.__file__, reflex.__file__
print("reflex", reflex.constants.Reflex.VERSION)
mods = [
    "reflex_enterprise", "reflex_enterprise.app", "reflex_enterprise.config", "reflex_enterprise.vars",
    "reflex_enterprise.auth", "reflex_enterprise.auth.oidc.state", "reflex_enterprise.auth.enforcement",
    "reflex_enterprise.auth.cookie", "reflex_enterprise.auth.replay", "reflex_enterprise.auth.decorators",
    "reflex_enterprise.plugins", "reflex_enterprise.plugins.event_handler_api", "reflex_enterprise.mcp",
    "reflex_enterprise.plugins.mcp_auth.provider",
    "reflex_enterprise.components.ag_grid", "reflex_enterprise.components.ag_grid.wrapper",
    "reflex_enterprise.components.map", "reflex_enterprise.components.dnd", "reflex_enterprise.components.flow",
    "reflex_enterprise.components.mantine", "reflex_enterprise.components.highcharts", "reflex_enterprise.testing",
]
bad = 0
for m in mods:
    try:
        importlib.import_module(m); print("OK  ", m)
    except Exception as e:
        bad += 1; print("FAIL", m, "->", type(e).__name__, str(e)[:300]); traceback.print_exc(limit=3)
import reflex_enterprise as rxe
for name in ["App", "Config", "AuthPlugin", "MCPPlugin", "static", "field", "var", "event", "ag_grid", "map", "dnd", "flow", "mantine"]:
    try:
        getattr(rxe, name); print("attr OK  ", name)
    except Exception as e:
        bad += 1; print("attr FAIL", name, type(e).__name__, str(e)[:200])
print("BAD =", bad)
