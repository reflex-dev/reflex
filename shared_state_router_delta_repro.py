"""Self-contained counter-example for PR #6841 ("Avoid root dirty delta for shared state events").

Issue #6392 documents *why* ``_patch_state`` dirties ``router``/``router_data`` on the
private root before resolving the delta::

    The purpose for this is to force recomputation of vars that depend on router_data,
    like the client_token.  If a shared state had a computed var that depended on the
    client_token, then it would need to be explicitly marked dirty in order to
    recompute the var for each token it is linked from.

PR #6841 keeps the dirtying and keeps the resolve, but snapshots ``dirty_vars`` /
``dirty_substates`` for *every state in the tree* beforehand and restores them
afterwards.  So the recomputation still happens on every event -- its result is just
discarded before the event's real delta is built.

Two consequences, both checked below.

CHECK 1 -- a ``SharedState`` computed var that depends on
``self.router.session.client_token`` is recomputed once per linked client per event
(proving the mechanism is load-bearing) but is never delivered to any of them again
after the initial ``_link_to``.  It also disappears from ``_previous_dirty_vars``, so
it stops being propagated to the other clients linked to the same token.

CHECK 2 -- the restore is not scoped to ``router``/``router_data``.  It reverts the
dirty sets of every state in the tree, which also discards dirtiness that the
throwaway resolve *consumed*.  An ``@rx.var(interval=...)`` on the same shared state
has its ``last_updated`` reset by that resolve and is then dropped from the delta, so
it never reaches the frontend again -- a permanently stale value on screen.

Run headless (no browser, no redis, default in-memory state manager)::

    uv run python shared_state_router_delta_repro.py

Exit code 0 == both invariants hold (current ``main``).
Exit code 1 == at least one is broken (PR #6841).

The module is also a runnable Reflex app (``reflex run``) if you would rather poke at
it with two browser tabs.
"""

# ruff: noqa: T201  (printing the delta trace is the entire point of this script)
from __future__ import annotations

import asyncio
import datetime
import itertools
import sys
from collections.abc import Callable, Mapping
from typing import Any

from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor

import reflex as rx
from reflex.istate.manager.memory import StateManagerMemory
from reflex.state import StateUpdate

SHARED_TOKEN = "room1"
CLIENTS = ("alice", "bob", "carol")
TICK_INTERVAL = datetime.timedelta(seconds=1)

# Every time the router-dependent computed var body actually runs, we record the
# client_token it observed.  This is how we tell "recomputed" apart from "delivered".
RECOMPUTED_FOR: list[str] = []

_ticks = itertools.count(1)


class Room(rx.SharedState):
    """A shared chat room with per-viewer and interval-refreshed computed vars."""

    messages: list[str] = []

    @rx.var
    def whoami(self) -> str:
        """Depends on the *viewing* client's router, not on any shared var.

        Returns:
            The client_token of whichever private state tree this shared state is
            currently patched into.
        """
        token = self.router.session.client_token
        RECOMPUTED_FOR.append(token)
        return token

    @rx.var(interval=TICK_INTERVAL)
    def tick(self) -> int:
        """A value that must be refreshed every interval.

        Returns:
            A monotonically increasing counter, bumped on each recomputation.
        """
        return next(_ticks)

    @rx.event
    async def join(self, token: str):
        """Link this client's Room to the shared token.

        Args:
            token: The shared token to link to.
        """
        await self._link_to(token)

    @rx.event
    def say(self, msg: str):
        """Append a message to the shared room.

        Args:
            msg: The message to append.
        """
        self.messages = [*self.messages, msg]


def index() -> rx.Component:
    """The demo page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.text(Room.whoami, id="whoami"),
        rx.text(Room.tick, id="tick"),
        rx.foreach(Room.messages, rx.text),
        rx.button("say hi", on_click=Room.say("hi")),
    )


app = rx.App()
app.add_page(index)


class _StubTokenManager:
    def __init__(self) -> None:
        self.token_to_socket: dict[str, object] = {}
        self.token_to_sid: dict[str, str] = {}
        self.sid_to_token: dict[str, str] = {}


class _StubEventNamespace:
    """Stands in for the socketio namespace so deltas land in a list instead of a socket."""

    def __init__(self, sink: Callable[[str, Mapping[str, Any]], None]):
        self._token_manager = _StubTokenManager()
        self._sink = sink

    async def emit_update(self, update: StateUpdate, token: str) -> None:
        """Record a delta instead of writing it to a socket.

        Args:
            update: The state update being emitted.
            token: The client token it is addressed to.
        """
        self._sink(token, update.delta)


def _router_data(token: str) -> dict[str, Any]:
    return {
        "pathname": "/",
        "query": {},
        "token": token,
        "sid": f"sid-{token}",
        "headers": {},
        "ip": "127.0.0.1",
    }


def _var(delta_sub: dict[str, Any], name: str, default: Any = None) -> Any:
    """Read a var out of a delta sub-dict, ignoring the field marker suffix.

    Args:
        delta_sub: The per-state delta mapping.
        name: The var name.
        default: Returned when the var is absent.

    Returns:
        The var value, or ``default``.
    """
    for key, value in delta_sub.items():
        if key.split("\x00")[0] == name or key.startswith(name + "_rx_state_"):
            return value
    return default


class Driver:
    """Drives the real event pipeline for several clients and records their deltas."""

    def __init__(self) -> None:
        """Wire the app up to an in-memory state manager and a recording namespace."""
        app._enable_state()
        self.deltas: list[tuple[str, dict]] = []
        self.namespace = _StubEventNamespace(
            lambda token, delta: self.deltas.append((token, dict(delta)))
        )
        app._event_namespace = self.namespace  # pyright: ignore[reportAttributeAccessIssue]
        self.state_manager = StateManagerMemory()
        app._state_manager = self.state_manager

        async def emit_delta_impl(  # noqa: RUF029
            token: str, delta: Mapping[str, Mapping[str, Any]]
        ) -> None:
            self.deltas.append((token, dict(delta)))

        async def emit_event_impl(token: str, *events: Event) -> None:
            pass

        self.processor = BaseStateEventProcessor(
            backend_exception_handler=self._reraise, graceful_shutdown_timeout=1
        )
        self.processor._root_context = EventContext(
            token="",
            state_manager=self.state_manager,
            enqueue_impl=self.processor.enqueue_many,
            emit_delta_impl=emit_delta_impl,
            emit_event_impl=emit_event_impl,
        )
        for client in CLIENTS:
            # Pretend every client has a live socket, so shared-state fan-out reaches them.
            self.namespace._token_manager.token_to_socket[client] = object()
        # What each client's browser currently displays, keyed by var name.
        self.screens: dict[str, dict[str, Any]] = {c: {} for c in CLIENTS}

    @staticmethod
    def _reraise(ex: Exception) -> None:
        raise ex

    async def send(self, client: str, handler: str, **payload) -> dict[str, Any]:
        """Dispatch one event and collect every delta it produced.

        Args:
            client: The client token dispatching the event.
            handler: The event handler name, relative to Room.
            payload: The event payload.

        Returns:
            A record of what was recomputed and what was delivered.
        """
        from reflex.istate.shared import UPDATE_OTHER_CLIENT_TASKS

        self.deltas.clear()
        RECOMPUTED_FOR.clear()

        future = await self.processor.enqueue(
            client,
            Event(
                name=f"{Room.get_full_name()}.{handler}",
                router_data=_router_data(client),
                payload=payload,
            ),
        )
        await future.wait_all()
        # Shared-state fan-out to other linked clients runs in detached tasks.
        for _ in range(200):
            if not UPDATE_OTHER_CLIENT_TASKS:
                break
            await asyncio.sleep(0.01)
        if UPDATE_OTHER_CLIENT_TASKS:
            await asyncio.gather(*list(UPDATE_OTHER_CLIENT_TASKS))

        room = Room.get_full_name()
        whoami_delivered: dict[str, Any] = {}
        tick_delivered: dict[str, Any] = {}
        for token, delta in self.deltas:
            sub = delta.get(room)
            if not sub:
                continue
            self.screens[token].update(sub)
            if (value := _var(sub, "whoami")) is not None:
                whoami_delivered[token] = value
            if (value := _var(sub, "tick")) is not None:
                tick_delivered[token] = value
        return {
            "event": f"{client}.{handler}({', '.join(map(str, payload.values()))})",
            "recomputed_for": sorted(set(RECOMPUTED_FOR)),
            "whoami_delivered": whoami_delivered,
            "tick_delivered": tick_delivered,
        }


def _check_whoami(rows: list[dict[str, Any]]) -> bool:
    """Print the recompute-vs-deliver table and return whether the invariant held.

    Args:
        rows: The per-event records produced by ``Driver.send``.

    Returns:
        True if every recomputation was delivered to the client it was computed for.
    """
    print("CHECK 1 -- router-dependent computed var on the linked SharedState")
    print(f"\n  {'event':<28} {'whoami recomputed for':<30} whoami delivered to")
    print("  " + "-" * 92)
    ok = True
    for row in rows:
        recomputed = ", ".join(row["recomputed_for"]) or "-"
        delivered = (
            ", ".join(f"{k}={v!r}" for k, v in sorted(row["whoami_delivered"].items()))
            or "NOTHING"
        )
        print(f"  {row['event']:<28} {recomputed:<30} {delivered}")
        ok = ok and all(t in row["whoami_delivered"] for t in row["recomputed_for"])
    return ok


def _check_tick(rows: list[dict[str, Any]], driver: Driver) -> bool:
    """Print the interval-var table and return whether refreshes reached the frontend.

    Args:
        rows: The per-event records produced by ``Driver.send``.
        driver: The driver holding each client's screen contents.

    Returns:
        True if the interval var advanced on screen.
    """
    print(
        f"\n\nCHECK 2 -- @rx.var(interval={TICK_INTERVAL.total_seconds():g}s) on the same "
        "SharedState (events are spaced past the interval)"
    )
    print(f"\n  {'event':<28} tick delivered to")
    print("  " + "-" * 92)
    for row in rows:
        delivered = (
            ", ".join(f"{k}={v!r}" for k, v in sorted(row["tick_delivered"].items()))
            or "NOTHING"
        )
        print(f"  {row['event']:<28} {delivered}")
    shown = {c: _var(driver.screens[c], "tick") for c in CLIENTS}
    print(f"\n  tick currently on screen: {shown}")
    # Every `say` round is spaced past the interval, so the acting client must be told
    # the refreshed value each time.
    return all(
        row["event"].split(".")[1].startswith("join")
        or row["event"].split(".")[0] in row["tick_delivered"]
        for row in rows
    )


async def main() -> int:
    """Run the scenario and check both invariants.

    Returns:
        Process exit code.
    """
    driver = Driver()
    rows: list[dict[str, Any]] = []

    async with driver.processor:
        rows.extend([
            await driver.send(client, "join", token=SHARED_TOKEN) for client in CLIENTS
        ])
        for client in CLIENTS:
            # Sleep past the interval so `tick` is genuinely expired each round.
            await asyncio.sleep(TICK_INTERVAL.total_seconds() * 1.2)
            rows.append(await driver.send(client, "say", msg=f"hi from {client}"))

    whoami_ok = _check_whoami(rows)
    tick_ok = _check_tick(rows, driver)

    print()
    if whoami_ok and tick_ok:
        print(
            "PASS: every per-token recomputation was delivered to the client it was\n"
            "      computed for, and the interval var kept advancing on screen.\n"
            "      (This is the behaviour on current main.)"
        )
        return 0

    print(
        "FAIL: #6841 restores dirty_vars/dirty_substates for EVERY state in the tree,\n"
        "      not just the root's 'router'/'router_data'.  That throws away all the\n"
        "      dirtiness produced by the resolve it just performed.\n"
    )
    if not whoami_ok:
        print(
            "      CHECK 1: Room.whoami was still recomputed for each linked client on\n"
            "      every event -- exactly the work _patch_state's router dirtying exists\n"
            "      to force (#6392) -- but no client was told the result.  It is also gone\n"
            "      from _previous_dirty_vars, so it no longer propagates to the other\n"
            "      clients linked to the same token.  It survives the initial _link_to only\n"
            "      because _patch_state skips the snapshot entirely when full_delta=True.\n"
        )
    if not tick_ok:
        print(
            "      CHECK 2: the throwaway resolve *consumed* the expired interval var --\n"
            "      recomputing it reset its last_updated -- and then the restore dropped it\n"
            "      from the delta.  needs_update() is False by the time the real delta is\n"
            "      built, so the refreshed value never reaches the frontend.  The value on\n"
            "      screen is frozen at whatever the initial link delivered.\n"
        )
    print(
        "      Neither of these is covered by the PR's tests, which call _patch_state\n"
        "      directly on a two-state tree with no router-dependent vars and assert only\n"
        "      that the dirty sets come back unchanged -- i.e. they assert the mechanism\n"
        "      is disabled rather than that disabling it is safe."
    )
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
