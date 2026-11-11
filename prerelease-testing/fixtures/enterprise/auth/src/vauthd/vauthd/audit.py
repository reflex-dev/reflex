"""Audit hook for vauthd: append (action, outcome, route, session) of every auth decision to $VAUTHD_AUDIT_FILE (JSONL).

The page guard's PAGE_LOAD record carries ``route=str(state.router.url)`` as seen by the on_load guard, i.e. exactly the
router view that reflex#7360 changed (on_load events no longer carry router_data).
"""

import json
import os
import time


def audit_auth(action, outcome, context) -> None:
    """Record one audit event (no claims, no payload)."""
    path = os.environ.get("VAUTHD_AUDIT_FILE")
    if not path:
        return
    rec = {
        "t": round(time.time(), 3),
        "pid": os.getpid(),
        "action": action.value,
        "outcome": outcome.value,
        "route": context.route,
        "session": bool(context.session_id),
        "handler": context.handler_name,
        "sub": (context.userinfo or {}).get("sub"),
        "reason": context.reason,
    }
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
