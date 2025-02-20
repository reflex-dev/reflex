"""Custom Exceptions."""

from typing import Any


class ReflexError(Exception):
    """Base exception for all Reflex exceptions."""


class ConfigError(ReflexError):
    """Custom exception for config related errors."""


class InvalidStateManagerModeError(ReflexError, ValueError):
    """Raised when an invalid state manager mode is provided."""


class ReflexRuntimeError(ReflexError, RuntimeError):
    """Custom RuntimeError for Reflex."""


class UploadTypeError(ReflexError, TypeError):
    """Custom TypeError for upload related errors."""


class EnvVarValueError(ReflexError, ValueError):
    """Custom ValueError raised when unable to convert env var to expected type."""


class ComponentTypeError(ReflexError, TypeError):
    """Custom TypeError for component related errors."""


class ChildrenTypeError(ComponentTypeError):
    """Raised when the children prop of a component is not a valid type."""

    def __init__(self, component: str, child: Any):
        """Initialize the exception.

        Args:
            component: The name of the component.
            child: The child that caused the error.
        """
        super().__init__(
            f"Component {component} received child {child} of type {type(child)}. "
            "Accepted types are other components, state vars, or primitive Python types (dict excluded)."
        )


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


class UntypedVarError(ReflexError, TypeError):
    """Custom TypeError for untyped var errors."""


class UntypedComputedVarError(ReflexError, TypeError):
    """Custom TypeError for untyped computed var errors."""

    def __init__(self, var_name: str):
        """Initialize the UntypedComputedVarError.

        Args:
            var_name: The name of the computed var.
        """
        super().__init__(f"Computed var '{var_name}' must have a type annotation.")


class ComputedVarSignatureError(ReflexError, TypeError):
    """Custom TypeError for computed var signature errors."""

    def __init__(self, var_name: str, signature: str):
        """Initialize the ComputedVarSignatureError.

        Args:
            var_name: The name of the var.
            signature: The invalid signature.
        """
        super().__init__(f"Computed var `{var_name}{signature}` cannot take arguments.")


class MissingAnnotationError(ReflexError, TypeError):
    """Custom TypeError for missing annotations."""

    def __init__(self, var_name: str):
        """Initialize the MissingAnnotationError.

        Args:
            var_name: The name of the var.
        """
        super().__init__(f"Var '{var_name}' must have a type annotation.")


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


class EventHandlerArgTypeMismatchError(ReflexError, TypeError):
    """Raised when the annotations of args accepted by an EventHandler differs from the spec of the event trigger."""


class EventFnArgMismatchError(ReflexError, TypeError):
    """Raised when the number of args required by an event handler is more than provided by the event trigger."""


class DynamicRouteArgShadowsStateVarError(ReflexError, NameError):
    """Raised when a dynamic route arg shadows a state var."""


class ComputedVarShadowsStateVarError(ReflexError, NameError):
    """Raised when a computed var shadows a state var."""


class ComputedVarShadowsBaseVarsError(ReflexError, NameError):
    """Raised when a computed var shadows a base var."""


class EventHandlerShadowsBuiltInStateMethodError(ReflexError, NameError):
    """Raised when an event handler shadows a built-in state method."""


class GeneratedCodeHasNoFunctionDefsError(ReflexError):
    """Raised when refactored code generated with flexgen has no functions defined."""


class PrimitiveUnserializableToJSONError(ReflexError, ValueError):
    """Raised when a primitive type is unserializable to JSON. Usually with NaN and Infinity."""


class InvalidLifespanTaskTypeError(ReflexError, TypeError):
    """Raised when an invalid task type is registered as a lifespan task."""


class DynamicComponentMissingLibraryError(ReflexError, ValueError):
    """Raised when a dynamic component is missing a library."""


class SetUndefinedStateVarError(ReflexError, AttributeError):
    """Raised when setting the value of a var without first declaring it."""


class StateSchemaMismatchError(ReflexError, TypeError):
    """Raised when the serialized schema of a state class does not match the current schema."""


class EnvironmentVarValueError(ReflexError, ValueError):
    """Raised when an environment variable is set to an invalid value."""


class DynamicComponentInvalidSignatureError(ReflexError, TypeError):
    """Raised when a dynamic component has an invalid signature."""


class InvalidPropValueError(ReflexError):
    """Raised when a prop value is invalid."""


class StateTooLargeError(ReflexError):
    """Raised when the state is too large to be serialized."""


class StateSerializationError(ReflexError):
    """Raised when the state cannot be serialized."""


class StateMismatchError(ReflexError, ValueError):
    """Raised when the state retrieved does not match the expected state."""


class SystemPackageMissingError(ReflexError):
    """Raised when a system package is missing."""

    def __init__(self, package: str):
        """Initialize the SystemPackageMissingError.

        Args:
            package: The missing package.
        """
        from reflex.constants import IS_MACOS

        extra = (
            f" You can do so by running 'brew install {package}'." if IS_MACOS else ""
        )
        super().__init__(
            f"System package '{package}' is missing."
            f" Please install it through your system package manager.{extra}"
        )


class EventDeserializationError(ReflexError, ValueError):
    """Raised when an event cannot be deserialized."""


class InvalidLockWarningThresholdError(ReflexError):
    """Raised when an invalid lock warning threshold is provided."""


class UnretrievableVarValueError(ReflexError):
    """Raised when the value of a var is not retrievable."""
