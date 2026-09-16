"""Per-event ambient context providers (e.g. i18n locale).

A provider yields a context manager entered around both handler execution and
delta resolution; it is called fresh at each phase, so state a handler changed
is re-read. Middleware can't do this (separate pre/post calls). No registered
providers means a ``nullcontext`` fast path.
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
        provider: Async callable from root state to a context manager.
    """
    _providers.append(provider)


def has_event_scope_providers() -> bool:
    """Whether any event-scope providers are registered.

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
        # ``async with`` only calls ``__aexit__`` if ``__aenter__`` returns, so
        # a provider raising mid-loop would otherwise leak the contexts already
        # entered (e.g. an earlier provider's contextvar token).
        try:
            for provider in _providers:
                self._stack.enter_context(await provider(self._root_state))
        except BaseException:
            self._stack.close()
            raise

    async def __aexit__(self, *exc_info: object) -> None:
        self._stack.close()


def event_scope(
    root_state: BaseState,
) -> contextlib.AbstractAsyncContextManager[None]:
    """Ambient-context scope for processing an event.

    Args:
        root_state: The client's root state instance.

    Returns:
        A scope entering every provider, or a no-op when none are registered.
    """
    if not _providers:
        return contextlib.nullcontext()
    return _EventScope(root_state)
