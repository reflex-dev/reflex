"""Custom Exceptions."""


class ReflexHostingCliError(Exception):
    """Base exception for all Reflex Hosting CLI exceptions."""


class NotAuthenticatedError(ReflexHostingCliError):
    """Raised when the user is not authenticated."""


class GetAppError(ReflexHostingCliError):
    """Raised when retrieving an app fails."""


class ScaleAppError(ReflexHostingCliError):
    """Raised when scaling an app fails."""


class ResponseError(ReflexHostingCliError):
    """Raised when a response is not as expected."""


class ConfigError(ReflexHostingCliError):
    """Raised when there is an error with the config."""


class ConfigInvalidFieldValueError(ReflexHostingCliError):
    """Raised when a field in the config has an invalid value."""


class ScaleTypeError(ReflexHostingCliError):
    """Raised when the scale type is invalid."""


class ScaleParamError(ReflexHostingCliError):
    """Raised when the scale parameter is invalid."""
