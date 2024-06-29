"""Custom Exceptions."""


class ReflexError(Exception):
    """Base exception for all Reflex exceptions."""


class ReflexRuntimeError(ReflexError, RuntimeError):
    """Custom RuntimeError for Reflex."""


class UploadTypeError(ReflexError, TypeError):
    """Custom TypeError for upload related errors."""


class EnvVarValueError(ReflexError, ValueError):
    """Custom ValueError raised when unable to convert env var to expected type."""


class ComponentTypeError(ReflexError, TypeError):
    """Custom TypeError for component related errors."""


class EventHandlerTypeError(ReflexError, TypeError):
    """Custom TypeError for event handler related errors."""


class EventHandlerValueError(ReflexError, ValueError):
    """Custom ValueError for event handler related errors."""


class StateValueError(ReflexError, ValueError):
    """Custom ValueError for state related errors."""


class VarNameError(ReflexError, NameError):
    """Custom NameError for when a state var has been shadowed by a substate var."""


class VarTypeError(ReflexError, TypeError):
    """Custom TypeError for var related errors."""


class VarValueError(ReflexError, ValueError):
    """Custom ValueError for var related errors."""


class VarAttributeError(ReflexError, AttributeError):
    """Custom AttributeError for var related errors."""


class UploadValueError(ReflexError, ValueError):
    """Custom ValueError for upload related errors."""


class RouteValueError(ReflexError, ValueError):
    """Custom ValueError for route related errors."""


class VarOperationTypeError(ReflexError, TypeError):
    """Custom TypeError for when unsupported operations are performed on vars."""


class VarDependencyError(ReflexError, ValueError):
    """Custom ValueError for when a var depends on a non-existent var."""


class InvalidStylePropError(ReflexError, TypeError):
    """Custom Type Error when style props have invalid values."""


class ImmutableStateError(ReflexError):
    """Raised when a background task attempts to modify state outside of context."""


class LockExpiredError(ReflexError):
    """Raised when the state lock expires while an event is being processed."""


class MatchTypeError(ReflexError, TypeError):
    """Raised when the return types of match cases are different."""
