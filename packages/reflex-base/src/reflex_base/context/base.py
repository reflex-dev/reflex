"""Shared contextvars wrapper for contextual globals."""

from __future__ import annotations

from contextvars import ContextVar, Token
from types import TracebackType
from typing import ClassVar

from typing_extensions import Self


class BaseContext:
    """Base context class that acts as a sync/async context manager for a per-subclass ContextVar.

    Each subclass gets its own :class:`ContextVar` and a class-level mapping from
    the ``id`` of each attached instance to its reset token, so any number of
    subclasses can be entered concurrently without interfering with each other,
    and instances with equal fields are attached independently.
    """

    __slots__ = ()

    _context_var: ClassVar[ContextVar[Self]]
    _attached_context_token: ClassVar[dict[int, Token[Self]]]

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Initialize the context variable and token registry for the subclass.

        Args:
            **kwargs: Forwarded to ``super().__init_subclass__``.
        """
        super().__init_subclass__(**kwargs)
        cls._context_var = ContextVar(cls.__name__)
        cls._attached_context_token = {}

    @classmethod
    def get(cls) -> Self:
        """Get the active context from the context variable.

        Returns:
            The active context instance.

        Raises:
            LookupError: If no context has been set for this class.
        """
        return cls._context_var.get()

    @classmethod
    def set(cls, context: Self) -> Token[Self]:
        """Set the active context in the context variable.

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
        """Attach this context to the current task.

        Returns:
            This context instance.

        Raises:
            RuntimeError: If this instance is already attached.
        """
        if id(self) in self._attached_context_token:
            msg = "Context is already attached, cannot enter context manager."
            raise RuntimeError(msg)
        self._attached_context_token[id(self)] = self._context_var.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Detach this context from the current task."""
        del exc_type, exc_val, exc_tb
        if (token := self._attached_context_token.pop(id(self), None)) is not None:
            self._context_var.reset(token)

    async def __aenter__(self) -> Self:
        """Attach this context to the current task asynchronously.

        Returns:
            This context instance.
        """
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Detach this context from the current task asynchronously."""
        self.__exit__(exc_type, exc_val, exc_tb)

    def ensure_context_attached(self) -> None:
        """Ensure that this instance is the active context in the current context.

        Raises:
            RuntimeError: If this instance is not the active context.
        """
        if self._context_var.get(None) is not self:
            msg = (
                f"{type(self).__name__} must be entered and active before calling "
                "this method."
            )
            raise RuntimeError(msg)
