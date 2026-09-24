"""Hosting service related utilities.

The Reflex Build API is reached through ``reflex-build-sdk``; what lives here is
the part that is the CLI's own -- resolving names interactively, reading the
config files, driving the browser login, and turning the SDK's typed results
into what the commands print.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
import webbrowser
from collections.abc import Iterator, Mapping
from enum import Enum
from http import HTTPStatus
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any, NoReturn, TypedDict

import click
from reflex_build_sdk import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AuthenticationError,
    DeploymentFailedError,
    LoginDeniedError,
    LoginTimeoutError,
    MissingTokenError,
    NotFoundError,
    ReflexBuild,
    ReflexBuildError,
)
from reflex_build_sdk._decode import json_key
from reflex_build_sdk._deploy import status_message_outcome
from reflex_build_sdk.types import DeploymentReport, LoginRequest, Me

import reflex_cli.constants as constants
from reflex_cli.core.config import Config, RegionOption
from reflex_cli.utils import console, log
from reflex_cli.utils.dependency import is_valid_url
from reflex_cli.utils.exceptions import (
    ResponseError,
    ScaleAppError,
    ScaleParamError,
    TokenAccessDeniedError,
    TokenValidationError,
)

if TYPE_CHECKING:
    from reflex_build_sdk.types import AppSummary, GcpConnection, GcpStatus, ProjectRef

logger = logging.getLogger(__name__)

# The archives `reflex export` produces, which a deployment is built from.
BACKEND_ARCHIVE = "backend.zip"
FRONTEND_ARCHIVE = "frontend.zip"

# Per socket operation on an upload, not per upload. A link that cannot move one
# chunk in this long -- roughly 17 kbps -- cannot finish an upload inside the
# window its signature was issued for either.
UPLOAD_IO_TIMEOUT = datetime.timedelta(minutes=2)


class ScaleType(str, Enum):
    """The scale type for an application."""

    SIZE = "size"
    REGION = "region"


@dataclasses.dataclass
class ScaleAppCliArgs:
    """CLI arguments for scaling an application."""

    type: ScaleType | None = None
    regions: dict[str, int] | None = None
    vm_type: str | None = None

    @classmethod
    def create(
        cls,
        regions: list[str] | dict[str, int] | None = None,
        vm_type: str | None = None,
        scale_type: ScaleType | str | None = None,
    ) -> ScaleAppCliArgs:
        """Create a ScaleAppCliArgs object.

        Args:
            regions: The regions to scale to.
            vm_type: The VM size to scale to.
            scale_type: The scale type.

        Returns:
            An instance of ScaleAppCliArgs.

        Raises:
            ScaleAppError: If both regions and vm_type are provided.

        """
        if isinstance(regions, list):
            regions = dict.fromkeys(regions, 1)

        if vm_type is not None and regions:
            raise ScaleAppError("Only one of --vmtype or --regions should be provided.")
        return cls(ScaleType(scale_type) if scale_type else None, regions, vm_type)

    @property
    def is_valid(self) -> bool:
        """Check if the CLI arguments are valid.

        Returns:
            bool: True if either vmtype or regions is set.

        """
        return bool(self.regions or self.vm_type)


class Region(TypedDict):
    """Region for scaling an application."""

    name: RegionOption
    number_of_machines: int


@dataclasses.dataclass
class ScaleParams:
    """Parameters for scaling an application."""

    type: ScaleType | None = None
    vm_type: str | None = None
    regions: tuple[Region, ...] = ()

    @classmethod
    def create(
        cls,
        scale_type: ScaleType | None = None,
        vm_type: str | None = None,
        regions: list[RegionOption] | Mapping[RegionOption, int] | None = None,
    ):
        """Create a ScaleParams object.

        Args:
            scale_type: The scale type.
            vm_type: The VM type to scale to.
            regions: The regions to scale to.

        Returns:
            ScaleParams: The created ScaleParams object.

        """
        if isinstance(regions, list):
            regions = dict.fromkeys(regions, 1)
        return cls(
            scale_type,
            vm_type,
            tuple(
                Region(name=name, number_of_machines=number)
                for name, number in regions.items()
            )
            if regions
            else (),
        )

    @classmethod
    def from_config(cls, config: Config) -> ScaleParams:
        """Create a ScaleParams object from a Config object.

        Args:
            config: The Config object.

        Returns:
            The created ScaleParams object.

        """
        return cls.create(
            vm_type=config.vmtype,
            regions={**config.regions} if config.regions else None,
        )

    def set_type(self, scale_type: ScaleType | str | None) -> ScaleParams:
        """Set the scale type.

        Args:
            scale_type: The scale type.

        Returns:
            The ScaleParams object with the scale type set.

        """
        return ScaleParams(
            ScaleType(scale_type) if scale_type else None, self.vm_type, self.regions
        )

    def set_type_from_cli_args(self, cli_args: ScaleAppCliArgs) -> ScaleParams:
        """Set the scale type from CLI arguments.

        Args:
            cli_args: The CLI arguments.

        Returns:
            The ScaleParams object with the scale type set.

        Raises:
            ScaleParamError: If the scale type is not provided when using cloud.yml or pyproject.toml.

        """
        scale_type = cli_args.type

        if scale_type is None and not cli_args.is_valid:
            raise ScaleParamError(
                "specify the type of scaling using --scale-type when using cloud.yml or pyproject.toml"
            )

        if scale_type is not None and cli_args.is_valid:
            logger.warning(
                "using --scale-type with --regions or --vmtype will have no effect"
            )

        if not cli_args.is_valid:
            if scale_type == ScaleType.SIZE and not cli_args.vm_type:
                raise ScaleParamError(
                    f"'vmtype' should be provided in the {constants.Dirs.CLOUD_YAML} for size scaling"
                )

            if scale_type == ScaleType.REGION and not cli_args.regions:
                raise ScaleParamError(
                    f"'regions' should be provided in the {constants.Dirs.CLOUD_YAML} for region scaling"
                )

        if cli_args.is_valid:
            return self.set_type(
                ScaleType(ScaleType.REGION)
                if cli_args.regions
                else ScaleType(ScaleType.SIZE)
            )
        return self.set_type(ScaleType(scale_type) if scale_type else None)

    def as_scale_arguments(self) -> dict[str, Any]:
        """Convert the parameters to the keyword arguments ``apps.scale`` takes.

        Returns:
            Either the machine size to run, or how many machines to run per region.

        """
        effective_type = self.type or ScaleType.REGION
        if effective_type == ScaleType.SIZE:
            return {"vm_type": self.vm_type}
        return {
            "regions": {
                region["name"]: region["number_of_machines"] for region in self.regions
            }
        }


@dataclasses.dataclass(frozen=True)
class AuthenticatedClient:
    """A Reflex Build client, and the identity its access token authenticates as."""

    api: ReflexBuild
    me: Me

    @property
    def token(self) -> str:
        """The access token the client sends.

        Returns:
            The access token.

        """
        return self.api.token or ""

    def close(self) -> None:
        """Release the connections the client holds."""
        self.api.close()


def as_json_document(value: Any) -> Any:
    """Render an SDK result as the plain data a ``--json`` document is made of.

    Dataclasses become objects under the API's own field names, and ids and
    timestamps the strings it sent, so a document keeps the shape it had when
    the CLI printed response bodies straight through.

    Args:
        value: The value to render.

    Returns:
        The value as lists, dicts and scalars.

    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            json_key(field): as_json_document(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {key: as_json_document(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_json_document(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def error_message(error: Exception) -> str:
    """Say what went wrong, the way the API put it where it said anything.

    ``str`` on a status error prefixes the API's explanation with the status
    line, which is noise in a message the user reads in place of an exception.

    Args:
        error: The error raised by the SDK.

    Returns:
        The API's explanation, or the error itself.

    """
    if isinstance(error, APIStatusError) and isinstance(error.detail, str):
        # A refusal the API sent no body with has nothing to say; its status
        # line is what is left, and it beats an empty message.
        return error.detail or str(error)
    return str(error)


@contextlib.contextmanager
def reporting_api_errors() -> Iterator[None]:
    """Report what the Reflex Build API refused, and exit, instead of raising.

    A command's body is wrapped in this so a refusal reads as the sentence the
    API wrote rather than a traceback, and so an expired or revoked token says
    what to do about it wherever it turns up -- not only where the command
    started by authenticating.

    Yields:
        To the command's body.

    Raises:
        Exit: If the API refused, or could not be reached.

    """
    try:
        yield
    except (AuthenticationError, MissingTokenError) as ex:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from ex
    except ReflexBuildError as ex:
        logger.error(error_message(ex))
        raise click.exceptions.Exit(1) from ex


def exit_reporting(error: ReflexBuildError, message: str) -> NoReturn:
    """Report a refused request in the caller's words, and exit.

    A token that will not authenticate is reported as itself instead: it has
    the same answer wherever it turns up, and the caller's wording -- "the
    deployment failed", "set full deploy failed" -- buries it.

    Args:
        error: The error the SDK raised.
        message: What to report for anything but an unusable token.

    Raises:
        Exit: Always.

    """
    if isinstance(error, (AuthenticationError, MissingTokenError)):
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
    else:
        logger.error(message)
    raise click.exceptions.Exit(1) from error


class SilentBackgroundBrowser(webbrowser.BackgroundBrowser):
    """A webbrowser.BackgroundBrowser that does not raise exceptions when it fails to open a browser."""

    def open(self, url: str, new: int = 0, autoraise: bool = True):
        """Open url in a new browser window.

        Args:
            url: The URL to open.
            new: Whether to open in a new window (2), tab (1), or the same tab (0).
            autoraise: Whether to raise the window.

        Returns:
            bool: True if the URL was opened successfully, False otherwise.

        """
        cmdline = [self.name] + [arg.replace("%s", url) for arg in self.args]
        sys.audit("webbrowser.open", url)
        try:
            if sys.platform[:3] == "win":
                p = subprocess.Popen(
                    cmdline, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                p = subprocess.Popen(
                    cmdline,
                    close_fds=True,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return p.poll() is None
        except OSError:
            return False


webbrowser.BackgroundBrowser = SilentBackgroundBrowser


class TokenSource(str, Enum):
    """Where an access token was loaded from."""

    CONFIG = "config file"
    ENVIRONMENT = "REFLEX_ACCESS_TOKEN environment variable"
    OPTION = "--token option"
    NONE = "none"


def get_existing_access_token_with_source() -> tuple[str, TokenSource]:
    """Fetch the access token from the environment or existing config, and say where it came from.

    ``REFLEX_ACCESS_TOKEN`` takes precedence: exporting it is an explicit
    choice for this invocation, while the config file is ambient state left
    behind by an earlier ``reflex login``.

    Returns:
        The access token and the source it was loaded from.
        If not found, return empty string and ``TokenSource.NONE`` instead.

    """
    access_token = os.environ.get("REFLEX_ACCESS_TOKEN", "")
    if access_token:
        logger.debug("Using REFLEX_ACCESS_TOKEN from environment")
        return access_token, TokenSource.ENVIRONMENT

    logger.debug("Fetching token from existing config...")
    try:
        access_token = stored_access_token()
    except (OSError, ValueError) as ex:
        logger.debug(
            f"Unable to fetch token from {constants.Hosting.HOSTING_JSON} due to: {ex}"
        )
        return "", TokenSource.NONE

    if access_token:
        return access_token, TokenSource.CONFIG

    return "", TokenSource.NONE


def rejected_token_message(source: TokenSource, err: TokenValidationError) -> str:
    """Describe a token the control plane would not validate.

    Args:
        source: Where the token was loaded from.
        err: The validation error.

    Returns:
        The message to report.
    """
    return (
        f"The access token from the {source.value} was rejected: {err} "
        f"(auth request id: {err.request_id})"
    )


def get_existing_access_token() -> str:
    """Fetch the access token from the existing config if applicable.

    Returns:
        The access token.
        If not found, return empty string for it instead.

    """
    return get_existing_access_token_with_source()[0]


def is_reflex_enterprise_installed() -> bool:
    """Check if reflex-enterprise is installed.

    Returns:
        True if reflex-enterprise is installed, False otherwise.
    """
    import importlib.metadata

    try:
        importlib.metadata.version("reflex-enterprise")
    except importlib.metadata.PackageNotFoundError:
        return False
    except Exception:
        return False
    else:
        return True


_last_auth_request_id: str = ""


def get_auth_request_id() -> str:
    """Get the request id sent with the most recent token validation request.

    The id is sent to the control plane as the ``X-Request-ID`` header, so it
    can be quoted to support to correlate a failed authentication with the
    server-side logs.

    Returns:
        The request id of the last ``validate_token`` call, or an empty string
        if no validation request has been made in this process.

    """
    return _last_auth_request_id


def _read_hosting_config() -> dict[str, Any]:
    """Read the hosting config file.

    A config that exists but cannot be read is reported rather than treated as
    empty, so callers do not overwrite entries they were unable to see.

    Returns:
        The stored config, or an empty dict if the file does not exist.

    Raises:
        OSError: If the config exists but cannot be read.
        ValueError: If the config exists but does not hold a JSON object.

    """
    try:
        with constants.Hosting.HOSTING_JSON.open(encoding="utf-8") as config_file:
            hosting_config = json.load(config_file)
    except FileNotFoundError:
        return {}
    # Valid JSON is not necessarily the object every caller indexes into.
    if not isinstance(hosting_config, dict):
        msg = f"{constants.Hosting.HOSTING_JSON} does not hold a JSON object"
        raise ValueError(msg)
    return hosting_config


def stored_access_token() -> str:
    """Read the access token held in the config file.

    Unlike ``get_existing_access_token`` this ignores ``REFLEX_ACCESS_TOKEN``
    and reports read failures, so callers can tell "no token stored" apart from
    "cannot tell what is stored".

    Returns:
        The stored token, or an empty string if the config holds none.

    Raises:
        OSError: If the config exists but cannot be read.
        ValueError: If the config exists but does not hold valid JSON.

    """
    return _read_hosting_config().get("access_token", "")


def _write_hosting_config(hosting_config: dict[str, Any]):
    """Write the hosting config file atomically.

    The config is written to a temporary file alongside the target and moved
    into place, so a failed or interrupted write leaves the previous
    credentials intact rather than truncating them.

    Args:
        hosting_config: The config to persist.

    """
    target = constants.Hosting.HOSTING_JSON
    target.parent.mkdir(parents=True, exist_ok=True)
    # Close the handle before replacing: Windows cannot rename an open file.
    temp_fd, temp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as config_file:
            json.dump(hosting_config, config_file)
            config_file.flush()
            os.fsync(config_file.fileno())
        temp_path.replace(target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def delete_token_from_config():
    """Delete the invalid token from the config file if applicable."""
    if constants.Hosting.HOSTING_JSON.exists():
        try:
            hosting_config = _read_hosting_config()
            hosting_config.pop("access_token", None)
            _write_hosting_config(hosting_config)
        except Exception as ex:
            # Best efforts removing invalid token is OK
            logger.debug(
                f"Unable to delete the invalid token from config file, err: {ex}"
            )
    # Delete the previous hosting service data if present. Best efforts, like
    # the rest of this function: the legacy file holds no token the CLI reads.
    try:
        constants.Hosting.HOSTING_JSON_V0.unlink(missing_ok=True)
    except OSError as ex:
        logger.debug(f"Unable to remove {constants.Hosting.HOSTING_JSON_V0}: {ex}")


def save_token_to_config(token: str):
    """Best efforts cache the token to the config file.

    Args:
        token: The access token to save.

    """
    try:
        try:
            hosting_config = _read_hosting_config()
        except (OSError, ValueError) as ex:
            # An unreadable config must not block re-authenticating; the token
            # is what makes the file useful, so start over from an empty one.
            logger.debug(
                f"Discarding unreadable {constants.Hosting.HOSTING_JSON}: {ex}"
            )
            hosting_config = {}
        hosting_config["access_token"] = token
        _write_hosting_config(hosting_config)
    except Exception as ex:
        logger.warning(
            f"Unable to save token to {constants.Hosting.HOSTING_JSON} due to: {ex}"
        )


def requires_access_token() -> str:
    """Fetch the access token from the existing config if applicable.

    Returns:
        The access token. If not found, return empty string for it instead.

    """
    # Check if the user is authenticated

    access_token = get_existing_access_token()
    if not access_token:
        logger.debug("No access token found from the existing config.")

    return access_token


def authenticated_token() -> tuple[str, dict[str, Any]]:
    """Fetch the access token from the existing config if applicable and validate it.

    Returns:
        The access token and validated user info.
        If not found, return empty string and dict for it instead.

    """
    # Check if the user is authenticated

    validated_info = {}
    access_token = get_existing_access_token()
    if access_token and not (
        validated_info := validate_token_with_retries(access_token)
    ):
        access_token = ""

    return access_token, validated_info


def requires_authenticated() -> str:
    """Check if the user is authenticated.

    Returns:
        The validated access token or empty string if not authenticated.

    """
    access_token, _ = authenticated_token()
    if access_token:
        return access_token
    access_token, _ = authenticate_on_browser()
    return access_token


def new_client(token: str | None = None) -> ReflexBuild:
    """Build a Reflex Build client that talks to the CLI's control plane.

    The URL is the CLI's own: the SDK reads ``REFLEX_BUILD_BACKEND_URL`` first,
    which ``reflex deploy`` does not, and only the CLI honours the legacy
    ``CP_BACKEND_URL``.

    Args:
        token: The access token to send, or None to use the one the environment
            or the config file holds.

    Returns:
        The client.

    """
    return ReflexBuild(
        token=token or get_existing_access_token() or None,
        base_url=constants.Hosting.HOSTING_SERVICE,
    )


def _validate(token: str, api: ReflexBuild | None = None) -> Me:
    """Ask the control plane who an access token authenticates as.

    Args:
        token: The access token to validate.
        api: The client to ask with. Defaults to one built for the call.

    Returns:
        The identity behind the token.

    Raises:
        TokenAccessDeniedError: If the token was refused.
        TokenValidationError: If the answer could not be had -- a timeout, a
            failed request, a server error. These are worth trying again.

    """
    global _last_auth_request_id
    source = "reflex-enterprise" if is_reflex_enterprise_installed() else "reflex"
    with contextlib.ExitStack() as stack:
        client = api if api is not None else stack.enter_context(new_client(token))
        try:
            return client.auth.me(source=source)
        except APIStatusError as ex:
            _last_auth_request_id = ex.request_id
            if ex.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                logger.debug(f"Access denied (request id: {ex.request_id})")
                raise TokenAccessDeniedError(
                    "access denied", request_id=ex.request_id
                ) from ex
            logger.debug(
                f"Unable to validate the token due to: {ex} (request id: {ex.request_id})"
            )
            raise TokenValidationError("server error", request_id=ex.request_id) from ex
        except APIError as ex:
            _last_auth_request_id = ex.request_id
            logger.debug(
                f"Request to auth server failed due to {ex} (request id: {ex.request_id})"
            )
            raise TokenValidationError(str(ex), request_id=ex.request_id) from ex


def identity_as_dict(me: Me) -> dict[str, Any]:
    """Render an identity the way the CLI and the framework have always read it.

    ``reflex.utils.prerequisites`` and ``reflex.custom_components`` read this
    out of ``authenticated_token`` across package versions, so it stays a
    mapping of the fields the control plane used to return.

    Args:
        me: The identity the access token authenticates as.

    Returns:
        The identity as a dict.

    """
    return {
        "user_id": str(me.user_id),
        "org_id": str(me.org_id),
        "email": me.email,
        "tier": me.tier,
        "is_service_account": me.is_service_account,
    }


def upload_client(client: AuthenticatedClient) -> ReflexBuild:
    """Build a client whose timeouts suit pushing a build's archives.

    The SDK's defaults are sized for API calls. An archive is not one: it is
    minutes of writing on a link the CLI does not choose, and the reserved
    signature it goes up under has its own window to finish inside.

    Args:
        client: The authenticated client the deploy is running under.

    Returns:
        A client to submit the deployment with. The caller closes it.

    """
    return ReflexBuild(
        token=client.token,
        base_url=constants.Hosting.HOSTING_SERVICE,
        timeout=UPLOAD_IO_TIMEOUT.total_seconds(),
    )


def validate_token(token: str) -> dict[str, Any]:
    """Validate the token with the control plane.

    Args:
        token: The access token to validate.

    Returns:
        Information about the user associated with the token.

    """
    return identity_as_dict(_validate(token))


def _validate_with_retries(
    access_token: str, api: ReflexBuild | None = None
) -> Me | None:
    """Validate an access token, reporting rather than raising when it does not.

    Args:
        access_token: The access token to validate.
        api: The client to ask with. Defaults to one built for the call.

    Returns:
        The identity behind the token, or None if it could not be established.

    """
    with console.status("Validating access token ..."):
        try:
            return _validate(access_token, api)
        except ValueError as ex:
            # getattr: mocks/foreign ValueErrors don't carry a request id.
            request_id = getattr(ex, "request_id", "") or get_auth_request_id()
            logger.error(f"Access denied (auth request id: {request_id})")
            delete_token_from_config()
        except Exception as ex:
            request_id = getattr(ex, "request_id", "") or get_auth_request_id()
            logger.warning(
                f"Unable to validate access token: {ex} (auth request id: {request_id})"
            )
    return None


def validate_token_with_retries(access_token: str) -> dict[str, Any]:
    """Validate the access token, reporting rather than raising when it does not.

    Args:
        access_token: The access token to validate.

    Returns:
        validated user info dict, empty if the token could not be validated.

    """
    me = _validate_with_retries(access_token)
    return identity_as_dict(me) if me is not None else {}


def get_authentication_client(token: str | None = None) -> AuthenticatedClient | None:
    """Get an authenticated client for a token that validates.

    Args:
        token: The authentication token.

    Returns:
        An authenticated client, or None when there is no token that validates.

    """
    access_token = token or get_existing_access_token()
    if not access_token:
        return None
    api = new_client(access_token)
    me = _validate_with_retries(access_token, api)
    if me is None:
        api.close()
        return None
    return AuthenticatedClient(api, me)


def get_authenticated_client(
    token: str | None = None, interactive: bool = True
) -> AuthenticatedClient:
    """Get an authenticated client.

    Args:
        token: The authentication token.
        interactive: If running in interactive mode.

    Returns:
        An authenticated client.

    Raises:
        Exit: If no token is provided in non-interactive mode, the token is
            rejected in non-interactive mode, or the browser login did not
            produce one.

    """
    if not interactive:
        if token:
            access_token, source = token, TokenSource.OPTION
        else:
            access_token, source = get_existing_access_token_with_source()
        if not access_token:
            logger.error("Token is required for non-interactive mode.")
            raise click.exceptions.Exit(1)
        api = new_client(access_token)
        try:
            with console.status("Validating access token ..."):
                me = _validate(access_token, api)
        except TokenValidationError as err:
            api.close()
            logger.error(rejected_token_message(source, err))
            raise click.exceptions.Exit(1) from err
        return AuthenticatedClient(api, me)

    if (client := get_authentication_client(token)) is not None:
        return client

    access_token, me = _authenticate_on_browser()
    if me is None:
        raise click.exceptions.Exit(1)
    return AuthenticatedClient(new_client(access_token), me)


def interactive_resolve_project_or_app_name_conflicts(
    items: list[Any],
    rows: list[list[str]],
    headers: list[str],
    conflict_warn_msg: str,
    conflict_ask_msg: str,
) -> Any:
    """Interactively resolve conflicts when multiple projects or apps are found.

    Args:
        items: The list of items to choose from.
        rows: The rows to display in the table.
        headers: The headers of the table.
        conflict_warn_msg: The warning message to display.
        conflict_ask_msg: The question to ask the user.

    Returns:
        The selected item.

    """
    logger.warning(conflict_warn_msg)
    console.print_table(rows, headers=list(headers))
    option = console.ask(
        conflict_ask_msg,
        choices=[str(i) for i in range(len(rows))],
    )
    return items[int(option)]


def search_app(
    app_name: str,
    client: AuthenticatedClient,
    project_id: str | None,
    interactive: bool = False,
) -> AppSummary | None:
    """Search for an application by name within a specific project.

    Args:
        app_name: The name of the application to search for.
        project_id: The ID of the project to search within. If None, searches across all projects.
        client: The authenticated client
        interactive: Whether to interactively resolve conflicts.

    Returns:
        The app, or None when no app has that name.

    Raises:
        Exit: If multiple apps are found and interactive is False.

    """
    apps = client.api.apps.search(app_name, project_id=project_id)

    if len(apps) > 1 and not interactive:
        logger.error(
            f"Multiple apps with the name {app_name!r} found. Please provide a unique name."
        )
        raise click.exceptions.Exit(1)

    if len(apps) > 1 and interactive:
        project_names = {
            project.id: project.name for project in client.api.projects.list()
        }
        return interactive_resolve_project_or_app_name_conflicts(
            apps,
            rows=[
                [
                    f"({i})",
                    str(app.id),
                    app.name,
                    project_names.get(app.project_id, ""),
                    str(app.project_id),
                ]
                for i, app in enumerate(apps)
            ],
            headers=["", "App ID", "Name", "Project name", "Project ID"],
            conflict_warn_msg="Found multiple apps with the same name. Select one to continue",
            conflict_ask_msg="Which app would you like to use?",
        )
    if len(apps) == 1:
        return apps[0]
    return None


def search_project(
    project_name: str, client: AuthenticatedClient, interactive: bool = False
) -> ProjectRef | None:
    """Search for a project by name.

    Args:
        project_name: The name of the project to search for.
        client: The authenticated client
        interactive: Whether to interactively resolve conflicts.

    Returns:
        The project, or None when no project has that name.

    Raises:
        Exit: If multiple projects are found and interactive is False.

    """
    projects = client.api.projects.search(project_name)

    if len(projects) > 1 and not interactive:
        logger.error(
            f"Multiple projects with the name {project_name!r} found. Please provide a unique name."
        )
        raise click.exceptions.Exit(1)

    if len(projects) > 1 and interactive:
        return interactive_resolve_project_or_app_name_conflicts(
            projects,
            rows=[
                [f"({i})", str(project.id), project.name]
                for i, project in enumerate(projects)
            ],
            headers=["", "Project ID", "Project name"],
            conflict_warn_msg="Found multiple projects with the same name. Select one to continue",
            conflict_ask_msg="Which project would you like to use?",
        )
    if len(projects) == 1:
        return projects[0]
    return None


# Hosting provider identifiers understood by the backend. Reflex Cloud is the
# managed platform (its backend wire value happens to be "fly", an
# implementation detail kept out of user-facing names); "gcp" is a
# customer-connected GCP Cloud Run target (bring-your-own-cloud, Enterprise tier).
PROVIDER_REFLEX_CLOUD = "fly"
PROVIDER_GCP = "gcp"

# User-facing provider names accepted on the CLI, mapped to backend values. Only
# provider-agnostic names are exposed -- the "fly" wire value is deliberately not
# an alias so deploy scripts don't couple to how Reflex Cloud is hosted.
PROVIDER_ALIASES = {
    "reflex-cloud": PROVIDER_REFLEX_CLOUD,
    "reflex": PROVIDER_REFLEX_CLOUD,
    "cloud": PROVIDER_REFLEX_CLOUD,
    "gcp": PROVIDER_GCP,
    "google": PROVIDER_GCP,
    "google-cloud": PROVIDER_GCP,
}


def normalize_provider(provider: str) -> str | None:
    """Map a user-facing provider name to the backend provider value.

    Args:
        provider: A provider name from the CLI (e.g. "reflex-cloud", "gcp").

    Returns:
        The backend provider value (``PROVIDER_REFLEX_CLOUD`` or
        ``PROVIDER_GCP``), or None if unrecognized.

    """
    return PROVIDER_ALIASES.get(provider.strip().lower())


def provider_display_name(provider: str | None) -> str:
    """Return a human-facing label for a backend provider value.

    Args:
        provider: The backend provider value (``PROVIDER_GCP`` for GCP; anything
            else, including None, is treated as Reflex Cloud).

    Returns:
        A display label, defaulting to "Reflex Cloud".

    """
    return "Google Cloud (GCP)" if provider == PROVIDER_GCP else "Reflex Cloud"


def get_token_org_id(client: AuthenticatedClient) -> str | None:
    """Return the organization id the caller's token is scoped to.

    Args:
        client: The authenticated client.

    Returns:
        The org id string, or None if unavailable.

    """
    return str(client.me.org_id) if client.me.org_id else None


def get_token_tier(client: AuthenticatedClient) -> str | None:
    """Return the subscription tier of the caller's token org.

    Args:
        client: The authenticated client.

    Returns:
        The tier name (e.g. "Enterprise"), or None if unavailable.

    """
    return client.me.tier or None


def gcp_deploy_available(client: AuthenticatedClient) -> GcpStatus | None:
    """Best-effort check of whether GCP is a usable deploy target for the caller.

    Never raises: it decides whether to *offer* GCP in ``reflex deploy``, so a
    lookup failure (older backend, permissions, network) simply falls back to
    the Reflex Cloud default rather than aborting the deploy.

    Args:
        client: The authenticated client.

    Returns:
        The GCP status when GCP is both configured and allowed for the caller's
        org, otherwise None.

    """
    org_id = get_token_org_id(client)
    if not org_id:
        return None
    try:
        status = client.api.providers.gcp_status(org_id)
    except Exception as ex:
        logger.debug(f"Unable to determine GCP availability: {ex}")
        return None
    return status if status.configured and status.allowed else None


def list_gcp_connections(
    client: AuthenticatedClient, org_id: str | None = None
) -> list[GcpConnection]:
    """List the GCP connections an org can deploy through.

    Read from the org's GCP status, which every member can see (the deploy
    dialog reads the same thing) and which lists only connections that are
    usable deploy targets. The provider-account listing is richer but is
    limited to org admins.

    Args:
        client: The authenticated client.
        org_id: The organization to query; defaults to the caller's token org.

    Returns:
        The usable connections, empty if no org id can be resolved.

    """
    org_id = org_id or get_token_org_id(client)
    if not org_id:
        return []
    return list(client.api.providers.gcp_status(org_id).connections)


def find_gcp_connection(
    connections: list[GcpConnection], name: str
) -> GcpConnection | None:
    """Pick the connection a user named, by id or by name.

    Args:
        connections: The connections to search, as returned by
            ``list_gcp_connections``.
        name: The connection id or name the user asked for.

    Returns:
        The matching connection, or None if nothing matched.

    """
    wanted = name.strip()
    for connection in connections:
        if str(connection.id) == wanted:
            return connection
    lowered = wanted.lower()
    for connection in connections:
        if connection.name.strip().lower() == lowered:
            return connection
    return None


def set_instance_bounds(
    app_id: str,
    client: AuthenticatedClient,
    min_instances: int | None = None,
    max_instances: int | None = None,
) -> str | None:
    """Set the autoscaling instance bounds on an app.

    Only the bounds explicitly passed are changed: the endpoint replaces both,
    so the app is read for the one that is not being set. The bounds are picked
    up by the next deployment, so this must be called before submitting one for
    it to take effect.

    Args:
        app_id: The id of the application.
        client: The authenticated client.
        min_instances: The minimum number of instances to keep running.
        max_instances: The maximum number of instances to scale out to.

    Returns:
        None on success, or a ``"set instance bounds failed: ..."`` string on
        error (validation, unsupported platform, or a scale already running).

    """
    try:
        current = client.api.apps.get(app_id)
        client.api.apps.set_instance_bounds(
            app_id,
            min_instances=current.min_instances
            if min_instances is None
            else min_instances,
            max_instances=current.max_instances
            if max_instances is None
            else max_instances,
        )
    except ReflexBuildError as ex:
        return f"set instance bounds failed: {error_message(ex)}"
    return None


def extract_subdomain(url: str):
    """Extract the subdomain from a given URL.

    Args:
        url: The URL to extract the subdomain from.

    Returns:
        str | None: The extracted subdomain, or None if extraction fails.

    """
    from urllib.parse import urlparse

    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    parsed_url = urlparse(url)
    netloc = parsed_url.netloc

    netloc = netloc.removeprefix("www.")

    parts = netloc.split(".")

    if len(parts) >= 2 or len(parts) == 1:
        return parts[0]

    return None


def scale_app(app_id: str, scale_params: ScaleParams, client: AuthenticatedClient):
    """Scale an application.

    Args:
        app_id: The ID of the application.
        scale_params: The scaling parameters.
        client: The authenticated client

    Raises:
        ResponseError: If the request to scale the app fails.

    """
    try:
        client.api.apps.scale(app_id, **scale_params.as_scale_arguments())
    except (AuthenticationError, MissingTokenError):
        # Answered by the command's own handler, which says how to fix it.
        raise
    except ReflexBuildError as ex:
        raise ResponseError(f"scale app failed: {error_message(ex)}") from ex


def select_project(project: str, token: str | None = None) -> str:
    """Select a project by its ID.

    Args:
        project: The ID of the project to select.
        token: The authentication token. If None, attempts to authenticate.

    Returns:
        A message saying what was selected, or why nothing was.

    """
    try:
        hosting_config = _read_hosting_config()
        hosting_config["project"] = project
        _write_hosting_config(hosting_config)
    except Exception as ex:
        return (
            f"failed to fetch token from {constants.Hosting.HOSTING_JSON} due to: {ex}"
        )
    return f"{project} is now selected."


def normalize_project_id(value: Any) -> str | None:
    """Normalize a project ID value, treating empty/whitespace strings and non-strings as None.

    Args:
        value: The raw project ID value from config, CLI args, or hosting.json.

    Returns:
        The stripped project ID, or None if the value is missing or blank.
    """
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def get_selected_project() -> str | None:
    """Retrieve the currently selected project ID.

    Returns:
        str | None: The ID of the selected project, or None if no project is selected.

    """
    try:
        return normalize_project_id(_read_hosting_config().get("project"))
    except Exception as ex:
        logger.debug(
            f"Unable to read selected project from {constants.Hosting.HOSTING_JSON} due to: {ex}"
        )
    return None


def get_default_project(authenticated_client: AuthenticatedClient) -> str | None:
    """Get the default project ID for the authenticated user.

    Args:
        authenticated_client: The authenticated client.

    Returns:
        The default project ID if available, None otherwise.
    """
    return str(authenticated_client.me.user_id)


# Terminal control sequences, which a build log is not entitled to emit into
# somebody's terminal. Ordered so a full sequence is consumed before the bare
# ESC that starts it: OSC first (it runs until its own terminator and is the
# one that writes the clipboard and forges hyperlinks), then CSI, then the
# two-character escapes, then anything left over.
_TERMINAL_CONTROL_RE = re.compile(
    r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC 8 hyperlinks, OSC 52 clipboard
    r"|\x1b\[[0-?]*[ -/]*[@-~]"  # CSI: colour, cursor moves, line erases
    # Every other escape sequence, in the general ECMA-48 shape: optional
    # intermediates then one final byte in 0x30-0x7E. Narrower classes leave
    # the final byte behind once the catch-all below eats the ESC -- `\x1b7`
    # (DECSC) printing a stray "7", `\x1bc` (full terminal reset) a stray "c".
    r"|\x1b[ -/]*[0-~]"
    r"|[\x00-\x08\x0b-\x1f\x7f-\x9f]"  # bare controls, keeping tab and newline
)


def _strip_terminal_controls(text: str) -> str:
    """*text* with terminal control sequences removed.

    A build log is the output of building the user's own app, dependencies
    included, and this excerpt is printed without anyone asking for it -- on
    any failed deploy, rather than only when `reflex cloud apps build-logs` is
    run. Colour is not worth carrying for that: the same sequences let the
    output erase the lines above it, forge a hyperlink, or write the
    clipboard, and none of that should be reachable from a dependency's build
    script. `markup=False` stops rich reading the text as its own markup and
    does nothing about escape sequences.

    Args:
        text: The text to strip.

    Returns:
        The text with terminal control sequences removed.

    """
    return _TERMINAL_CONTROL_RE.sub("", text)


# How long the watch waits out a dropped connection before looking again. The
# deployment outlives the connection, so the watch does too.
_WATCH_RETRY_SLEEP = datetime.timedelta(seconds=2)

# How long the control plane may stay unreachable before the watch hands the
# deployment back. Long enough to ride out a reconnecting VPN or a flapping
# link, short enough that a real outage does not hang a CI job until it is
# killed.
_WATCH_UNREACHABLE_GRACE = datetime.timedelta(minutes=5)

# "failed" is not one of the markers the SDK reads a status message for -- the
# ones it documents cover the statuses the pipeline publishes -- and is kept
# because it is what this predicate has always tested for. Dropping it could
# only ever make the answer less strict.
_STATUS_FAILED = "failed"


def deployment_status_failed(status: str) -> bool:
    """Check whether a deployment status reports a failure.

    Args:
        status: The status string the hosting service returned.

    Returns:
        True if the status says the deployment did not make it.

    """
    # A status the control plane could not produce says nothing about the
    # deployment, and the watch loop treats it as such rather than a failure.
    if "bad response" in status:
        return False
    if status_message_outcome(status) is not None:
        return status_message_outcome(status) == "failed"
    return _STATUS_FAILED in status


def _report_deployment_failure(
    deployment_id: str, report: DeploymentReport, fallback: str = ""
) -> None:
    """Tell the user why their deploy failed and what to do about it.

    The build log is offered only where the control plane recorded one. A
    failure in our pipeline reported as a build failure sends somebody hunting
    for a bug in an app that does not have one, which is the more expensive of
    the two mistakes.

    Args:
        deployment_id: The ID of the deployment.
        report: The deployment's final report.
        fallback: What to report when the report records no reason.

    """
    if reason := (report.reason or fallback):
        logger.error(reason)
    if report.guidance:
        logger.warning(report.guidance)

    if not report.build_log_excerpt:
        # A log the server holds but could not read is not a build that
        # produced none, and saying nothing here reads as the latter.
        if report.build_log_unreadable:
            logger.warning(
                "the build log could not be read right now; try again with:\n"
                f" reflex cloud apps build-logs {deployment_id}"
            )
        return
    # Raw build output: paths, versions and tracebacks, all of which rich would
    # read as markup given the chance, plus whatever escape sequences the
    # build printed.
    console.print("\nthe end of the build log:")
    console.print(_strip_terminal_controls(report.build_log_excerpt), markup=False)
    console.print(
        f"\nfor the whole log:\n reflex cloud apps build-logs {deployment_id}"
    )


class WatchOutcome(str, Enum):
    """How watching a deployment ended."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    # The deployment is still being worked on and the watching stopped: the
    # control plane went away, or refused to say more. Neither of the other two
    # is an honest answer for it.
    UNFINISHED = "unfinished"


@dataclasses.dataclass(frozen=True)
class WatchResult:
    """How watching a deployment ended, and the last thing it was told."""

    outcome: WatchOutcome
    # The last status message the watch saw, empty if it never saw one.
    status: str

    @property
    def failed(self) -> bool:
        """Whether the deployment is known not to have made it.

        Returns:
            True only for a deployment that ended without going live.

        """
        return self.outcome is WatchOutcome.FAILED


def watch_deployment_status(
    deployment_id: str, client: AuthenticatedClient
) -> WatchResult:
    """Continuously watch the status of a specific deployment.

    Args:
        deployment_id: The ID of the deployment.
        client: The authenticated client

    Returns:
        How the watching ended, and the last status message it saw. A caller
        that only wants to know whether to fail reads ``failed``: a watch that
        stopped early is not a deployment that did.

    """
    try:
        uuid.UUID(deployment_id)
    except ValueError:
        logger.error(f"{deployment_id!r} is not a deployment id.")
        return WatchResult(WatchOutcome.FAILED, "")

    last_status = ""

    def note(message: str) -> None:
        """Record and report a status the deployment reached.

        Args:
            message: The status message.

        """
        nonlocal last_status
        last_status = message
        logger.info(message)

    def narrated(recorded: str) -> str:
        """Choose between the narrated status and the deployment's recorded one.

        Args:
            recorded: The status from the deployment's report.

        Returns:
            The last message the API narrated, when that message settled the
            deployment itself. A message the SDK could not read an outcome from
            is why it asked for the report, and reporting it back would answer
            with the stale line the report was fetched to get past.

        """
        return last_status if status_message_outcome(last_status) else recorded

    def stopped_following(reason: str) -> WatchResult:
        """Hand the deployment back to the user and stop watching it.

        Args:
            reason: Why the watching stopped.

        Returns:
            An unfinished watch: the build was submitted and is still being
            worked on, so saying it succeeded would be a guess and saying it
            failed would be a wrong one.

        """
        logger.warning(
            f"stopped following the deployment: {reason}. It is still running; "
            f"check it with:\n reflex cloud apps status {deployment_id} --watch"
        )
        return WatchResult(WatchOutcome.UNFINISHED, last_status)

    with console.status("listening to status updates!"):
        unreachable_since = None
        while True:
            try:
                report = client.api.deployments.wait(deployment_id, on_status=note)
            except DeploymentFailedError as ex:
                _report_deployment_failure(deployment_id, ex.report, str(ex))
                return WatchResult(WatchOutcome.FAILED, narrated(ex.report.status))
            except NotFoundError:
                # The id parses but names nothing, so there is no deployment to
                # report on and nothing to wait for.
                logger.error(f"no deployment with id {deployment_id}.")
                return WatchResult(WatchOutcome.FAILED, last_status)
            except APIConnectionError as ex:
                # The deployment is still there; only this process's view of it
                # went away, and waiting that out is what the watch is for. Not
                # forever, though: a control plane that stays unreachable is a
                # command that never returns, so the handoff below ends it.
                now = monotonic()
                if unreachable_since is None:
                    unreachable_since = now
                    logger.warning(
                        "lost contact with the deployment service; still trying."
                    )
                if now - unreachable_since >= _WATCH_UNREACHABLE_GRACE.total_seconds():
                    return stopped_following(error_message(ex))
                time.sleep(_WATCH_RETRY_SLEEP.total_seconds())
                continue
            except ReflexBuildError as ex:
                return stopped_following(error_message(ex))
            break
    if report.status == "AwaitingApproval":
        logger.log(
            log.SUCCESS,
            "build submitted for approval; it will deploy automatically once an approver approves it.",
        )
    else:
        logger.log(log.SUCCESS, "deployment completed successfully")
    # The status the watch reports is the message the API narrated, the same
    # string `apps status` without --watch reports, rather than the report's
    # bare state -- one command should not name the same thing two ways.
    return WatchResult(WatchOutcome.SUCCEEDED, narrated(report.status))


def fetch_token(request_id: str, client: ReflexBuild | None = None) -> str:
    """Fetch the access token for the request_id from Control Plane.

    Args:
        request_id: The request ID used when the user opens the browser for authentication.
        client: The client to ask with. Defaults to one built for the call.

    Returns:
        The access token if it exists, empty strings otherwise.

    Raises:
        LoginDeniedError: If the user refused the login, which no amount of
            waiting will turn into a token.

    """
    login = LoginRequest(request_id=request_id, url="")
    with contextlib.ExitStack() as stack:
        if client is None:
            client = stack.enter_context(new_client())
        try:
            # One check per call: the caller runs the waiting loop, and this
            # one's own wait would sit silently under its status message.
            return client.auth.finish_login(login, timeout=0.0, poll_interval=0.0)
        except LoginTimeoutError:
            # Not approved yet.
            return ""
        except LoginDeniedError:
            raise
        except Exception as ex:
            logger.debug(f"Unable to fetch token due to: {ex}")
            return ""
    return ""


def _authenticate_on_browser() -> tuple[str, Me | None]:
    """Open the browser to authenticate the user.

    Returns:
        The access token and the identity behind it, or ``("", None)`` if the
        login did not produce one.

    Raises:
        Exit: when the hosting service URL is invalid.

    """
    if not is_valid_url(constants.Hosting.HOSTING_SERVICE_UI):
        logger.error(
            f"Invalid hosting URL: {constants.Hosting.HOSTING_SERVICE_UI}. Ensure the URL is in the correct format and includes a valid scheme"
        )
        raise click.exceptions.Exit(1)

    with new_client() as client:
        login = client.auth.begin_login(ui_url=constants.Hosting.HOSTING_SERVICE_UI)

        console.print(
            f"Opening {login.url} ... By connecting your account, you agree to "
            "Reflex Cloud [Terms of Service] and [Privacy Policy].",
            markup=False,
        )

        if not webbrowser.open(login.url):
            logger.warning(
                f"Unable to automatically open the browser. Please go to {login.url} to authenticate."
            )
        console.ask("please hit 'Enter' or 'Return' after login on website complete")
        access_token = ""
        with console.status("Waiting for access token ..."):
            for _ in range(constants.Hosting.AUTH_RETRY_LIMIT):
                try:
                    access_token = fetch_token(login.request_id, client)
                except LoginDeniedError:
                    logger.error("The login was denied.")
                    return "", None
                if access_token:
                    break
                time.sleep(1)

    if not access_token:
        return "", None
    me = _validate_with_retries(access_token)
    if me is None:
        return "", None
    save_token_to_config(access_token)
    select_project(project=str(me.user_id))
    return access_token, me


def authenticate_on_browser() -> tuple[str, dict[str, Any]]:
    """Open the browser to authenticate the user.

    Returns:
        The access token if valid and user information dict otherwise ("", {}).

    """
    access_token, me = _authenticate_on_browser()
    return (access_token, identity_as_dict(me)) if me is not None else ("", {})


def log_out_on_browser():
    """Open the browser to log out the user."""
    with contextlib.suppress(Exception):
        delete_token_from_config()
    console.print(f"Opening {constants.Hosting.HOSTING_SERVICE_UI} ...")
    if not webbrowser.open(constants.Hosting.HOSTING_SERVICE_UI):
        logger.warning(
            f"Unable to open the browser automatically. Please go to {constants.Hosting.HOSTING_SERVICE_UI} to log out."
        )


def process_envs(envs: list[str]) -> dict[str, str]:
    """Process the environment variables.

    Args:
        envs: The environment variables expected in key=value format.

    Returns:
        dict[str, str]: The processed environment variables in a dictionary.

    Raises:
        SystemExit: If the envs are not in valid format.

    """
    processed_envs = {}
    for env in envs:
        kv = env.split("=", maxsplit=1)
        if len(kv) != 2:
            raise SystemExit("Invalid env format: should be <key>=<value>.")

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", kv[0]):
            raise SystemExit(
                "Invalid env name: should start with a letter or underscore, followed by letters, digits, or underscores."
            )
        processed_envs[kv[0]] = kv[1]
    return processed_envs


def read_config(
    config_path: str | None = None, env: str | None = None
) -> Config | None:
    """Read the config file.

    Args:
        config_path: The path to the config file. If None, defaults to 'cloud.yml'.
        env: The environment to read the config for. If None, reads the default config.

    Returns:
        Config | None: The config file as a Config instance, or None if not found or invalid.

    """
    if config_path:
        return Config.from_yaml(Path(config_path))
    return Config.from_yaml_or_toml_or_none()


def generate_config(interactive: bool = True, token: str | None = None) -> Path | None:
    """Generate the config file with app-based prefilling.

    Args:
        interactive: Whether to use interactive mode for authentication and app selection.
        token: An existing authentication token to use instead of interactive auth.

    Returns:
        The path of the config file written, or None if none was.

    Raises:
        click.exceptions.Exit: If authentication fails or user cancels operation.
    """
    try:
        import yaml
    except ImportError:
        logger.error("Please install PyYAML to use this command: pip install pyyaml")
        return None

    config_path = Path("cloud.yml")
    if config_path.exists():
        logger.error("cloud.yml already exists.")
        return None

    try:
        authenticated_client = get_authenticated_client(
            token=token, interactive=interactive
        )
    except click.exceptions.Exit:
        logger.error("Authentication required to generate prefilled config.")
        raise

    current_dir_name = Path.cwd().name

    try:
        app = search_app(
            app_name=current_dir_name,
            project_id=None,
            client=authenticated_client,
            interactive=interactive,
        )
    except click.exceptions.Exit:
        raise
    except Exception as ex:
        logger.warning(f"Could not search for apps: {ex}")
        app = None

    if app:
        logger.info(f"Found app '{app.name}' - prefilling config with app data.")
        default = {"name": app.name, "appid": str(app.id)}
        if app.description:
            default["description"] = app.description
        default["project"] = str(app.project_id)
    else:
        logger.info(
            f"No app found with name '{current_dir_name}' - creating config with minimal defaults."
        )
        default = {"name": current_dir_name}

    with config_path.open("w") as config_file:
        yaml.dump(default, config_file, default_flow_style=False, sort_keys=False)
    logger.log(log.SUCCESS, "cloud.yml created successfully.")
    logger.info(
        "For more configuration options, see: https://reflex.dev/docs/hosting/config-file/"
    )
    return config_path


def get_vm_types() -> list[dict]:
    """Retrieve the available VM types.

    A refused or unreachable request raises rather than reading as an empty
    listing: a caller cannot tell "there are none" from "we could not ask".

    Returns:
        list[dict]: A list of VM types as dictionaries.

    """
    with new_client() as client:
        vm_types = client.deployments.vm_types()
    return [dataclasses.asdict(vm_type) for vm_type in vm_types]


def get_regions() -> list[dict]:
    """Get the supported regions from the hosting server.

    A refused or unreachable request raises rather than reading as an empty
    listing: a caller cannot tell "there are none" from "we could not ask".

    Returns:
        list[dict]: A list of dict representation of the region information.

    """
    with new_client() as client:
        regions = client.deployments.regions()
    return [{"name": region.name, "code": region.code} for region in regions]
