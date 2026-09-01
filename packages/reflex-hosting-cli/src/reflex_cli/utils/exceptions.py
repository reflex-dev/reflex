"""Custom Exceptions."""


class ReflexHostingCliError(Exception):
    """Base exception for all Reflex Hosting CLI exceptions."""


class NotAuthenticatedError(ReflexHostingCliError):
    """Raised when the user is not authenticated."""


class TokenValidationError(ReflexHostingCliError):
    """Raised when validating an access token with the control plane fails.

    Carries the X-Request-ID sent with the validation request so callers can
    surface it for correlation with server-side logs.
    """

    def __init__(self, message: str, request_id: str = ""):
        """Initialize the error.

        Args:
            message: The error message.
            request_id: The X-Request-ID header sent with the failed request.
        """
        super().__init__(message)
        self.request_id = request_id


class TokenAccessDeniedError(TokenValidationError, ValueError):
    """Raised when the control plane rejects the access token."""


class GetAppError(ReflexHostingCliError):
    """Raised when retrieving an app fails."""


class ScaleAppError(ReflexHostingCliError):
    """Raised when scaling an app fails."""


class ResponseError(ReflexHostingCliError):
    """Raised when a response is not as expected."""


class ArchiveUploadError(ReflexHostingCliError):
    """Raised when a build's archives cannot be uploaded to storage."""


class ConfigError(ReflexHostingCliError):
    """Raised when there is an error with the config."""


class ConfigInvalidFieldValueError(ReflexHostingCliError):
    """Raised when a field in the config has an invalid value."""


class ScaleTypeError(ReflexHostingCliError):
    """Raised when the scale type is invalid."""


class ScaleParamError(ReflexHostingCliError):
    """Raised when the scale parameter is invalid."""
