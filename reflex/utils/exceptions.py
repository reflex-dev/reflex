"""Custom Exceptions."""

from typing import NoReturn


class ReflexError(Exception):
    """Base exception for all Reflex exceptions."""


class ConfigError(ReflexError):
    """Custom exception for config related errors."""


class InvalidStateManagerMode(ReflexError, ValueError):
    """Raised when an invalid state manager mode is provided."""


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


class EventHandlerArgTypeMismatch(ReflexError, TypeError):
    """Raised when the annotations of args accepted by an EventHandler differs from the spec of the event trigger."""


class EventFnArgMismatch(ReflexError, TypeError):
    """Raised when the number of args required by an event handler is more than provided by the event trigger."""


class DynamicRouteArgShadowsStateVar(ReflexError, NameError):
    """Raised when a dynamic route arg shadows a state var."""


class ComputedVarShadowsStateVar(ReflexError, NameError):
    """Raised when a computed var shadows a state var."""


class ComputedVarShadowsBaseVars(ReflexError, NameError):
    """Raised when a computed var shadows a base var."""


class EventHandlerShadowsBuiltInStateMethod(ReflexError, NameError):
    """Raised when an event handler shadows a built-in state method."""


class GeneratedCodeHasNoFunctionDefs(ReflexError):
    """Raised when refactored code generated with flexgen has no functions defined."""


class PrimitiveUnserializableToJSON(ReflexError, ValueError):
    """Raised when a primitive type is unserializable to JSON. Usually with NaN and Infinity."""


class InvalidLifespanTaskType(ReflexError, TypeError):
    """Raised when an invalid task type is registered as a lifespan task."""


class DynamicComponentMissingLibrary(ReflexError, ValueError):
    """Raised when a dynamic component is missing a library."""


class SetUndefinedStateVarError(ReflexError, AttributeError):
    """Raised when setting the value of a var without first declaring it."""


class StateSchemaMismatchError(ReflexError, TypeError):
    """Raised when the serialized schema of a state class does not match the current schema."""


class EnvironmentVarValueError(ReflexError, ValueError):
    """Raised when an environment variable is set to an invalid value."""


class DynamicComponentInvalidSignature(ReflexError, TypeError):
    """Raised when a dynamic component has an invalid signature."""


class InvalidPropValueError(ReflexError):
    """Raised when a prop value is invalid."""


class StateTooLargeError(ReflexError):
    """Raised when the state is too large to be serialized."""


class SystemPackageMissingError(ReflexError):
    """Raised when a system package is missing."""


def raise_system_package_missing_error(package: str) -> NoReturn:
    """Raise a SystemPackageMissingError.

    Args:
        package: The name of the missing system package.

    Raises:
        SystemPackageMissingError: The raised exception.
    """
    from reflex.constants import IS_MACOS

    raise SystemPackageMissingError(
        f"System package '{package}' is missing."
        " Please install it through your system package manager."
        + (f" You can do so by running 'brew install {package}'." if IS_MACOS else "")
    )
