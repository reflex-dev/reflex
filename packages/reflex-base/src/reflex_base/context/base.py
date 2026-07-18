"""Shared contextvars wrapper for contextual globals."""

from __future__ import annotations

import dataclasses
from contextvars import ContextVar, Token
from typing import ClassVar

from typing_extensions import Self


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class BaseContext:
    """Base context class that acts as an async context manager to set the context var."""

    _context_var: ClassVar[ContextVar[Self]]
    _attached_context_token: ClassVar[dict[Self, Token[Self]]]

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Initialize the context variable for the subclass."""
        super(BaseContext, cls).__init_subclass__(**kwargs)
        cls._context_var = ContextVar(cls.__name__)
        cls._attached_context_token = {}

    @classmethod
    def get(cls) -> Self:
        """Get the context from the context variable.

        Returns:
            The context instance.
        """
        return cls._context_var.get()

    @classmethod
    def set(cls, context: Self) -> Token[Self]:
        """Set the context in the context variable.

        Args:
            context: The context instance to set.

        Returns:
            The token for resetting the context variable.
        """
        return cls._context_var.set(context)

    @classmethod
    def reset(cls, token: Token[Self]) -> None:
        """Reset the context variable to a previous state.

        Args:
            token: The token to reset the context variable to.
        """
        cls._context_var.reset(token)

    def __enter__(self) -> Self:
        """Enter the context.

        Returns:
            This context instance.
        """
        if self._attached_context_token.get(self) is not None:
            msg = "Context is already attached, cannot enter context manager."
            raise RuntimeError(msg)
        self._attached_context_token[self] = self._context_var.set(self)
        return self

    def __exit__(self, *exc_info):
        """Exit the context."""
        if (token := self._attached_context_token.pop(self)) is not None:
            self._context_var.reset(token)

    def ensure_context_attached(self):
        """Ensure that the context is attached to the current context variable.

        Raises:
            RuntimeError: If the context is not attached.
        """
        if self._attached_context_token.get(self) is None:
            msg = f"{type(self).__name__} must be entered before calling this method."
            raise RuntimeError(msg)
