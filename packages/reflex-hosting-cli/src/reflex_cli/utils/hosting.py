"""Hosting service related utilities."""

from __future__ import annotations

import contextlib
import dataclasses
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
import time
import uuid
import webbrowser
from collections.abc import Mapping
from enum import Enum
from http import HTTPStatus
from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import urljoin

import click

import reflex_cli.constants as constants
from reflex_cli.core.config import Config, RegionOption
from reflex_cli.utils import console, dependency
from reflex_cli.utils.dependency import is_valid_url
from reflex_cli.utils.exceptions import (
    GetAppError,
    NotAuthenticatedError,
    ResponseError,
    ScaleAppError,
    ScaleParamError,
)


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
            console.warn(
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
        console.error("Token is required for non-interactive mode.")
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


def get_existing_access_token() -> str:
    """Fetch the access token from the existing config if applicable.

    Returns:
        The access token.
        If not found, return empty string for it instead.

    """
    import os

    console.debug("Fetching token from existing config...")
    access_token = ""
    try:
        with constants.Hosting.HOSTING_JSON.open() as config_file:
            hosting_config = json.load(config_file)
            access_token = hosting_config.get("access_token", "")
    except Exception as ex:
        console.debug(
            f"Unable to fetch token from {constants.Hosting.HOSTING_JSON} due to: {ex}"
        )

    if not access_token:
        access_token = os.environ.get("REFLEX_ACCESS_TOKEN", "")
        if access_token:
            console.debug("Using REFLEX_ACCESS_TOKEN from environment")

    return access_token


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


def validate_token(token: str) -> dict[str, Any]:
    """Validate the token with the control plane.

    Args:
        token: The access token to validate.

    Returns:
        Information about the user associated with the token.

    Raises:
        ValueError: if access denied.
        Exception: if runs into timeout, failed requests, unexpected errors. These should be tried again.

    """
    import httpx

    try:
        # Add reflex-enterprise detection flag as query parameter
        params = {
            "source": "reflex-enterprise"
            if is_reflex_enterprise_installed()
            else "reflex"
        }

        response = httpx.post(
            urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/authenticate/me"),
            headers=authorization_header(token),
            params=params,
            timeout=constants.Hosting.TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as re:
        console.debug(f"Request to auth server failed due to {re}")
        raise Exception(str(re)) from re
    except httpx.HTTPError as ex:
        console.debug(f"Unable to validate the token due to: {ex}")
        raise Exception("server error") from ex
    except ValueError as ve:
        console.debug("Access denied")
        raise ValueError("access denied") from ve
    except Exception as ex:
        console.debug(f"Unexpected error: {ex}")
        raise Exception("internal errors") from ex


def delete_token_from_config():
    """Delete the invalid token from the config file if applicable."""
    if constants.Hosting.HOSTING_JSON.exists():
        try:
            with constants.Hosting.HOSTING_JSON.open("r") as config_file:
                hosting_config = json.load(config_file)
            hosting_config.pop("access_token", None)
            with constants.Hosting.HOSTING_JSON.open("w") as config_file:
                json.dump(hosting_config, config_file)
        except Exception as ex:
            # Best efforts removing invalid token is OK
            console.debug(
                f"Unable to delete the invalid token from config file, err: {ex}"
            )
    # Delete the previous hosting service data if present.
    if constants.Hosting.HOSTING_JSON_V0.exists():
        constants.Hosting.HOSTING_JSON_V0.unlink()


def save_token_to_config(token: str):
    """Best efforts cache the token to the config file.

    Args:
        token: The access token to save.

    """
    try:
        if not Path(constants.Reflex.DIR).exists():
            Path(constants.Reflex.DIR).mkdir(parents=True, exist_ok=True)
        hosting_config: dict[str, str] = {}
        if constants.Hosting.HOSTING_JSON.exists():
            try:
                with constants.Hosting.HOSTING_JSON.open("r") as config_file:
                    hosting_config = json.load(config_file)
            except (OSError, ValueError):
                hosting_config = {}
        hosting_config["access_token"] = token
        with constants.Hosting.HOSTING_JSON.open("w") as config_file:
            json.dump(hosting_config, config_file)
    except Exception as ex:
        console.warn(
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
        console.debug("No access token found from the existing config.")

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
    console.warn(conflict_warn_msg)
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
        console.error(
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
        console.error(
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
):
    """Create a new application.

    Args:
        app_name: The name of the application.
        description: The description of the application.
        project_id: The ID of the project to associate the application with.
        client: The authenticated client

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
    response = httpx.post(
        urljoin(constants.Hosting.HOSTING_SERVICE, "/api/v1/apps/"),
        json={"name": app_name, "description": description, "project": project_id},
        headers=authorization_header(client.token),
        timeout=constants.Hosting.TIMEOUT,
    )
    if response.status_code == HTTPStatus.FORBIDDEN:
        console.debug(f"Server responded with 403: {response.text}")
        raise ValueError(f"{response.text}")
    response.raise_for_status()
    response_json = response.json()
    return response_json


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
        console.debug(f"Server responded with 400: {response_json.get('detail')}")
        raise ValueError(f"{response_json.get('detail', 'bad request')}")
    if response.status_code == HTTPStatus.CONFLICT:
        console.debug(f"Duplicate project name: {response_json.get('detail')}")
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


def get_selected_project() -> str | None:
    """Retrieve the currently selected project ID.

    Returns:
        str | None: The ID of the selected project, or None if no project is selected.

    """
    try:
        with constants.Hosting.HOSTING_JSON.open() as config_file:
            hosting_config = json.load(config_file)
            return hosting_config.get("project")
    except Exception as ex:
        console.debug(
            f"Unable to fetch token from {constants.Hosting.HOSTING_JSON} due to: {ex}"
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

    Returns:
        The deployment id.git c

    Raises:
        NotAuthenticatedError: If the token is not valid.

    """
    import httpx

    if not isinstance(client, AuthenticatedClient):
        raise NotAuthenticatedError("not authenticated")
    cli_version = importlib.metadata.version("reflex-hosting-cli")
    zips = [
        (
            "files",
            (
                "backend.zip",
                (zip_dir / "backend.zip").open("rb"),
            ),
        ),
        (
            "files",
            (
                "frontend.zip",
                (zip_dir / "frontend.zip").open("rb"),
            ),
        ),
    ]
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
        console.warn("no app with given id found")
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
        console.warn(f"No application found with ID '{app_id}'")
        return None
    if not app:
        console.warn("no app with given id found")
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
                console.success(status)
                break
            if "build error" in status:
                console.warn(status)
                console.warn(
                    f"to see the build logs:\n reflex cloud apps build-logs {deployment_id}"
                )
                return False
            if "unable to find status for given id" in status:
                console.error(status)
                return False
            if "error" in status:
                console.warn(status)
                return False
            if "bad response" in status:
                console.warn(status)
                return True
            if status == current_status:
                continue
            current_status = status
            console.info(status)
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
        console.debug(f"Unable to fetch token due to request error: {re}")
    except httpx.HTTPError as he:
        console.debug(f"Unable to fetch token due to {he}")
    except json.JSONDecodeError as jde:
        console.debug(f"Server did not respond with valid json: {jde}")
    except KeyError as ke:
        console.debug(f"Server response format unexpected: {ke}")
    except Exception as ex:
        console.debug(f"Unexpected errors: {ex}")

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

    console.print(f"Opening {auth_url} ...")

    if not is_valid_url(constants.Hosting.HOSTING_SERVICE_UI):
        console.error(
            f"Invalid hosting URL: {constants.Hosting.HOSTING_SERVICE_UI}. Ensure the URL is in the correct format and includes a valid scheme"
        )
        raise click.exceptions.Exit(1)

    if not webbrowser.open(auth_url):
        console.warn(
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
        except ValueError:
            console.error("Access denied")
            delete_token_from_config()
        except Exception as ex:
            console.debug(f"Unable to validate token due to: {ex}")
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
        console.error("Please install PyYAML to use this command: pip install pyyaml")
        return

    if Path("cloud.yml").exists():
        console.error("cloud.yml already exists.")
        return

    try:
        authenticated_client = get_authenticated_client(
            token=token, interactive=interactive
        )
    except click.exceptions.Exit:
        console.error("Authentication required to generate prefilled config.")
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
        console.warn(f"Could not search for apps: {ex}")
        app = None

    if app:
        console.info(f"Found app '{app['name']}' - prefilling config with app data.")
        default = {"name": app["name"]}

        if app.get("id"):
            default["appid"] = app["id"]
        if app.get("description"):
            default["description"] = app["description"]
        if app.get("project_id"):
            default["project"] = app["project_id"]
    else:
        console.info(
            f"No app found with name '{current_dir_name}' - creating config with minimal defaults."
        )
        default = {"name": current_dir_name}

    with Path("cloud.yml").open("w") as config_file:
        yaml.dump(default, config_file, default_flow_style=False, sort_keys=False)
    console.success("cloud.yml created successfully.")
    console.info(
        "For more configuration options, see: https://reflex.dev/docs/hosting/config-file/"
    )
    return


def log_out_on_browser():
    """Open the browser to log out the user."""
    with contextlib.suppress(Exception):
        delete_token_from_config()
    console.print(f"Opening {constants.Hosting.HOSTING_SERVICE_UI} ...")
    if not webbrowser.open(constants.Hosting.HOSTING_SERVICE_UI):
        console.warn(
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
            console.error("Expect server to return a list ")
            return []
        if (
            response_json
            and response_json[0] is not None
            and not isinstance(response_json[0], dict)
        ):
            console.error("Expect return values are dict's")
            return []
    except Exception as ex:
        console.error(f"Unable to get vmtypes due to {ex}.")
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
            console.error("Expect server to return a list ")
            return []
        if (
            response_json
            and response_json[0] is not None
            and not isinstance(response_json[0], dict)
        ):
            console.error("Expect return values are dict's")
            return []
        return [
            {"name": region["name"], "code": region["code"]} for region in response_json
        ]
    except Exception as ex:
        console.error(f"Unable to get regions due to {ex}.")
        return []
