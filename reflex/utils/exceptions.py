"""Custom Exceptions."""


class ReflexError(Exception):
    """Base exception for all Reflex exceptions."""


class InvalidStylePropError(ReflexError, TypeError):
    """Custom Type Error when style props have invalid values."""

    pass


class ImmutableStateError(ReflexError):
    """Raised when a background task attempts to modify state outside of context."""


class LockExpiredError(ReflexError):
    """Raised when the state lock expires while an event is being processed."""


class MatchTypeError(ReflexError, TypeError):
    """Raised when the return types of match cases are different."""

    pass
