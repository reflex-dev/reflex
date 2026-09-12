"""Stub ``NameResolver``s for unit testing."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

from reflex_base.registry import NameResolver, RegistrationContext

from reflex.state import BaseState, State


def stub_resolver(
    *,
    state_name: str | None = None,
    target: type[BaseState] = State,
    handler_prefix: str | None = None,
) -> NameResolver:
    """Build a tiny one-off :class:`NameResolver`.

    Args:
        state_name: Override returned for ``target`` (else ``None``).
        target: Which state class the override scopes to.
        handler_prefix: When set, prefixes every handler name.

    Returns:
        A resolver with the requested behavior.
    """

    class _Stub:
        def resolve_state_name(self, state_cls):
            return state_name if state_cls is target else None

        def resolve_handler_name(self, state_cls, handler_name):
            return f"{handler_prefix}{handler_name}" if handler_prefix else None

    return _Stub()


@contextlib.contextmanager
def temporary_resolver(resolver: NameResolver) -> Iterator[RegistrationContext]:
    """Install ``resolver`` for the duration of the ``with`` block.

    Restoring matters: ``set_name_resolver`` clears the per-class name caches,
    so a resolver left installed leaks its names into later tests.

    Args:
        resolver: The resolver to install temporarily.

    Yields:
        The active registration context.
    """
    ctx = RegistrationContext.get()
    original = ctx.name_resolver
    try:
        ctx.set_name_resolver(resolver)
        yield ctx
    finally:
        ctx.set_name_resolver(original)
