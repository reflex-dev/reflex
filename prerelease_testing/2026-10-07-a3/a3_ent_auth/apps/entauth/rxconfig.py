"""ent_auth_mcp_redis: enterprise auth + MCP on Redis / multi-worker.

Env knobs (all optional):
  APP_FP / APP_BP           frontend / backend ports (default 3340 / 8340)
  AUTH_EXTRA_SCOPES=1       AuthPlugin(extra_scopes=["offline_access", "address"])
  AUTH_MULTI=1              two providers (Acme/Globex) via import-path strings
  MCP_CALL_RATE_LIMIT       MCPPlugin(call_rate_limit=...) (default 60)
  MCP_TOKEN_RATE_LIMIT      MCPPlugin(token_rate_limit=...) (default 10)
  MCP_PENDING               "queue" (default) or "drop"
  MCP_ACCESS_TTL            MCPPlugin(access_token_ttl=...) seconds (default 3600)
"""

import os

import reflex_enterprise as rxe

FP = int(os.environ.get("APP_FP", "3340"))
BP = int(os.environ.get("APP_BP", "8340"))

_auth_kwargs = {}
if os.environ.get("AUTH_EXTRA_SCOPES"):
    _auth_kwargs["extra_scopes"] = ["offline_access", "address"]
if os.environ.get("AUTH_MULTI"):
    _auth_kwargs["auth_providers"] = [
        "entauth.providers.AcmeAuthState",
        "entauth.providers.GlobexAuthState",
    ]

config = rxe.Config(
    app_name="entauth",
    frontend_port=FP,
    backend_port=BP,
    telemetry_enabled=False,
    plugins=[
        rxe.AuthPlugin(**_auth_kwargs),
        rxe.MCPPlugin(
            app_scopes={
                "profile:read": "Read the test profile",
                "items:write": "Modify the agent items",
            },
            pending_updates=os.environ.get("MCP_PENDING", "queue"),
            call_rate_limit=int(os.environ.get("MCP_CALL_RATE_LIMIT", "60")),
            token_rate_limit=int(os.environ.get("MCP_TOKEN_RATE_LIMIT", "10")),
            access_token_ttl=float(os.environ.get("MCP_ACCESS_TTL", "3600")),
        ),
    ],
)
