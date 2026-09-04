"""Hosting service related utilities."""

from __future__ import annotations

import contextlib
import dataclasses
import importlib.metadata
import json
import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from collections.abc import Callable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urljoin

import click

import reflex_cli.constants as constants
from reflex_cli.core.config import Config, RegionOption
from reflex_cli.utils import console, dependency, log
from reflex_cli.utils.dependency import is_valid_url
from reflex_cli.utils.exceptions import (
    ArchiveUploadError,
    GetAppError,
    NotAuthenticatedError,
    ResponseError,
    ScaleAppError,
    ScaleParamError,
    TokenAccessDeniedError,
    TokenValidationError,
)

logger = logging.getLogger(__name__)

# The reserve endpoint's key for each of a build's archives, and the file it
# signs a destination for.
ARCHIVES = {"backend": "backend.zip", "frontend": "frontend.zip"}

# Read size for a streamed archive PUT: small enough that the progress bar moves
# on a slow uplink, large enough not to syscall per kilobyte.
UPLOAD_CHUNK_SIZE = 256 * 1024

# Per socket operation, not per upload. A link that cannot move one chunk in
# this long -- roughly 17 kbps -- cannot finish an upload inside the window its
# signature was issued for either, and hanging on it tells the user nothing.
UPLOAD_CONNECT_TIMEOUT = 30.0
UPLOAD_IO_TIMEOUT = 120.0

# A signature that lapsed mid-upload is recovered by reserving again, and a
# fresh reservation mints a fresh deployment id -- so the retry re-uploads both
# archives under the new prefix rather than resuming the one that expired. Past
# two signed windows the link is the problem, and saying so beats looping.
UPLOAD_ATTEMPTS = 2


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

    def as_json(self) -> dict[str, Any]:
        """Convert the object to a dictionary.

        Returns:
            dict: The object as a dictionary.

        """
        effective_type = self.type or ScaleType.REGION
        return (
            {
                "type": str(effective_type.value),
                "size": self.vm_type,
            }
            if effective_type == ScaleType.SIZE
            else {
                "type": str(effective_type.value),
                "regions": {
                    region["name"]: region["number_of_machines"]
                    for region in self.regions
                },
            }
        )


@dataclasses.dataclass
class UnAuthenticatedClient:
    """A client that is not authenticated."""

    @staticmethod
    def authenticate() -> AuthenticatedClient:
        """Authenticate the client.

        Returns:
            An authenticated client.

        """
        access_token, validated_info = authenticate_on_browser()
        return AuthenticatedClient(access_token, validated_info)


@dataclasses.dataclass
class AuthenticatedClient:
    """A client that is authenticated."""

    token: str
    validated_data: dict[str, Any]


def get_authentication_client(
    token: str | None = None,
) -> AuthenticatedClient | UnAuthenticatedClient:
    """Get an authentication client.

    Args:
        token: The authentication token.

    Returns:
        An authenticated client if the token is valid, otherwise an unauthenticated client.

    """
    access_token = token or get_existing_access_token()
    if access_token:
        validated_info = validate_token_with_retries(access_token)
        if validated_info:
            return AuthenticatedClient(access_token, validated_info)
    return UnAuthenticatedClient()


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
        Exit: If no token is provided in non-interactive mode.

    """
    env_token = get_existing_access_token() if not token else ""
    if not token and not env_token and not interactive:
        logger.error("Token is required for non-interactive mode.")
        raise click.exceptions.Exit(1)

    client = get_authentication_client(token)
    if isinstance(client, UnAuthenticatedClient):
        return client.authenticate()
    return client


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


def validate_token(token: str) -> dict[str, Any]:
    """Validate the token with the control plane.

    Args:
        token: The access token to validate.

    Returns:
        Information about the user associated with the token.

    Raises:
        TokenAccessDeniedError: if access denied.
        TokenValidationError: if runs into timeout, failed requests, unexpected errors. These should be tried again.

    """
    import httpx

    global _last_auth_request_id
    request_id = _last_auth_request_id = uuid.uuid4().hex

    try:
        # Add reflex-enterprise detection flag as query parameter
        params = {
            "source": "reflex-enterprise"
            if is_reflex_enterprise_installed()
            else "reflex"
        }

        response = httpx.post(
            urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/authenticate/me"),
            headers={**authorization_header(token), "X-Request-ID": request_id},
            params=params,
            timeout=constants.Hosting.TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as re:
        logger.debug(
            f"Request to auth server failed due to {re} (request id: {request_id})"
        )
        raise TokenValidationError(str(re), request_id=request_id) from re
    except httpx.HTTPError as ex:
        logger.debug(
            f"Unable to validate the token due to: {ex} (request id: {request_id})"
        )
        raise TokenValidationError("server error", request_id=request_id) from ex
    except ValueError as ve:
        logger.debug(f"Access denied (request id: {request_id})")
        raise TokenAccessDeniedError("access denied", request_id=request_id) from ve
    except Exception as ex:
        logger.debug(f"Unexpected error: {ex} (request id: {request_id})")
        raise TokenValidationError("internal errors", request_id=request_id) from ex


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


def create_token(
    name: str,
    expiration: int,
    client: AuthenticatedClient,
) -> str:
    """Create a new access token.

    Args:
        name: The name of the token.
        expiration: The expiration time in seconds. If None, the token does not expire.
        client: The authenticated client

    Returns:
        The created access token.

    Raises:
        NotAuthenticatedError: If the client is not authenticated.
        Exception: If the token creation fails.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    try:
        response = httpx.post(
            urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/user/token"),
            json={"name": name, "expiration": expiration},
            headers=authorization_header(client.token),
            timeout=constants.Hosting.TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        raise Exception(f"Failed to create token: {ex.response.text}") from ex

    return response.text


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


def authorization_header(token: str) -> dict[str, str]:
    """Construct an authorization header with the specified token.

    Args:
        token: The access token to use.

    Returns:
        The authorization header in dict format.

    """
    return {"X-API-TOKEN": token}


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


def interactive_resolve_project_or_app_name_conflicts(
    items: list[dict],
    rows: list[list[str]],
    headers: list[str],
    conflict_warn_msg: str,
    conflict_ask_msg: str,
) -> dict:
    """Interactively resolve conflicts when multiple projects or apps are found.

    Args:
        items: The list of items to choose from.
        rows: The rows to display in the table.
        headers: The headers of the table.
        conflict_warn_msg: The warning message to display.
        conflict_ask_msg: The question to ask the user.

    Returns:
        The selected item as a dictionary

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
) -> dict | None:
    """Search for an application by name within a specific project.

    Args:
        app_name: The name of the application to search for.
        project_id: The ID of the project to search within. If None, searches across all projects.
        client: The authenticated client
        interactive: Whether to interactively resolve conflicts.

    Returns:
        list[dict]: The search results as a list of dicts.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        Exception: If the search request fails.
        Exit: If multiple apps are found and interactive is False.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    params: dict[str, str] = {"app_name": app_name}
    if project_id:
        params["project_id"] = project_id
    response = httpx.get(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/apps/search"),
        params=params,
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        ex_details = ex.response.json().get("detail")
        raise Exception(ex_details) from ex

    apps = response.json()

    if len(apps) > 1 and not interactive:
        logger.error(
            f"Multiple apps with the name {app_name!r} found. Please provide a unique name."
        )
        raise click.exceptions.Exit(1)

    if len(apps) > 1 and interactive:
        return interactive_resolve_project_or_app_name_conflicts(
            apps,
            rows=[
                [f"({i})", x["id"], x["name"], x["project"]["name"], x["project_id"]]
                for i, x in enumerate(apps)
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
) -> dict | None:
    """Search for a project by name.

    Args:
        project_name: The name of the application to search for.
        client: The authenticated client
        interactive: Whether to interactively resolve conflicts.

    Returns:
        list[dict]: The search results as a list of dict.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        Exception: If the search request fails.
        Exit: If multiple projects are found and interactive is False.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")

    response = httpx.get(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/project/search"),
        params={"project_name": project_name},
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        ex_details = ex.response.json().get("detail")
        raise Exception(f"project search failed: {ex_details}") from ex

    projects = response.json()

    if len(projects) > 1 and not interactive:
        logger.error(
            f"Multiple projects with the name {project_name!r} found. Please provide a unique name."
        )
        raise click.exceptions.Exit(1)

    if len(projects) > 1 and interactive:
        return interactive_resolve_project_or_app_name_conflicts(
            projects,
            rows=[[f"({i})", x["id"], x["name"]] for i, x in enumerate(projects)],
            headers=["", "Project ID", "Project name"],
            conflict_warn_msg="Found multiple projects with the same name. Select one to continue",
            conflict_ask_msg="Which project would you like to use?",
        )
    if len(projects) == 1:
        return projects[0]
    return None


def get_app(app_id: str, client: AuthenticatedClient) -> dict:
    """Retrieve details of a specific application by its ID.

    Args:
        app_id: The ID of the application to retrieve.
        client: The authenticated client

    Returns:
        dict: The application details as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        GetAppError: If the request to get the app fails.
        ValueError: If the app_id is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    if not isinstance(app_id, str) or not app_id:
        raise ValueError("app_id should be a string")
    response = httpx.get(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"/api/v1/apps/{app_id}"),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            raise GetAppError(ex.response.json().get("detail")) from ex
        except json.JSONDecodeError:
            raise GetAppError(ex.response.text) from ex
    return response.json()


def create_app(
    app_name: str,
    client: AuthenticatedClient,
    description: str,
    project_id: str | None,
    provider: str | None = None,
):
    """Create a new application.

    Args:
        app_name: The name of the application.
        description: The description of the application.
        project_id: The ID of the project to associate the application with.
        client: The authenticated client
        provider: The hosting provider to pin the app to (e.g. "gcp"). ``None``
            keeps the Reflex Cloud default.

    Returns:
        dict: The created application details as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        ValueError: If forbidden.

    """
    import httpx

    if not isinstance(app_name, str) or not app_name:
        raise ValueError("app_name should be a string")
    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    payload: dict[str, Any] = {
        "name": app_name,
        "description": description,
        "project": project_id,
    }
    if provider is not None:
        payload["provider"] = provider
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/apps/"),
        json=payload,
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    if response.status_code == HTTPStatus.FORBIDDEN:
        logger.debug(f"Server responded with 403: {response.text}")
        raise ValueError(f"{response.text}")
    response.raise_for_status()
    response_json = response.json()
    return response_json


# Hosting provider identifiers understood by the backend. Reflex Cloud is the
# managed platform (its backend wire value happens to be "fly", an
# implementation detail kept out of user-facing names); "gcp" is a
# customer-connected GCP Cloud Run target (bring-your-own-cloud, Enterprise tier).
PROVIDER_REFLEX_CLOUD = "fly"
PROVIDER_GCP = "gcp"

# User-facing provider names accepted on the CLI, mapped to backend values. Only
# provider-agnostic names are exposed — the "fly" wire value is deliberately not
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
    org_id = client.validated_data.get("org_id")
    return org_id if isinstance(org_id, str) and org_id else None


def get_token_tier(client: AuthenticatedClient) -> str | None:
    """Return the subscription tier of the caller's token org.

    Args:
        client: The authenticated client.

    Returns:
        The tier name (e.g. "Enterprise"), or None if unavailable.

    """
    tier = client.validated_data.get("tier")
    return tier if isinstance(tier, str) and tier else None


def get_gcp_provider_status(org_id: str, client: AuthenticatedClient) -> dict:
    """Fetch the org's GCP deploy availability.

    Args:
        org_id: The organization id to query.
        client: The authenticated client.

    Returns:
        A dict ``{configured, allowed, project_id, region, connections}``:
        ``configured`` is whether a GCP account is connected, ``allowed``
        whether the org's tier permits GCP deploys, and ``connections`` the
        named connections that are usable deploy targets.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/orgs/{org_id}/provider-accounts/gcp/status",
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def gcp_deploy_available(client: AuthenticatedClient) -> dict | None:
    """Best-effort check of whether GCP is a usable deploy target for the caller.

    Never raises: it decides whether to *offer* GCP in ``reflex deploy``, so a
    lookup failure (older backend, permissions, network) simply falls back to
    the Reflex Cloud default rather than aborting the deploy.

    Args:
        client: The authenticated client.

    Returns:
        The GCP status dict when GCP is both configured and allowed for the
        caller's org, otherwise None.

    """
    org_id = get_token_org_id(client)
    if not org_id:
        return None
    try:
        status = get_gcp_provider_status(org_id, client)
    except Exception as ex:
        logger.debug(f"Unable to determine GCP availability: {ex}")
        return None
    if status.get("configured") and status.get("allowed"):
        return status
    return None


def list_provider_accounts(org_id: str, client: AuthenticatedClient) -> list[dict]:
    """List the cloud provider accounts connected to an organization.

    Args:
        org_id: The organization id to query.
        client: The authenticated client.

    Returns:
        A list of ``{id, provider, name, is_default, config, created_by,
        created_at, updated_at}`` dicts (no secret material). Each row is one
        named connection; ``config`` carries its ``project_id``, ``region``,
        ``artifact_repo`` and ``runtime_service_account``.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/orgs/{org_id}/provider-accounts",
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def set_app_provider(
    app_id: str,
    provider: str,
    client: AuthenticatedClient,
    provider_account_id: str | None = None,
    service_name: str | None = None,
) -> str:
    """Choose which hosting platform an app deploys to.

    Switching providers on a deployed app tears down its resources on the
    previous provider and demotes its deployments; the app must be redeployed to
    come back up on the new provider.

    Args:
        app_id: The id of the application.
        provider: The backend provider value (``PROVIDER_REFLEX_CLOUD`` or
            ``PROVIDER_GCP``).
        client: The authenticated client.
        provider_account_id: Which of the org's GCP connections the app deploys
            through (GCP only). None keeps the connection the app already has
            when it stays on GCP, and means the org's default connection when
            GCP is first chosen.
        service_name: The Cloud Run service name the app deploys as (GCP only).
            None keeps the app's current name, or lets the server mint one from
            the app name; the server refuses a change once the app has deployed.

    Returns:
        The provider now set on the app, or a ``"... failed: ..."`` string on
        error.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    payload: dict[str, Any] = {"provider": provider}
    if provider_account_id is not None:
        payload["provider_account_id"] = provider_account_id
    if service_name is not None:
        payload["service_name"] = service_name
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"/api/v1/apps/{app_id}/provider"),
        json=payload,
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            ex_details = ex.response.json().get("detail")
        except (ValueError, AttributeError):
            ex_details = ex.response.text
        return f"set provider failed: {ex_details}"
    return response.json().get("provider", provider)


def set_app_full_deploy(
    app_id: str, full_deploy: bool, client: AuthenticatedClient
) -> dict[str, Any] | str:
    """Set whether the app's frontend is served from the provider too.

    In full-deploy mode the compiled frontend is bundled into the provider's
    container and served in front of the backend, so the whole app runs on the
    connected cloud account and nothing is hosted on Reflex's CDN. It is
    GCP-only and Enterprise-only. Flipping the mode on a running app stops it,
    so the next deploy brings it back up in the new mode -- which is why this
    has to be set before the hostname is reserved: the reserved URL is baked
    into the exported frontend.

    Args:
        app_id: The id of the application.
        full_deploy: Whether to serve the frontend from the provider.
        client: The authenticated client.

    Returns:
        ``{full_deploy, stopped, stop_confirmed}`` -- whether the app was
        stopped to apply the change, and whether the provider confirmed the
        stop -- or a ``"... failed: ..."`` string on error.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.post(
        urljoin(
            constants.Hosting.HOSTING_SERVICE, f"/api/v1/apps/{app_id}/full_deploy"
        ),
        json={"full_deploy": full_deploy},
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            ex_details = ex.response.json().get("detail")
        except (ValueError, AttributeError):
            ex_details = ex.response.text
        return f"set full deploy failed: {ex_details}"
    return response.json()


def list_gcp_connections(
    client: AuthenticatedClient, org_id: str | None = None
) -> list[dict]:
    """List the GCP connections an org can deploy through.

    Read from the org's GCP status, which every member can see (the deploy
    dialog reads the same thing) and which lists only connections that are
    usable deploy targets. The provider-account listing is richer but is
    limited to org admins.

    Args:
        client: The authenticated client.
        org_id: The organization to query; defaults to the caller's token org.

    Returns:
        A list of ``{id, name, is_default, project_id, region}`` dicts, empty
        if no org id can be resolved.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    org_id = org_id or get_token_org_id(client)
    if not org_id:
        return []
    status = get_gcp_provider_status(org_id, client)
    return [
        connection
        for connection in (status.get("connections") or [])
        if isinstance(connection, dict)
    ]


def find_gcp_connection(connections: list[dict], name: str) -> dict | None:
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
        if str(connection.get("id") or "") == wanted:
            return connection
    lowered = wanted.lower()
    for connection in connections:
        if str(connection.get("name") or "").strip().lower() == lowered:
            return connection
    return None


def set_instance_bounds(
    app_id: str,
    client: AuthenticatedClient,
    min_instances: int | None = None,
    max_instances: int | None = None,
) -> str | None:
    """Set the autoscaling instance bounds on an app.

    Only the bounds explicitly passed are sent; an omitted bound is left at
    whatever the app already has (the platform default, unless previously
    overridden). The bounds are picked up by the next deployment, so this must
    be called before submitting one for it to take effect.

    Args:
        app_id: The id of the application.
        client: The authenticated client.
        min_instances: The minimum number of instances to keep running.
        max_instances: The maximum number of instances to scale out to.

    Returns:
        None on success, or a ``"set instance bounds failed: ..."`` string on
        error (validation, unsupported platform, or a scale already running).

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    bounds: dict[str, int] = {}
    if min_instances is not None:
        bounds["min_instances"] = min_instances
    if max_instances is not None:
        bounds["max_instances"] = max_instances
    response = httpx.post(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/apps/{app_id}/instance_bounds",
        ),
        json=bounds,
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            ex_details = ex.response.json().get("detail")
        except (ValueError, AttributeError):
            ex_details = ex.response.text
        return f"set instance bounds failed: {ex_details}"
    return None


def rollback_deployment(
    app_id: str, deployment_id: str, client: AuthenticatedClient
) -> str | None:
    """Roll an app back to one of its previous deployments.

    Redeploys the target deployment's already-built image and makes it the
    current deployment again, without rebuilding from source.

    Args:
        app_id: The id of the application.
        deployment_id: The id of the deployment to roll back to.
        client: The authenticated client.

    Returns:
        None on success, or a ``"rollback failed: ..."`` string on error.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.post(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/apps/{app_id}/deployments/{deployment_id}/rollback",
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            ex_details = ex.response.json().get("detail")
        except (ValueError, AttributeError):
            ex_details = ex.response.text
        return f"rollback failed: {ex_details}"
    return None


def update_deployment_description(
    app_id: str,
    deployment_id: str,
    description: str,
    client: AuthenticatedClient,
) -> str | None:
    """Set or clear the changelog note on a single deployment.

    Args:
        app_id: The id of the application.
        deployment_id: The id of the deployment to annotate.
        description: The note to store (empty string clears it).
        client: The authenticated client.

    Returns:
        None on success, or a ``"update description failed: ..."`` string on
        error.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.post(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/apps/{app_id}/deployments/{deployment_id}/description",
        ),
        json={"description": description},
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            ex_details = ex.response.json().get("detail")
        except (ValueError, AttributeError):
            ex_details = ex.response.text
        return f"update description failed: {ex_details}"
    return None


def get_hostname(
    app_id: str, app_name: str, client: AuthenticatedClient, hostname: str | None
) -> dict:
    """Retrieve or reserve a hostname for a specific application.

    Args:
        app_id: The ID of the application.
        app_name: The name of the application.
        hostname: The desired hostname. If None, a hostname will be generated.
        client: The authenticated client

    Returns:
        dict: The hostname details as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        Exception: If deployment fails or the hostname is invalid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")

    data = {"app_id": app_id, "app_name": app_name}
    if hostname:
        clean_hostname = extract_subdomain(hostname)
        if clean_hostname is None:
            raise Exception("bad hostname provided")
        data["hostname"] = clean_hostname
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/apps/reserve"),
        headers=authorization_header(client.token),
        json=data,
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        if ex.response.status_code == 413:
            raise Exception(
                "deployment failed: the deployment payload is too large (over 100MB). "
                "Please reduce the size of your project by removing large files or "
                "adding them to your .gitignore file."
            ) from ex
        try:
            ex_details = ex.response.json().get("detail")
            if ex_details == "hostname taken":
                return {"error": "hostname taken"}
            raise Exception(f"deployment failed: {ex_details}") from ex
        except (ValueError, AttributeError):
            # Response is not valid JSON or missing detail field
            raise Exception(
                f"deployment failed: HTTP {ex.response.status_code} - {ex.response.text}"
            ) from ex
    response_json = response.json()
    return response_json


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


def get_secrets(app_id: str, client: AuthenticatedClient) -> str:
    """Retrieve secrets for a given application.

    Args:
        app_id: The ID of the application.
        client: The authenticated client

    Returns:
        The secrets as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"/api/v1/apps/{app_id}/secrets"),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            return ex.response.json().get("detail")
        except json.JSONDecodeError:
            return ex.response.text
    return response.json()


def update_secrets(
    app_id: str,
    secrets: dict,
    client: AuthenticatedClient,
    reboot: bool = False,
):
    """Update secrets for a given application.

    Args:
        app_id: The ID of the application.
        secrets: The secrets to update.
        reboot: Whether to reboot the application with the new secrets.
        client: The authenticated client

    Returns:
        The updated secrets as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.post(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/apps/{app_id}/secrets?reboot={reboot}",
        ),
        headers=authorization_header(client.token),
        json={"secrets": secrets},
        timeout=constants.Hosting.TIMEOUT,
    )
    response.raise_for_status()
    response_json = response.json()
    return response_json


def delete_secret(
    app_id: str, key: str, client: AuthenticatedClient, reboot: bool = False
) -> str:
    """Delete a secret for a given application.

    Args:
        app_id: The ID of the application.
        key: The key of the secret to delete.
        reboot: Whether to reboot the application with the updated secrets.
        client: The authenticated client

    Returns:
        The response from the delete operation as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.delete(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/apps/{app_id}/secrets/{key}?reboot={reboot}",
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            return ex.response.json().get("detail")
        except json.JSONDecodeError:
            return ex.response.text
    return response.json()


def create_project(name: str, client: AuthenticatedClient) -> dict:
    """Create a new project.

    Args:
        name: The name of the project.
        client: The authenticated client

    Returns:
        dict: The created project details as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        ValueError: If the request to create the project fails.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/project/create"),
        json={"name": name},
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    response_json = response.json()
    if response.status_code == HTTPStatus.BAD_REQUEST:
        logger.debug(f"Server responded with 400: {response_json.get('detail')}")
        raise ValueError(f"{response_json.get('detail', 'bad request')}")
    if response.status_code == HTTPStatus.CONFLICT:
        logger.debug(f"Duplicate project name: {response_json.get('detail')}")
        raise ValueError(
            f"A project named '{name}' already exists. Please use a different name."
        )
    response.raise_for_status()
    return response_json


def select_project(project: str, token: str | None = None) -> str:
    """Select a project by its ID.

    Args:
        project: The ID of the project to select.
        token: The authentication token. If None, attempts to authenticate.

    Returns:
        None

    """
    try:
        with constants.Hosting.HOSTING_JSON.open() as config_file:
            hosting_config = json.load(config_file)
        with constants.Hosting.HOSTING_JSON.open("w") as config_file:
            hosting_config["project"] = project
            json.dump(hosting_config, config_file)
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
        with constants.Hosting.HOSTING_JSON.open() as config_file:
            hosting_config = json.load(config_file)
            return normalize_project_id(hosting_config.get("project"))
    except Exception as ex:
        logger.debug(
            f"Unable to read selected project from {constants.Hosting.HOSTING_JSON} due to: {ex}"
        )
    return None


def get_projects(client: AuthenticatedClient) -> list[dict]:
    """Retrieve a list of projects.

    Args:
        client: The authenticated client.

    Returns:
        The list of projects as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/project/"),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    response.raise_for_status()
    response_json = response.json()
    return response_json


def get_project(project_id: str, client: AuthenticatedClient):
    """Retrieve a single project given the project ID.

    Args:
        project_id: The ID of the project.
        client: The authenticated client

    Returns:
        The project details as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"/api/v1/project/{project_id}"),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    response.raise_for_status()
    response_json = response.json()
    return response_json


def get_project_roles(project_id: str, client: AuthenticatedClient):
    """Retrieve the roles for a project.

    Args:
        project_id: The ID of the project.
        client: The authenticated client

    Returns:
        The roles as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(
            constants.Hosting.HOSTING_SERVICE, f"/api/v1/project/{project_id}/roles"
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    response.raise_for_status()
    response_json = response.json()
    return response_json


def get_project_role_permissions(
    project_id: str, role_id: str, client: AuthenticatedClient
):
    """Retrieve the permissions for a specific role in a project.

    Args:
        project_id: The ID of the project.
        role_id: The ID of the role.
        client: The authenticated client

    Returns:
        The role permissions as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/project/{project_id}/role/{role_id}",
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    response.raise_for_status()
    response_json = response.json()
    return response_json


def get_project_role_users(project_id: str, client: AuthenticatedClient):
    """Retrieve the users for a project.

    Args:
        project_id: The ID of the project.
        client: The authenticated client

    Returns:
        The users as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(
            constants.Hosting.HOSTING_SERVICE, f"/api/v1/project/{project_id}/users"
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    response.raise_for_status()
    response_json = response.json()
    return response_json


def invite_user_to_project(
    role_id: str, user_id: str, client: AuthenticatedClient
) -> str:
    """Invite a user to a project with a specific role.

    Args:
        role_id: The ID of the role to assign to the user.
        user_id: The ID of the user to invite.
        client: The authenticated client

    Returns:
        The response from the invite operation as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/project/users/invite"),
        headers=authorization_header(client.token),
        json={"user_id": user_id, "role_id": role_id},
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            return ex.response.json().get("detail")
        except json.JSONDecodeError:
            return ex.response.text
    return response.json()


def validate_deployment_args(
    app_name: str,
    app_id: str | None,
    project_id: str | None,
    regions: list[str] | None,
    vmtype: str | None,
    hostname: str | None,
    client: AuthenticatedClient,
) -> str:
    """Validate the deployment arguments.

    Args:
        app_name: The name of the application.
        app_id: The ID of the application.
        project_id: The ID of the project to associate the deployment with.
        regions: The list of regions for the deployment.
        vmtype: The VM type for the deployment.
        hostname: The hostname for the deployment.
        client: The authenticated client.

    Returns:
        The validation result as a string -- "success" if all checks pass.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        return "not authenticated"

    param_data = {
        "app_name": app_name or "",
        "app_id": app_id or "",
        "project_id": project_id or "",
        "regions": json.dumps(regions or []),
        "vmtype": vmtype or "",
        "hostname": hostname or "",
    }
    response = httpx.get(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/deployments/validate_cli"),
        headers=authorization_header(client.token),
        params=param_data,
        timeout=15,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        try:
            ex_details = ex.response.json().get("detail")
        except (httpx.RequestError, ValueError, KeyError):
            return "deployment failed: internal server error"
        else:
            return f"deployment failed: {ex_details}"

    return "success"


def _response_detail(response: Any, fallback: str) -> str:
    """Read the server's explanation for a refusal out of its body.

    Args:
        response: The refused response.
        fallback: What to say when the body does not carry an explanation.

    Returns:
        What the server said, or the fallback.

    """
    try:
        detail = response.json()["detail"]
    except (ValueError, KeyError, TypeError):
        detail = None
    # Every refusal this CLI can provoke carries a sentence. A body shaped some
    # other way -- a validation report, an HTML error page from something in
    # front of the service -- is not one, and pasting its repr at the user is
    # worse than the fallback.
    return detail if isinstance(detail, str) else fallback


def reserve_archive_upload(
    app_id: str, sizes: dict[str, int], client: AuthenticatedClient
) -> dict[str, Any] | None:
    """Ask the control plane where to put a build's archives.

    Nothing this endpoint itself refuses with is a 404 -- an unknown app, a
    missing permission and an out-of-range size are all 400 or 403 -- so a 404
    means the route is not there, on a control plane older than it. The caller
    relays the archives through it instead.

    Args:
        app_id: The app the build belongs to.
        sizes: Each archive's exact byte count, keyed as in ``ARCHIVES``. The
            count is signed into the URL, so a build that changes afterwards
            needs a new reservation rather than a retry of the same upload.
        client: The authenticated client.

    Returns:
        A deployment id with a signed target for each archive, or None if this
        control plane cannot hand one out.

    """
    import httpx

    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/deployments/reserve"),
        json={
            "app_id": app_id,
            "backend_size": sizes["backend"],
            "frontend_size": sizes["frontend"],
        },
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    if response.status_code == HTTPStatus.NOT_FOUND:
        return None
    response.raise_for_status()
    return response.json()


class _UploadAbandonedError(Exception):
    """The other archive's upload failed, so finishing this one buys nothing."""


def _archive_chunks(
    path: Path, advance: Callable[[int], None], abandoned: threading.Event
) -> Iterator[bytes]:
    """Read an archive in chunks, reporting each one once it is on the wire.

    Args:
        path: The archive to read.
        advance: Called with a chunk's size after it has been written out.
        abandoned: Set once the other archive's upload has failed.

    Yields:
        Successive chunks of the archive.

    Raises:
        _UploadAbandonedError: The other archive's upload failed partway through.

    """
    with path.open("rb") as archive:
        while chunk := archive.read(UPLOAD_CHUNK_SIZE):
            if abandoned.is_set():
                raise _UploadAbandonedError
            yield chunk
            advance(len(chunk))


def presigned_put(target: dict[str, Any], content: Any, size: int) -> None:
    """Upload a body to the presigned key it was signed for.

    Content-Length is set here rather than left to httpx, and that is the whole
    reason this is one function. The signature pins the exact byte count, so the
    request has to carry it: for a bytes body httpx would derive the same value
    anyway, but for a stream it cannot, and falls back to a chunked body that
    the signature does not match. Getting that wrong is silent until storage
    refuses the upload.

    No authorization header goes with it. The signature is the credential, and
    the destination is not ours to authenticate against.

    Args:
        target: The ``url`` and any required ``headers`` from the signing call.
        content: The body, as bytes or as an iterator of byte chunks.
        size: The body's exact byte count, as signed.

    """
    import httpx

    response = httpx.put(
        target["url"],
        headers={**target.get("headers", {}), "Content-Length": str(size)},
        content=content,
        timeout=httpx.Timeout(
            connect=UPLOAD_CONNECT_TIMEOUT,
            read=UPLOAD_IO_TIMEOUT,
            write=UPLOAD_IO_TIMEOUT,
            pool=UPLOAD_CONNECT_TIMEOUT,
        ),
    )
    response.raise_for_status()


def _put_archive(
    path: Path,
    target: dict[str, Any],
    size: int,
    advance: Callable[[int], None],
    abandoned: threading.Event,
) -> None:
    """Stream one archive to the key it was signed for.

    Args:
        path: The archive to upload.
        target: The ``url`` and required ``headers`` from the reservation.
        size: The archive's byte count, as reserved.
        advance: Called with a chunk's size after it has been written out.
        abandoned: Set once the other archive's upload has failed.

    """
    presigned_put(target, _archive_chunks(path, advance, abandoned), size)


def _put_reserved_archives(
    zip_dir: Path, reservation: dict[str, Any], sizes: dict[str, int]
) -> None:
    """Upload both of a build's archives to their signed keys, concurrently.

    They are independent objects under the same prefix, so nothing orders them.
    But neither is worth finishing alone: this build submits under one id, and
    if the other archive never lands there is nothing to submit. So the first
    failure abandons its sibling mid-stream rather than leaving the user
    watching a large upload complete into a deployment that cannot happen.

    Whatever the first archive to genuinely fail raised comes back out of here.

    Args:
        zip_dir: The directory holding the archives.
        reservation: The response from ``reserve_archive_upload``.
        sizes: Each archive's byte count, keyed as in ``ARCHIVES``.

    """
    abandoned = threading.Event()

    def upload(
        filename: str,
        target: dict[str, Any],
        size: int,
        advance: Callable[[int], None],
    ) -> None:
        try:
            _put_archive(zip_dir / filename, target, size, advance, abandoned)
        except _UploadAbandonedError:
            # Stopping on purpose is not a failure of its own, and it never
            # sets the flag: the archive that did fail is holding the reason,
            # and its future is the one that should carry it out of here.
            pass
        except BaseException:
            abandoned.set()
            raise

    with (
        console.transfer_progress() as progress,
        ThreadPoolExecutor(max_workers=len(ARCHIVES)) as pool,
    ):
        uploads = []
        for key, filename in ARCHIVES.items():
            task = progress.add_task(filename, total=sizes[key])
            uploads.append(
                pool.submit(
                    upload,
                    filename,
                    reservation[key],
                    sizes[key],
                    partial(progress.advance, task),
                )
            )
        for future in uploads:
            future.result()


def upload_archives(
    zip_dir: Path, app_id: str, sizes: dict[str, int], client: AuthenticatedClient
) -> str | None:
    """Push a build's archives straight to storage, without relaying them.

    A 403 on a PUT is a lapsed signature, and the recovery is a new reservation.
    That mints a new deployment id naming a new prefix, so both archives go up
    again under it -- the one that succeeded under the old id is not somewhere
    the new deployment will look.

    Args:
        zip_dir: The directory holding the archives.
        app_id: The app the build belongs to.
        sizes: Each archive's byte count, keyed as in ``ARCHIVES``.
        client: The authenticated client.

    Returns:
        The deployment id the archives now live under, or None if this control
        plane has no reserve endpoint and they have to be relayed instead.

    Raises:
        ArchiveUploadError: The archives could not be put where they belong.

    """
    import httpx

    for attempt in range(UPLOAD_ATTEMPTS):
        try:
            reservation = reserve_archive_upload(app_id, sizes, client)
        except httpx.HTTPStatusError as ex:
            raise ArchiveUploadError(
                _response_detail(ex.response, f"HTTP {ex.response.status_code}")
            ) from ex
        except httpx.HTTPError as ex:
            raise ArchiveUploadError(
                f"could not reach the deployment service: {ex}"
            ) from ex
        if reservation is None:
            return None
        try:
            _put_reserved_archives(zip_dir, reservation, sizes)
        except httpx.HTTPStatusError as ex:
            if ex.response.status_code != HTTPStatus.FORBIDDEN:
                raise ArchiveUploadError(
                    f"could not upload the build to storage: HTTP {ex.response.status_code}"
                ) from ex
            if attempt < UPLOAD_ATTEMPTS - 1:
                logger.warning("the upload window expired; reserving another one")
        except httpx.HTTPError as ex:
            raise ArchiveUploadError(f"could not upload the build: {ex}") from ex
        else:
            return reservation["deployment_id"]
    raise ArchiveUploadError(
        "the upload did not finish before its window closed; this usually means "
        "the connection is too slow for the size of the build"
    )


def create_deployment(
    zip_dir: Path,
    client: AuthenticatedClient,
    app_name: str | None,
    project_id: str | None,
    regions: list | None,
    hostname: str | None,
    vmtype: str | None,
    secrets: dict | None,
    packages: list | None,
    strategy: str | None,
    app_id: str | None,
    description: str | None = None,
) -> str:
    """Create a new deployment for an application.

    Args:
        app_name: The name of the application.
        project_id: The ID of the project to associate the deployment with.
        regions: The list of regions for the deployment.
        zip_dir: The directory containing the zip files for the deployment.
        hostname: The hostname for the deployment.
        vmtype: The VM type for the deployment.
        secrets: The secrets to use for the deployment.
        client: The authenticated client
        packages: The list of packages to install on the VM.
        strategy: The deployment strategy to use.
        app_id: The ID of the application.
        description: An optional changelog note recorded on this deployment and
            shown in ``reflex cloud apps history``.

    Returns:
        The deployment id.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    cli_version = importlib.metadata.version("reflex-hosting-cli")
    payload: dict[str, Any] = {
        "app_id": app_id,
        "app_name": app_name,
        "reflex_hosting_cli_version": cli_version,
        "reflex_version": dependency.get_reflex_version(),
        "python_version": platform.python_version(),
    }
    if project_id:
        payload["project_id"] = project_id
    if regions:
        regions = regions or []
        payload["regions"] = json.dumps(regions)
    if hostname:
        payload["hostname"] = hostname
    if vmtype:
        payload["vm_type"] = vmtype
    if secrets:
        payload["secrets"] = json.dumps(secrets)
    if packages:
        payload["packages"] = json.dumps(packages)
    if strategy:
        payload["deployment_strategy"] = strategy
    if description:
        payload["description"] = description

    # The archives go straight to storage where the control plane can sign for
    # them, and only their id is submitted here. Relaying them through it is the
    # fallback for a control plane that cannot, and for a caller with no app id
    # to reserve against.
    stored_build_id = None
    if app_id is not None:
        sizes = {key: (zip_dir / name).stat().st_size for key, name in ARCHIVES.items()}
        try:
            stored_build_id = upload_archives(zip_dir, app_id, sizes, client)
        except ArchiveUploadError as ex:
            return f"deployment failed: {ex}"

    with contextlib.ExitStack() as archives:
        zips = None
        if stored_build_id is not None:
            payload["stored_build_id"] = stored_build_id
        else:
            zips = [
                ("files", (name, archives.enter_context((zip_dir / name).open("rb"))))
                for name in ARCHIVES.values()
            ]
        response = httpx.post(
            urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/deployments"),
            data=payload,
            files=zips,
            headers=authorization_header(client.token),
            timeout=55,
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        if ex.response.status_code == 413:
            return (
                "deployment failed: the deployment payload is too large (over 100MB). "
                "Please reduce the size of your project by removing large files or "
                "adding them to your .gitignore file."
            )
        try:
            ex_details = ex.response.json().get("detail")
        except (httpx.RequestError, ValueError, KeyError):
            return "deployment failed: internal server error"
        else:
            return f"deployment failed: {ex_details}"
    return response.json()


class SecurityReviewError(ResponseError):
    """Raised when a security review request fails."""


_SECURITY_REVIEW_PREFIX = "/api/v1/agents/security-review"


def _security_review_detail(response: Any) -> str:
    """Extract a human-readable ``detail`` from a failed review response.

    Args:
        response: The error response from the security review API.

    Returns:
        The server-provided detail, or a generic fallback if the body is not
        a JSON object with a ``detail`` field.

    """
    return _response_detail(response, "internal server error")


def submit_security_review(zip_bytes: bytes, client: AuthenticatedClient) -> str:
    """Submit a zipped app for security review.

    Uploads the archive straight to object storage via a presigned URL, then
    submits the stored object for review.

    Args:
        zip_bytes: The zipped app source to review.
        client: The authenticated client.

    Returns:
        The id of the submitted job, to be polled with ``get_security_review``.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        SecurityReviewError: If any step of the submission fails.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")

    auth = authorization_header(client.token)

    # 1. Ask the API for a presigned URL to upload the archive directly.
    upload_url_response = httpx.post(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"{_SECURITY_REVIEW_PREFIX}/jobs/upload-url",
        ),
        json={"content_length": len(zip_bytes), "content_type": "application/zip"},
        headers=auth,
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        upload_url_response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        raise SecurityReviewError(_security_review_detail(ex.response)) from ex
    upload = upload_url_response.json()

    # 2. Upload the bytes to storage, under the length and type the URL pins.
    try:
        presigned_put(upload, zip_bytes, len(zip_bytes))
    except httpx.HTTPStatusError as ex:
        raise SecurityReviewError("failed to upload app source for review") from ex

    # 3. Submit the uploaded object for review.
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"{_SECURITY_REVIEW_PREFIX}/jobs"),
        json={"key": upload["key"]},
        headers=auth,
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        raise SecurityReviewError(_security_review_detail(ex.response)) from ex
    return response.json()["job_id"]


def get_security_review(job_id: str, client: AuthenticatedClient) -> dict[str, Any]:
    """Poll a previously submitted security review job.

    Args:
        job_id: The id returned by ``submit_security_review``.
        client: The authenticated client.

    Returns:
        The job status payload: ``status`` is one of ``pending``, ``complete``
        or ``error``; ``result`` holds the review once ``complete``.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        SecurityReviewError: If the server returns an error.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")

    response = httpx.get(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"{_SECURITY_REVIEW_PREFIX}/jobs/{job_id}",
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        raise SecurityReviewError(_security_review_detail(ex.response)) from ex
    return response.json()


def stop_app(app_id: str, client: AuthenticatedClient):
    """Stop a running application.

    Args:
        app_id: The ID of the application.
        client: The authenticated client

    Returns:
        The response from the stop operation as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"/api/v1/apps/{app_id}/stop"),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        ex_details = ex.response.json().get("detail")
        return f"stop app failed: {ex_details}"
    return response.json()


def start_app(app_id: str, client: AuthenticatedClient):
    """Start a stopped application.

    Args:
        app_id: The ID of the application.
        client: The authenticated client

    Returns:
        The response from the start operation as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"/api/v1/apps/{app_id}/start"),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        ex_details = ex.response.json().get("detail")
        return f"start app failed: {ex_details}"
    return response.json()


def delete_app(app_id: str, client: AuthenticatedClient):
    """Delete an application.

    Args:
        app_id: The ID of the application.
        client: The authenticated client

    Returns:
        The response from the delete operation as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    app = get_app(app_id=app_id, client=client)
    if not app:
        logger.warning("no app with given id found")
        return None
    response = httpx.delete(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"/api/v1/apps/{app['id']}/delete"),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        ex_details = ex.response.json().get("detail")
        return f"delete app failed: {ex_details}"
    return response.json()


def get_app_logs(
    app_id: str,
    offset: int | None,
    start: int | None,
    end: int | None,
    client: AuthenticatedClient,
    cursor: str | None = None,
):
    """Retrieve logs for a given application.

    Args:
        app_id: The ID of the application.
        offset: The offset in seconds from the current time.
        start: The start time in Unix epoch format.
        end: The end time in Unix epoch format.
        client: The authenticated client
        cursor: The cursor for pagination.

    Returns:
        The logs as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    try:
        app = get_app(app_id=app_id, client=client)
    except GetAppError:
        logger.warning(f"No application found with ID '{app_id}'")
        return None
    if not app:
        logger.warning("no app with given id found")
        return None
    params: dict[str, str | int | None] = (
        {"offset": offset} if offset else {"start": start, "end": end}
    )
    if cursor:
        params["cursor"] = cursor
    try:
        with console.status("Fetching application logs..."):
            response = httpx.get(
                urljoin(
                    constants.Hosting.HOSTING_SERVICE,
                    f"/api/v1/apps/{app['id']}/logsv2",
                ),
                params=params,
                headers=authorization_header(client.token),
                timeout=constants.Hosting.TIMEOUT,
            )
            response.raise_for_status()
    except httpx.RequestError:
        return []
    except httpx.HTTPStatusError as ex:
        try:
            ex_details = ex.response.json().get("detail")
        except json.JSONDecodeError:
            return []
        else:
            return f"get app logs failed: {ex_details}"
    else:
        try:
            return response.json()
        except json.JSONDecodeError:
            return []


def list_apps(client: AuthenticatedClient, project: str | None = None) -> list[dict]:
    """List all the hosted deployments of the authenticated user.

    Args:
        project: The project ID to filter deployments.
        client: The authenticated client

    Returns:
        List[dict]: A list of deployments as dictionaries.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        Exception: when listing apps fails.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")

    url = urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/apps")
    params = {"project": project} if project else None

    response = httpx.get(
        url,
        params=params,
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        ex_details = ex.response.json().get("detail")
        raise Exception(f"list app failed: {ex_details}") from ex
    return response.json()


def get_app_history(app_id: str, client: AuthenticatedClient) -> list:
    """Retrieve the deployment history for a given application.

    Args:
        app_id: The ID of the application.
        client: The authenticated client

    Returns:
        list: A list of deployment history entries as dictionaries.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"/api/v1/apps/{app_id}/history"),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )

    response.raise_for_status()
    response_json = response.json()
    result = [
        {
            "id": deployment["id"],
            "status": deployment["status"],
            "hostname": deployment["hostname"],
            "python version": deployment["python_version"],
            "reflex version": deployment["reflex_version"],
            "vm type": deployment["vm_type"],
            "timestamp": deployment["timestamp"],
            "description": deployment.get("description") or "",
            "can rollback": deployment.get("can_rollback", False),
        }
        for deployment in response_json
    ]
    return result


def get_app_status(app_id: str, client: AuthenticatedClient) -> str:
    """Retrieve the status of a specific app.

    Args:
        app_id: The ID of the app.
        client: The authenticated client

    Returns:
        str: The status of the app.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    try:
        response = httpx.get(
            urljoin(
                constants.Hosting.HOSTING_SERVICE,
                f"/api/v1/deployments/{app_id}/status",
            ),
            headers=authorization_header(client.token),
            timeout=constants.Hosting.TIMEOUT,
        )
    except httpx.RequestError as e:
        return "lost connection: trying again" + f"({e.__class__.__name__}: {e})"

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        return f"error: bad response: {response.status_code}. received a bad response from cloud service."
    return response.json()


def scale_app(app_id: str, scale_params: ScaleParams, client: AuthenticatedClient):
    """Scale an application.

    Args:
        app_id: The ID of the application.
        scale_params: The scaling parameters.
        client: The authenticated client

    Returns:
        The response from the scale operation as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.
        ResponseError: If the request to scale the app fails.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, f"/api/v1/apps/{app_id}/scale"),
        headers=authorization_header(client.token),
        json=scale_params.as_json(),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        ex_details = ex.response.json().get("detail")
        raise ResponseError(f"scale app failed: {ex_details}") from ex
    return response.json()


def get_deployment_status(deployment_id: str, client: AuthenticatedClient) -> str:
    """Retrieve the status of a specific deployment.

    Args:
        deployment_id: The ID of the deployment.
        client: The authenticated client

    Returns:
        str: The status of the deployment.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/deployments/{deployment_id}/status",
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as ex:
        ex_details = ex.response.json().get("detail")
        return f"get status failed: {ex_details}"
    return response.json()


def _get_deployment_status(deployment_id: str, token: str) -> str:
    """Retrieve the status of a specific deployment with error handling.

    Args:
        deployment_id: The ID of the deployment.
        token: The authentication token.

    Returns:
        str: The status of the deployment, or an error message if the request fails.

    """
    import httpx

    try:
        response = httpx.get(
            urljoin(
                constants.Hosting.HOSTING_SERVICE,
                f"/api/v1/deployments/{deployment_id}/status",
            ),
            headers=authorization_header(token),
            timeout=constants.Hosting.TIMEOUT,
        )
    except httpx.RequestError as e:
        return "lost connection: trying again" + f"({e.__class__.__name__}: {e})"

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        return "bad response. received a bad response from cloud service."
    return response.json()


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


def _get_deployment_failure(deployment_id: str, token: str) -> dict | None:
    """Why a deployment failed, in fields, or None when that cannot be had.

    None covers every way of not getting an answer, and they are one case to
    the caller: a control plane predating this endpoint 404s, an older
    self-hosted one may not route it at all, and the network may simply be
    down. All three mean the same thing here -- report the failure the way the
    CLI always has, from the status string.

    Args:
        deployment_id: The ID of the deployment.
        token: The authentication token.

    Returns:
        The failure report, or None if it could not be read.

    """
    import httpx

    try:
        response = httpx.get(
            urljoin(
                constants.Hosting.HOSTING_SERVICE,
                f"/api/v1/deployments/{deployment_id}/failure",
            ),
            headers=authorization_header(token),
            timeout=constants.Hosting.TIMEOUT,
        )
        response.raise_for_status()
        report = response.json()
    # Wider than json.JSONDecodeError, because a malformed body has more than
    # one way to fail: an undecodable encoding raises UnicodeDecodeError (a
    # ValueError) and a deeply nested document raises RecursionError (a
    # RuntimeError). Either escaping would abort the watch over an answer this
    # function is contracted to treat as no answer at all.
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, RecursionError):
        return None
    return report if isinstance(report, dict) else None


def _report_deployment_failure(
    deployment_id: str,
    token: str,
    status: str,
    *,
    offer_build_logs: bool,
) -> None:
    """Tell the user why their deploy failed and what to do about it.

    The build log is offered only where the control plane says it is the
    answer. A failure in our pipeline reported as a build failure sends
    somebody hunting for a bug in an app that does not have one, which is the
    more expensive of the two mistakes and the reason the fault is asked about
    at all.

    Args:
        deployment_id: The ID of the deployment.
        token: The authentication token.
        status: The status string the watch loop ended on.
        offer_build_logs: Whether to point at the build log when no structured
            report can be read, preserving what this arm printed before.

    """
    report = _get_deployment_failure(deployment_id, token)
    if report is None:
        logger.warning(status)
        if offer_build_logs:
            logger.warning(
                f"to see the build logs:\n reflex cloud apps build-logs {deployment_id}"
            )
        return

    logger.error(report.get("reason") or status)
    if guidance := report.get("guidance"):
        logger.warning(guidance)

    excerpt = report.get("build_log_excerpt")
    # Typed as a string by the endpoint, checked because this one is not ours:
    # the CLI is versioned apart from the control plane and talks to
    # self-hosted ones, so a non-string here would raise in the sanitiser and
    # take down a report that had already read fine.
    if not excerpt or not isinstance(excerpt, str):
        # A log the server holds but could not read is not a build that
        # produced none, and saying nothing here reads as the latter.
        if report.get("build_log_unreadable"):
            logger.warning(
                "the build log could not be read right now; try again with:\n"
                f" reflex cloud apps build-logs {deployment_id}"
            )
        return
    # Raw build output: paths, versions and tracebacks, all of which rich would
    # read as markup given the chance, plus whatever escape sequences the
    # build printed.
    console.print("\nthe end of the build log:")
    console.print(_strip_terminal_controls(excerpt), markup=False)
    console.print(
        f"\nfor the whole log:\n reflex cloud apps build-logs {deployment_id}"
    )


def watch_deployment_status(deployment_id: str, client: AuthenticatedClient) -> bool:
    """Continuously watch the status of a specific deployment.

    Args:
        deployment_id: The ID of the deployment.
        client: The authenticated client

    Returns:
        True when the watching ends.
        False when watching ends in fail.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    with console.status("listening to status updates!"):
        current_status = ""
        while True:
            status = _get_deployment_status(
                deployment_id=deployment_id, token=client.token
            )
            if "completed successfully" in status:
                logger.log(log.SUCCESS, status)
                break
            if "AwaitingApproval" in status:
                logger.log(
                    log.SUCCESS,
                    "build submitted for approval; it will deploy automatically once an approver approves it.",
                )
                break
            if "build error" in status:
                _report_deployment_failure(
                    deployment_id, client.token, status, offer_build_logs=True
                )
                return False
            if "unable to find status for given id" in status:
                # Not a failed deployment but an id that resolves to nothing,
                # so there is no row to report on and nothing to ask for.
                logger.error(status)
                return False
            if "error" in status:
                _report_deployment_failure(
                    deployment_id, client.token, status, offer_build_logs=False
                )
                return False
            if "bad response" in status:
                logger.warning(status)
                return True
            if status != current_status:
                current_status = status
                logger.info(status)
            time.sleep(0.5)
    return True


def get_deployment_build_logs(deployment_id: str, client: AuthenticatedClient):
    """Retrieve the build logs for a specific deployment.

    Args:
        deployment_id: The ID of the deployment.
        client: The authenticated client

    Returns:
        dict: The build logs as a dictionary.

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    response = httpx.get(
        urljoin(
            constants.Hosting.HOSTING_SERVICE,
            f"/api/v1/deployments/{deployment_id}/build/logs",
        ),
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )

    response.raise_for_status()
    return response.json()


def list_projects():
    """List all projects.

    This function is currently a placeholder and does not perform any operations.

    Returns:
        None

    """
    return


def fetch_token(request_id: str) -> str:
    """Fetch the access token for the request_id from Control Plane.

    Args:
        request_id: The request ID used when the user opens the browser for authentication.

    Returns:
        The access token if it exists, empty strings otherwise.

    """
    import httpx

    token = ""
    try:
        resp = httpx.get(
            urljoin(
                constants.Hosting.HOSTING_SERVICE,
                f"/api/v1/cli/token?request_id={request_id}",
            ),
            timeout=constants.Hosting.TIMEOUT,
        )
        resp.raise_for_status()
        token = (resp_json := resp.json()).get("token_id", "")
        project_id = resp_json.get("user_id", "")
        select_project(project=project_id)
    except httpx.RequestError as re:
        logger.debug(f"Unable to fetch token due to request error: {re}")
    except httpx.HTTPError as he:
        logger.debug(f"Unable to fetch token due to {he}")
    except json.JSONDecodeError as jde:
        logger.debug(f"Server did not respond with valid json: {jde}")
    except KeyError as ke:
        logger.debug(f"Server response format unexpected: {ke}")
    except Exception as ex:
        logger.debug(f"Unexpected errors: {ex}")

    return token


def authenticate_on_browser() -> tuple[str, dict[str, Any]]:
    """Open the browser to authenticate the user.

    Returns:
        The access token if valid and user information dict otherwise ("", {}).

    Raises:
        Exit: when the hosting service URL is invalid.

    """
    request_id = uuid.uuid4().hex
    auth_url = urljoin(
        constants.Hosting.HOSTING_SERVICE_UI, f"/cli/login?request_id={request_id}"
    )

    if not is_valid_url(constants.Hosting.HOSTING_SERVICE_UI):
        logger.error(
            f"Invalid hosting URL: {constants.Hosting.HOSTING_SERVICE_UI}. Ensure the URL is in the correct format and includes a valid scheme"
        )
        raise click.exceptions.Exit(1)

    console.print(
        f"Opening {auth_url} ... By connecting your account, you agree to "
        "Reflex Cloud [Terms of Service] and [Privacy Policy].",
        markup=False,
    )

    if not webbrowser.open(auth_url):
        logger.warning(
            f"Unable to automatically open the browser. Please go to {auth_url} to authenticate."
        )
    validated_info = {}
    access_token = ""
    console.ask("please hit 'Enter' or 'Return' after login on website complete")
    with console.status("Waiting for access token ..."):
        for _ in range(constants.Hosting.AUTH_RETRY_LIMIT):
            access_token = fetch_token(request_id)
            if access_token:
                break
            time.sleep(1)

    if access_token and (validated_info := validate_token_with_retries(access_token)):
        save_token_to_config(access_token)
    else:
        access_token = ""
    return access_token, validated_info


def get_default_project(authenticated_client: AuthenticatedClient) -> str | None:
    """Get the default project ID for the authenticated user.

    Args:
        authenticated_client: The authenticated client.

    Returns:
        The default project ID if available, None otherwise.
    """
    return authenticated_client.validated_data.get("user_id")


def validate_token_with_retries(access_token: str) -> dict[str, Any]:
    """Validate the access token without retries.

    Args:
        access_token: The access token to validate.

    Returns:
        validated user info dict.

    """
    with console.status("Validating access token ..."):
        try:
            return validate_token(access_token)
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
    return {}


def process_envs(envs: list[str]) -> dict[str, str]:
    """Process the environment variables.

    Args:
        envs: The environment variables expected in key=value format.

    Raises:
        SystemExit: If the envs are not in valid format.

    Returns:
        dict[str, str]: The processed environment variables in a dictionary.

    Raises:
        SystemExit: If invalid format.

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


def generate_config(interactive: bool = True, token: str | None = None):
    """Generate the config file with app-based prefilling.

    Args:
        interactive: Whether to use interactive mode for authentication and app selection.
        token: An existing authentication token to use instead of interactive auth.

    Raises:
        click.exceptions.Exit: If authentication fails or user cancels operation.
    """
    try:
        import yaml
    except ImportError:
        logger.error("Please install PyYAML to use this command: pip install pyyaml")
        return

    if Path("cloud.yml").exists():
        logger.error("cloud.yml already exists.")
        return

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
        logger.info(f"Found app '{app['name']}' - prefilling config with app data.")
        default = {"name": app["name"]}

        if app.get("id"):
            default["appid"] = app["id"]
        if app.get("description"):
            default["description"] = app["description"]
        if app.get("project_id"):
            default["project"] = app["project_id"]
    else:
        logger.info(
            f"No app found with name '{current_dir_name}' - creating config with minimal defaults."
        )
        default = {"name": current_dir_name}

    with Path("cloud.yml").open("w") as config_file:
        yaml.dump(default, config_file, default_flow_style=False, sort_keys=False)
    logger.log(log.SUCCESS, "cloud.yml created successfully.")
    logger.info(
        "For more configuration options, see: https://reflex.dev/docs/hosting/config-file/"
    )
    return


def log_out_on_browser():
    """Open the browser to log out the user."""
    with contextlib.suppress(Exception):
        delete_token_from_config()
    console.print(f"Opening {constants.Hosting.HOSTING_SERVICE_UI} ...")
    if not webbrowser.open(constants.Hosting.HOSTING_SERVICE_UI):
        logger.warning(
            f"Unable to open the browser automatically. Please go to {constants.Hosting.HOSTING_SERVICE_UI} to log out."
        )


def get_vm_types() -> list[dict]:
    """Retrieve the available VM types.

    Returns:
        list[dict]: A list of VM types as dictionaries.

    """
    import httpx

    try:
        response = httpx.get(
            urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/deployments/vm_types"),
            timeout=10,
        )
        response.raise_for_status()
        response_json = response.json()
        if response_json is None or not isinstance(response_json, list):
            logger.error("Expect server to return a list ")
            return []
        if (
            response_json
            and response_json[0] is not None
            and not isinstance(response_json[0], dict)
        ):
            logger.error("Expect return values are dict's")
            return []
    except Exception as ex:
        logger.error(f"Unable to get vmtypes due to {ex}.")
        return []
    else:
        return response_json


def get_regions() -> list[dict]:
    """Get the supported regions from the hosting server.

    Returns:
        list[dict]: A list of dict representation of the region information.

    """
    import httpx

    try:
        response = httpx.get(
            urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/deployments/regions"),
            timeout=10,
        )
        response.raise_for_status()
        response_json = response.json()
        if response_json is None or not isinstance(response_json, list):
            logger.error("Expect server to return a list ")
            return []
        if (
            response_json
            and response_json[0] is not None
            and not isinstance(response_json[0], dict)
        ):
            logger.error("Expect return values are dict's")
            return []
        return [
            {"name": region["name"], "code": region["code"]} for region in response_json
        ]
    except Exception as ex:
        logger.error(f"Unable to get regions due to {ex}.")
        return []
