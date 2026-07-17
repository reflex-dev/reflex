"""Per-event ambient context providers.

Some features need a context (e.g. a contextvar) active for the whole duration
of an event: during handler execution *and* during delta/computed-var
resolution, which happens after the handler. Middleware cannot express this
(its pre/post hooks are separate calls), so this module lets a feature register
a provider that yields a context manager entered around both phases.

The provider is called fresh at each phase, so a value it derives from state
(e.g. a locale a handler just changed) is re-read for delta resolution.

External packages register providers; the event processor enters them via
:func:`event_scope`. When nothing is registered, the fast path is a bare
``nullcontext`` so non-users pay effectively nothing.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reflex.state import BaseState

# A provider takes the root state and returns (async) a synchronous context
# manager to enter for the current event phase.
EventScopeProvider = Callable[
    ["BaseState"], Awaitable[contextlib.AbstractContextManager[None]]
]

_providers: list[EventScopeProvider] = []


def register_event_scope_provider(provider: EventScopeProvider) -> None:
    """Register a per-event ambient-context provider.

    Args:
        provider: An async callable taking the root state and returning a
            synchronous context manager to enter around handler execution and
            delta resolution.
    """
    _providers.append(provider)


def has_event_scope_providers() -> bool:
    """Whether any event-scope providers are registered.

    A cheap synchronous check so the processor can skip scope handling
    entirely when no feature uses it.

    Returns:
        True if at least one provider is registered.
    """
    return bool(_providers)


class _EventScope:
    """Async context manager entering every registered provider's scope."""

    __slots__ = ("_root_state", "_stack")

    def __init__(self, root_state: BaseState):
        self._root_state = root_state
        self._stack = contextlib.ExitStack()

    async def __aenter__(self) -> None:
        for provider in _providers:
            self._stack.enter_context(await provider(self._root_state))

    async def __aexit__(self, *exc_info: object) -> None:
        self._stack.close()


def event_scope(
    root_state: BaseState,
) -> contextlib.AbstractAsyncContextManager[None]:
    """Build the ambient-context scope for processing an event.

    Args:
        root_state: The client's root state instance.

    Returns:
        An async context manager entering every registered provider's scope,
        or a no-op context when none are registered.
    """
    if not _providers:
        return contextlib.nullcontext()
    return _EventScope(root_state)
