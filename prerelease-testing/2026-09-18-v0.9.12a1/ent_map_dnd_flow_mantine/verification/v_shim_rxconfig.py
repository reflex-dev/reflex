"""Configuration for the IT ticketing demo.

Exercises the EventHandlerAPIPlugin: every event handler on the State
is exposed as an HTTP POST endpoint under /_reflex/event/..., and the
OpenAPI spec is published at /_reflex/events/openapi.yaml with an
RFC 9727 catalog at /.well-known/api-catalog.
"""

import reflex as rx

# QA-ONLY SHIM (verifier): work around the 0.9.12a1 metaclass break (ISSUE 1) so the
# app can start and the ISSUE 2 redaction can be tested over HTTP.
import reflex.vars as _rxvars
from reflex.state import State as _State

_rxvars.BaseStateMeta = type(_State)

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="tickets",
    async_db_url="sqlite+aiosqlite:///tickets.db",
    db_url="sqlite:///tickets.db",
    plugins=[
        rxe.EventHandlerAPIPlugin(
            contact={"name": "Reflex Maintainers", "email": "info@reflex.dev"},
            license_info={
                "name": "Apache 2.0",
                "url": "https://opensource.org/licenses/Apache-2.0",
            },
        )
    ],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
