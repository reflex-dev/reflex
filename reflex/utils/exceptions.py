"""Custom Exceptions."""


class ReflexError(Exception):
    """Base exception for all Reflex exceptions."""

    def __init__(self, message: str, analytics_enabled: bool = False) -> None:
        """Custom constructor. If analytics enabled, send telemetry.

        Args:
            message: the exception message
            analytics_enabled: whether to include this exception when telemetry is enabled.
        """
        from reflex.utils import telemetry

        if analytics_enabled:
            telemetry.send("error", context="backend", message=message)
        super().__init__(message)


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
