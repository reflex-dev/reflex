"""Custom Exceptions."""


class InvalidStylePropError(TypeError):
    """Custom Type Error when style props have invalid values."""

    pass


class ImmutableStateError(AttributeError):
    """Raised when a background task attempts to modify state outside of context."""


class LockExpiredError(Exception):
    """Raised when the state lock expires while an event is being processed."""


class MatchTypeError(TypeError):
    """Raised when the return types of match cases are different."""

    pass
