"""Stand-ins for the outside world: CRM, chat, storage, and the rest.

Each call carries an idempotency key, the way a real provider's does. Calling
twice with the same key returns the first result instead of acting again, so an
example can be crashed, retried, and replayed the way the engine really does it,
and a test can still say how many contacts were created.
"""

from __future__ import annotations

import asyncio
import collections
import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True, slots=True)
class Call:
    """One attempt at an external action.

    Attributes:
        action: What was called, e.g. ``crm.upsert``.
        key: The idempotency key the caller used.
        payload: The arguments it was called with.
    """

    action: str
    key: str
    payload: dict[str, Any]


class ProviderError(Exception):
    """An external action that failed the way a provider's would."""


class World:
    """The external services an example talks to."""

    def __init__(self) -> None:
        """Start with nothing called and nothing failing."""
        self.calls: list[Call] = []
        self.records: dict[tuple[str, str], dict[str, Any]] = {}
        self.faults: collections.Counter[tuple[str, str | None]] = collections.Counter()
        self.gates: dict[tuple[str, str | None], asyncio.Event] = {}

    def reset(self) -> None:
        """Forget every call, record, and planned failure."""
        self.calls.clear()
        self.records.clear()
        self.faults.clear()
        for gate in self.gates.values():
            gate.set()
        self.gates.clear()

    def break_next(self, action: str, times: int = 1, key: str | None = None) -> None:
        """Make the next calls to an action fail.

        Args:
            action: The action to break.
            times: How many calls fail before it works again.
            key: Break only the calls carrying this key, rather than all of them.
        """
        self.faults[action, key] = times

    def hold(self, action: str, key: str | None = None) -> asyncio.Event:
        """Make calls to an action wait, as a slow provider's would, until released.

        Args:
            action: The action to hold.
            key: Hold only the calls carrying this key, rather than all of them.

        Returns:
            The event that releases them when set.
        """
        gate = self.gates[action, key] = asyncio.Event()
        return gate

    def attempts(self, action: str) -> int:
        """Count every call made to an action, including repeats.

        Args:
            action: The action.

        Returns:
            How many times it was called.
        """
        return sum(call.action == action for call in self.calls)

    def effects(self, action: str) -> list[dict[str, Any]]:
        """Return what an action actually did, once per distinct key.

        Args:
            action: The action.

        Returns:
            The stored result of each distinct key, in the order they happened.
        """
        return [record for (name, _), record in self.records.items() if name == action]

    def plan(self, action: str, key: str, result: dict[str, Any]) -> None:
        """Decide what an action will answer, before anything calls it.

        Args:
            action: The action, e.g. ``ocr.extract``.
            key: The key it will be called with.
            result: What it answers.
        """
        self.records[action, key] = result

    async def call(self, action: str, key: str, **payload: Any) -> dict[str, Any]:
        """Perform an external action, once per key.

        Args:
            action: What to call, e.g. ``crm.upsert``.
            key: The idempotency key; a repeat returns the first result.
            **payload: The arguments.

        Returns:
            The result, which is the first result when the key repeats.

        Raises:
            ProviderError: If the action has been broken for this call.
        """
        self.calls.append(Call(action, key, payload))
        for held in ((action, key), (action, None)):
            if (gate := self.gates.get(held)) is not None:
                await gate.wait()
        for fault in ((action, key), (action, None)):
            if self.faults[fault]:
                self.faults[fault] -= 1
                msg = f"{action} is unavailable"
                raise ProviderError(msg)
        stored = self.records.get((action, key))
        if stored is not None:
            return stored
        result = {
            "id": f"{action.replace('.', '-')}-{len(self.records) + 1}",
            **payload,
        }
        self.records[action, key] = result
        return result


# The examples and their tests share one world, reset between tests.
world = World()
