"""What a durable handler can learn about the attempt it is running in.

A handler is a plain method: it takes its payload and returns its transition,
and nothing about the engine leaks into that signature. But some things a
handler legitimately needs -- a correlation id for its logs, a stable
idempotency key for an outbound HTTP call, a link that addresses this run --
are properties of the attempt rather than of the payload. They are exposed
here instead of being threaded through every handler.

The context is per-attempt and never spans one: reading it outside a durable
handler returns None rather than a stale value from a previous step.
"""

from __future__ import annotations

import dataclasses
import hashlib
from contextvars import ContextVar, Token


@dataclasses.dataclass(frozen=True, slots=True)
class RunContext:
    """Identity of the attempt a durable handler is running in.

    Attributes:
        run_id: The run this attempt belongs to.
        workflow_id: The stable workflow identity.
        ordinal: The mailbox slot being executed.
        handler_id: The handler this slot names.
        attempt: Which attempt this is, counting from one.
        epoch: The claim fence for this attempt.
    """

    run_id: str
    workflow_id: str
    ordinal: int
    handler_id: str
    attempt: int
    epoch: int

    def idempotency_key(self, *, scope: str = "") -> str:
        """Derive a stable key for an outbound call made by this step.

        Every retry of a step is the *same* logical work, so the key must not
        change between attempts -- that is the whole point of handing it to a
        payment or messaging API. It does change when the step changes, so two
        different steps of one run never collide.

        Args:
            scope: Distinguishes several calls made by one handler.

        Returns:
            A hex key, stable across retries of this step.
        """
        material = f"{self.run_id}:{self.ordinal}:{self.handler_id}:{scope}"
        return hashlib.sha256(material.encode()).hexdigest()[:32]


_current: ContextVar[RunContext | None] = ContextVar(
    "reflex_workflow_run_context", default=None
)


def current_run() -> RunContext | None:
    """Read the attempt this code is running in.

    Returns:
        The context, or None outside a durable handler.
    """
    return _current.get()


def require_run(reason: str) -> RunContext:
    """Read the current attempt, refusing to continue without one.

    Args:
        reason: What the caller needed the context for, used in the message.

    Returns:
        The context.

    Raises:
        WorkflowRuntimeError: If called outside a durable handler.
    """
    from reflex_base.utils.exceptions import WorkflowRuntimeError

    context = _current.get()
    if context is None:
        msg = (
            f"{reason} needs the run it belongs to, and there is no durable "
            "handler running. Call it from inside a @rx.event(durable=True) "
            "handler."
        )
        raise WorkflowRuntimeError(msg)
    return context


def bind_run(context: RunContext) -> Token[RunContext | None]:
    """Install a run context for the duration of one attempt.

    Args:
        context: The attempt's identity.

    Returns:
        The token that restores the previous context.
    """
    return _current.set(context)


def unbind_run(token: Token[RunContext | None]) -> None:
    """Restore the context that was in place before an attempt.

    Args:
        token: The token returned by ``bind_run``.
    """
    _current.reset(token)
