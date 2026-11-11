"""App middleware used by the await matrix: an auth gate, a recorder and a mutator."""

from __future__ import annotations

import json
import os
import time

import reflex as rx
from reflex.event import Event
from reflex.state import StateUpdate

MW_LOG = os.environ.get("AWAIT_MW_LOG", "mw_events.jsonl")


def _record(kind: str, event: Event, **extra) -> None:
    try:
        payload = json.loads(json.dumps(event.payload, default=repr))
    except Exception as ex:  # pragma: no cover
        payload = {"unserializable": repr(ex)}
    with open(MW_LOG, "a") as f:
        f.write(
            json.dumps({
                "t": round(time.time(), 3),
                "kind": kind,
                "name": event.name,
                "payload": payload,
                "has_router_data": bool(event.router_data),
                "pid": os.getpid(),
                **extra,
            })
            + "\n"
        )


class RecorderMiddleware(rx.Middleware):
    """Logs every event preprocess sees."""

    async def preprocess(self, app, state, event):
        _record("seen", event, state_cls=type(state).__name__)
        return None


class AuthGate(rx.Middleware):
    """Blocks any event whose handler name starts with `secret_` unless Auth.logged_in."""

    async def preprocess(self, app, state, event):
        handler = event.name.rpartition(".")[2]
        if not handler.startswith("secret_"):
            return None
        from awaitapp.awaitapp import Auth

        auth = await state.get_state(Auth)
        if auth.logged_in:
            return None
        _record("blocked", event)
        auth.blocked_count += 1
        delta = await state._get_resolved_delta()
        state._clean()
        return StateUpdate(
            delta=delta,
            events=Event.from_event_type(rx.toast.error(f"blocked {handler}")),
        )


class Mutator(rx.Middleware):
    """Rewrites the payload of `mutate_me` events (amount * 10) and raises for `mw_raise`."""

    async def preprocess(self, app, state, event):
        handler = event.name.rpartition(".")[2]
        if handler == "mutate_me" and "amount" in event.payload:
            event.payload["amount"] = int(event.payload["amount"]) * 10
            _record("mutated", event)
        if handler == "mw_raise":
            msg = "middleware exploded"
            raise RuntimeError(msg)
        return None
