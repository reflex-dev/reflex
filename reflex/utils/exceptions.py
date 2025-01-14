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


class VarAnnotationError(ReflexError, TypeError):
    """Custom AttributeError for var annotation related errors."""

    def __init__(self, var_name, annotation_value):
        """Initialize the VarAnnotationError.

        Args:
            var_name: The name of the var.
            annotation_value: The value of the annotation.
        """
        super().__init__(
            f"Invalid annotation '{annotation_value}' for var '{var_name}'."
        )


class MismatchedArgumentTypeError(ReflexError, TypeError):
    """Custom TypeError for mismatched argument type errors."""

    def __init__(self, value, field_name, expected_type):
        """Initialize the MismatchedArgumentError.

        Args:
            value: The name of the argument received.
            field_name: The expected argument name.
            expected_type: The expected argument type.
        """
        super().__init__(
            f"Expected field '{field_name}' to receive type '{expected_type}', but got '{value}' of type '{type(value)}'."
        )


class MismatchedComputedVarReturn(ReflexError, TypeError):
    """Custom TypeError for mismatched computed var return type errors."""

    def __init__(self, var_name, return_type, expected_type):
        """Initialize the MismatchedComputedVarReturn.

        Args:
            var_name: The name of the computed var.
            return_type: The return type of the computed var.
            expected_type: The expected return type.
        """
        super().__init__(
            f"Computed var '{var_name}' must return type '{expected_type}', got '{return_type}'."
        )


class UntypedComputedVarError(ReflexError, TypeError):
    """Custom TypeError for untyped computed var errors."""

    def __init__(self, var_name):
        """Initialize the UntypedComputedVarError.

        Args:
            var_name: The name of the computed var.
        """
        super().__init__(f"Computed var '{var_name}' must have a type annotation.")


class UploadValueError(ReflexError, ValueError):
    """Custom ValueError for upload related errors."""


class PageValueError(ReflexError, ValueError):
    """Custom ValueError for page related errors."""


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


class StateSerializationError(ReflexError):
    """Raised when the state cannot be serialized."""


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


class InvalidLockWarningThresholdError(ReflexError):
    """Raised when an invalid lock warning threshold is provided."""


class UnretrievableVarValueError(ReflexError):
    """Raised when the value of a var is not retrievable."""
