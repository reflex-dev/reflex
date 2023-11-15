"""Hosting service related utilities."""
from __future__ import annotations

import contextlib
import enum
import json
import os
import re
import time
import uuid
import webbrowser
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import List, Optional

import httpx
import websockets
from pydantic import Field, ValidationError, root_validator

from nextpy import constants
from nextpy.core.base import Base
from nextpy.core.config import get_config
from nextpy.utils import console

# TODO: Beware of potential issues with config's mutable nature. Currently, once the module is imported, constants are fixed to the initial config values. While this isn't problematic now, introducing features like dynamic configs (e.g., command line flags for cp_backend_url) would demand significant refactoring, as the imported config might not reflect the desired state.
config = get_config()
# Endpoint to create or update a deployment
POST_DEPLOYMENTS_ENDPOINT = f"{config.cp_backend_url}/deployments"
# Endpoint to get all deployments for the user
GET_DEPLOYMENTS_ENDPOINT = f"{config.cp_backend_url}/deployments"
# Endpoint to fetch information from backend in preparation of a deployment
POST_DEPLOYMENTS_PREPARE_ENDPOINT = f"{config.cp_backend_url}/deployments/prepare"
# Endpoint to authenticate current user
POST_VALIDATE_ME_ENDPOINT = f"{config.cp_backend_url}/authenticate/me"
# Endpoint to fetch a login token after user completes authentication on web
FETCH_TOKEN_ENDPOINT = f"{config.cp_backend_url}/authenticate"
# Endpoint to delete a deployment
DELETE_DEPLOYMENTS_ENDPOINT = f"{config.cp_backend_url}/deployments"
# Endpoint to get deployment status
GET_DEPLOYMENT_STATUS_ENDPOINT = f"{config.cp_backend_url}/deployments"
# Public endpoint to get the list of supported regions in hosting service
GET_REGIONS_ENDPOINT = f"{config.cp_backend_url}/deployments/regions"
# Websocket endpoint to stream logs of a deployment
DEPLOYMENT_LOGS_ENDPOINT = f'{config.cp_backend_url.replace("http", "ws")}/deployments'
# The HTTP endpoint to fetch logs of a deployment
POST_DEPLOYMENT_LOGS_ENDPOINT = f"{config.cp_backend_url}/deployments/logs"
# Expected server response time to new deployment request. In seconds.
DEPLOYMENT_PICKUP_DELAY = 30
# End of deployment workflow message. Used to determine if it is the last message from server.
END_OF_DEPLOYMENT_MESSAGES = ["deploy success"]
# How many iterations to try and print the deployment event messages from server during deployment.
DEPLOYMENT_EVENT_MESSAGES_RETRIES = 120
# Timeout limit for http requests
HTTP_REQUEST_TIMEOUT = 60  # seconds


def get_existing_access_token() -> tuple[str, str]:
    """Fetch the access token from the existing config if applicable.

    Returns:
        The access token and the invitation code.
        If either is not found, return empty string for it instead.
    """
    console.debug("Fetching token from existing config...")
    access_token = invitation_code = ""
    try:
        with open(constants.Hosting.HOSTING_JSON, "r") as config_file:
            hosting_config = json.load(config_file)
            access_token = hosting_config.get("access_token", "")
            invitation_code = hosting_config.get("code", "")
    except Exception as ex:
        console.debug(
            f"Unable to fetch token from {constants.Hosting.HOSTING_JSON} due to: {ex}"
        )
    return access_token, invitation_code


def validate_token(token: str):
    """Validate the token with the control plane.

    Args:
        token: The access token to validate.

    Raises:
        ValueError: if access denied.
        Exception: if runs into timeout, failed requests, unexpected errors. These should be tried again.
    """
    try:
        response = httpx.post(
            POST_VALIDATE_ME_ENDPOINT,
            headers=authorization_header(token),
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        if response.status_code == HTTPStatus.FORBIDDEN:
            raise ValueError
        response.raise_for_status()
    except httpx.RequestError as re:
        console.debug(f"Request to auth server failed due to {re}")
        raise Exception(str(re)) from re
    except httpx.HTTPError as ex:
        console.debug(f"Unable to validate the token due to: {ex}")
        raise Exception("server error") from ex
    except ValueError as ve:
        console.debug(f"Access denied for {token}")
        raise ValueError("access denied") from ve
    except Exception as ex:
        console.debug(f"Unexpected error: {ex}")
        raise Exception("internal errors") from ex


def delete_token_from_config(include_invitation_code: bool = False):
    """Delete the invalid token from the config file if applicable.

    Args:
        include_invitation_code:
            Whether to delete the invitation code as well.
            When user logs out, we delete the invitation code together.
    """
    if os.path.exists(constants.Hosting.HOSTING_JSON):
        hosting_config = {}
        try:
            with open(constants.Hosting.HOSTING_JSON, "w") as config_file:
                hosting_config = json.load(config_file)
                del hosting_config["access_token"]
                if include_invitation_code:
                    del hosting_config["code"]
                json.dump(hosting_config, config_file)
        except Exception as ex:
            # Best efforts removing invalid token is OK
            console.debug(
                f"Unable to delete the invalid token from config file, err: {ex}"
            )


def save_token_to_config(token: str, code: str | None = None):
    """Best efforts cache the token, and optionally invitation code to the config file.

    Args:
        token: The access token to save.
        code: The invitation code to save if exists.
    """
    hosting_config: dict[str, str] = {"access_token": token}
    if code:
        hosting_config["code"] = code
    try:
        with open(constants.Hosting.HOSTING_JSON, "w") as config_file:
            json.dump(hosting_config, config_file)
    except Exception as ex:
        console.warn(
            f"Unable to save token to {constants.Hosting.HOSTING_JSON} due to: {ex}"
        )


def requires_access_token() -> str:
    """Fetch the access token from the existing config if applicable.

    Returns:
        The access token. If not found, return empty string for it instead.
    """
    # Check if the user is authenticated

    access_token, _ = get_existing_access_token()
    if not access_token:
        console.debug("No access token found from the existing config.")

    return access_token


def authenticated_token() -> tuple[str, str]:
    """Fetch the access token from the existing config if applicable and validate it.

    Returns:
        The access token and the invitation code.
        If either is not found, return empty string for it instead.
    """
    # Check if the user is authenticated

    access_token, invitation_code = get_existing_access_token()
    if not access_token:
        console.debug("No access token found from the existing config.")
        access_token = ""
    elif not validate_token_with_retries(access_token):
        access_token = ""

    return access_token, invitation_code


def authorization_header(token: str) -> dict[str, str]:
    """Construct an authorization header with the specified token as bearer token.

    Args:
        token: The access token to use.

    Returns:
        The authorization header in dict format.
    """
    return {"Authorization": f"Bearer {token}"}


def requires_authenticated() -> str:
    """Check if the user is authenticated.

    Returns:
        The validated access token or empty string if not authenticated.
    """
    access_token, invitation_code = authenticated_token()
    if access_token:
        return access_token
    return authenticate_on_browser(invitation_code)


class DeploymentPrepInfo(Base):
    """The params/settings returned from the prepare endpoint
    including the deployment key and the frontend/backend URLs once deployed.
    The key becomes part of both frontend and backend URLs.
    """

    # The deployment key
    key: str
    # The backend URL
    api_url: str
    # The frontend URL
    deploy_url: str


class DeploymentPrepareResponse(Base):
    """The params/settings returned from the prepare endpoint,
    used in the CLI for the subsequent launch request.
    """

    # The app prefix, used on the server side only
    app_prefix: str
    # The reply from the server for a prepare request to deploy over a particular key
    # If reply is not None, it means server confirms the key is available for use.
    reply: Optional[DeploymentPrepInfo] = None
    # The list of existing deployments by the user under the same app name.
    # This is used to allow easy upgrade case when user attempts to deploy
    # in the same named app directory, user intends to upgrade the existing deployment.
    existing: Optional[List[DeploymentPrepInfo]] = None
    # The suggested key name based on the app name.
    # This is for a new deployment, user has not deployed this app before.
    # The server returns key suggestion based on the app name.
    suggestion: Optional[DeploymentPrepInfo] = None
    enabled_regions: Optional[List[str]] = None

    @root_validator(pre=True)
    def ensure_at_least_one_deploy_params(cls, values):
        """Ensure at least one set of param is returned for any of the cases we try to prepare.

        Args:
            values: The values passed in.

        Raises:
            ValueError: If all of the optional fields are None.

        Returns:
            The values passed in.
        """
        if (
            values.get("reply") is None
            and not values.get("existing")  # existing cannot be an empty list either
            and values.get("suggestion") is None
        ):
            raise ValueError(
                "At least one set of params for deploy is required from control plane."
            )
        return values


class DeploymentsPreparePostParam(Base):
    """Params for app API URL creation backend API."""

    # The app name which is found in the config
    app_name: str
    # The deployment key
    key: Optional[str] = None  #  name of the deployment
    # The frontend hostname to deploy to. This is used to deploy at hostname not in the regular domain.
    frontend_hostname: Optional[str] = None


def prepare_deploy(
    app_name: str,
    key: str | None = None,
    frontend_hostname: str | None = None,
) -> DeploymentPrepareResponse:
    """Send a POST request to Control Plane to prepare a new deployment.
    Control Plane checks if there is conflict with the key if provided.
    If the key is absent, it will return existing deployments and a suggested name based on the app_name in the request.

    Args:
        key: The deployment name.
        app_name: The app name.
        frontend_hostname: The frontend hostname to deploy to. This is used to deploy at hostname not in the regular domain.

    Raises:
        Exception: If the operation fails. The exception message is the reason.

    Returns:
        The response containing the backend URLs if successful, None otherwise.
    """
    # Check if the user is authenticated
    if not (token := requires_authenticated()):
        raise Exception("not authenticated")
    try:
        response = httpx.post(
            POST_DEPLOYMENTS_PREPARE_ENDPOINT,
            headers=authorization_header(token),
            json=DeploymentsPreparePostParam(
                app_name=app_name, key=key, frontend_hostname=frontend_hostname
            ).dict(exclude_none=True),
            timeout=HTTP_REQUEST_TIMEOUT,
        )

        response_json = response.json()
        console.debug(f"Response from prepare endpoint: {response_json}")
        if response.status_code == HTTPStatus.FORBIDDEN:
            console.debug(f'Server responded with 403: {response_json.get("detail")}')
            raise ValueError(f'{response_json.get("detail", "forbidden")}')
        response.raise_for_status()
        return DeploymentPrepareResponse(
            app_prefix=response_json["app_prefix"],
            reply=response_json["reply"],
            suggestion=response_json["suggestion"],
            existing=response_json["existing"],
            enabled_regions=response_json.get("enabled_regions"),
        )
    except httpx.RequestError as re:
        console.error(f"Unable to prepare launch due to {re}.")
        raise Exception(str(re)) from re
    except httpx.HTTPError as he:
        console.error(f"Unable to prepare deploy due to {he}.")
        raise Exception(f"{he}") from he
    except json.JSONDecodeError as jde:
        console.error(f"Server did not respond with valid json: {jde}")
        raise Exception("internal errors") from jde
    except (KeyError, ValidationError) as kve:
        console.error(f"The server response format is unexpected {kve}")
        raise Exception("internal errors") from kve
    except ValueError as ve:
        # This is a recognized client error, currently indicates forbidden
        raise Exception(f"{ve}") from ve
    except Exception as ex:
        console.error(f"Unexpected error: {ex}.")
        raise Exception("internal errors") from ex


class DeploymentPostResponse(Base):
    """The URL for the deployed site."""

    # The frontend URL
    frontend_url: str = Field(..., regex=r"^https?://", min_length=8)
    # The backend URL
    backend_url: str = Field(..., regex=r"^https?://", min_length=8)


class DeploymentsPostParam(Base):
    """Params for hosted instance deployment POST request."""

    # Key is the name of the deployment, it becomes part of the URL
    key: str = Field(..., regex=r"^[a-z0-9-]+$")
    # Name of the app
    app_name: str = Field(..., min_length=1)
    # json encoded list of regions to deploy to
    regions_json: str = Field(..., min_length=1)
    # The app prefix, used on the server side only
    app_prefix: str = Field(..., min_length=1)
    # The version of nextpy CLI used to deploy
    nextpy_version: str = Field(..., min_length=1)
    # The number of CPUs
    cpus: Optional[int] = None
    # The memory in MB
    memory_mb: Optional[int] = None
    # Whether to auto start the hosted deployment
    auto_start: Optional[bool] = None
    # Whether to auto stop the hosted deployment when idling
    auto_stop: Optional[bool] = None
    # The frontend hostname to deploy to. This is used to deploy at hostname not in the regular domain.
    frontend_hostname: Optional[str] = None
    # The description of the deployment
    description: Optional[str] = None
    # The json encoded list of environment variables
    envs_json: Optional[str] = None
    # The command line prefix for tracing
    nextpy_cli_entrypoint: Optional[str] = None
    # The metrics endpoint
    metrics_endpoint: Optional[str] = None


def deploy(
    frontend_file_name: str,
    backend_file_name: str,
    export_dir: str,
    key: str,
    app_name: str,
    regions: list[str],
    app_prefix: str,
    vm_type: str | None = None,
    cpus: int | None = None,
    memory_mb: int | None = None,
    auto_start: bool | None = None,
    auto_stop: bool | None = None,
    frontend_hostname: str | None = None,
    envs: dict[str, str] | None = None,
    with_tracing: str | None = None,
    with_metrics: str | None = None,
) -> DeploymentPostResponse:
    """Send a POST request to Control Plane to launch a new deployment.

    Args:
        frontend_file_name: The frontend file name.
        backend_file_name: The backend file name.
        export_dir: The directory where the frontend/backend zip files are exported.
        key: The deployment name.
        app_name: The app name.
        regions: The list of regions to deploy to.
        app_prefix: The app prefix.
        vm_type: The VM type.
        cpus: The number of CPUs.
        memory_mb: The memory in MB.
        auto_start: Whether to auto start.
        auto_stop: Whether to auto stop.
        frontend_hostname: The frontend hostname to deploy to. This is used to deploy at hostname not in the regular domain.
        envs: The environment variables.
        with_tracing: A string indicating the command line prefix for tracing.
        with_metrics: A string indicating the metrics endpoint.

    Raises:
        AssertionError: If the request is rejected by the hosting server.
        Exception: If the operation fails. The exception message is the reason.

    Returns:
        The response containing the URL of the site to be deployed if successful, None otherwise.
    """
    # Check if the user is authenticated
    if not (token := requires_access_token()):
        raise Exception("not authenticated")

    try:
        params = DeploymentsPostParam(
            key=key,
            app_name=app_name,
            regions_json=json.dumps(regions),
            app_prefix=app_prefix,
            cpus=cpus,
            memory_mb=memory_mb,
            auto_start=auto_start,
            auto_stop=auto_stop,
            envs_json=json.dumps(envs) if envs else None,
            frontend_hostname=frontend_hostname,
            nextpy_version=constants.Nextpy.VERSION,
            nextpy_cli_entrypoint=with_tracing,
            metrics_endpoint=with_metrics,
        )
        with open(
            os.path.join(export_dir, frontend_file_name), "rb"
        ) as frontend_file, open(
            os.path.join(export_dir, backend_file_name), "rb"
        ) as backend_file:
            # https://docs.python-requests.org/en/latest/user/advanced/#post-multiple-multipart-encoded-files
            files = [
                ("files", (frontend_file_name, frontend_file)),
                ("files", (backend_file_name, backend_file)),
            ]
            response = httpx.post(
                POST_DEPLOYMENTS_ENDPOINT,
                headers=authorization_header(token),
                data=params.dict(exclude_none=True),
                files=files,
            )
        # If the server explicitly states bad request,
        # display a different error
        if response.status_code == HTTPStatus.BAD_REQUEST:
            raise AssertionError(f"Server rejected this request: {response.text}")
        response.raise_for_status()
        response_json = response.json()
        return DeploymentPostResponse(
            frontend_url=response_json["frontend_url"],
            backend_url=response_json["backend_url"],
        )
    except OSError as oe:
        console.error(f"Client side error related to file operation: {oe}")
        raise
    except httpx.RequestError as re:
        console.error(f"Unable to deploy due to request error: {re}")
        raise Exception("request error") from re
    except httpx.HTTPError as he:
        console.error(f"Unable to deploy due to {he}.")
        raise Exception(str) from he
    except json.JSONDecodeError as jde:
        console.error(f"Server did not respond with valid json: {jde}")
        raise Exception("internal errors") from jde
    except (KeyError, ValidationError) as kve:
        console.error(f"Post params or server response format unexpected: {kve}")
        raise Exception("internal errors") from kve
    except AssertionError as ve:
        console.error(f"Unable to deploy due to request error: {ve}")
        # re-raise the error back to the user as client side error
        raise
    except Exception as ex:
        console.error(f"Unable to deploy due to internal errors: {ex}.")
        raise Exception("internal errors") from ex


class DeploymentsGetParam(Base):
    """Params for hosted instance GET request."""

    # The app name which is found in the config
    app_name: Optional[str]


def list_deployments(
    app_name: str | None = None,
) -> list[dict]:
    """Send a GET request to Control Plane to list deployments.

    Args:
        app_name: the app name as an optional filter when listing deployments.

    Raises:
        Exception: If the operation fails. The exception message shows the reason.

    Returns:
        The list of deployments if successful, None otherwise.
    """
    if not (token := requires_authenticated()):
        raise Exception("not authenticated")

    params = DeploymentsGetParam(app_name=app_name)

    try:
        response = httpx.get(
            GET_DEPLOYMENTS_ENDPOINT,
            headers=authorization_header(token),
            params=params.dict(exclude_none=True),
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as re:
        console.error(f"Unable to list deployments due to request error: {re}")
        raise Exception("request timeout") from re
    except httpx.HTTPError as he:
        console.error(f"Unable to list deployments due to {he}.")
        raise Exception("internal errors") from he
    except (ValidationError, KeyError, json.JSONDecodeError) as vkje:
        console.error(f"Server response format unexpected: {vkje}")
        raise Exception("internal errors") from vkje
    except Exception as ex:
        console.error(f"Unexpected error: {ex}.")
        raise Exception("internal errors") from ex


def fetch_token(request_id: str) -> tuple[str, str]:
    """Fetch the access token for the request_id from Control Plane.

    Args:
        request_id: The request ID used when the user opens the browser for authentication.

    Returns:
        The access token if it exists, None otherwise.
    """
    access_token = invitation_code = ""
    try:
        resp = httpx.get(
            f"{FETCH_TOKEN_ENDPOINT}/{request_id}",
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        access_token = (resp_json := resp.json()).get("access_token", "")
        invitation_code = resp_json.get("code", "")
    except httpx.RequestError as re:
        console.debug(f"Unable to fetch token due to request error: {re}")
    except httpx.HTTPError as he:
        console.debug(f"Unable to fetch token due to {he}")
    except json.JSONDecodeError as jde:
        console.debug(f"Server did not respond with valid json: {jde}")
    except KeyError as ke:
        console.debug(f"Server response format unexpected: {ke}")
    except Exception:
        console.debug("Unexpected errors: {ex}")

    return access_token, invitation_code


def poll_backend(backend_url: str) -> bool:
    """Poll the backend to check if it is up.

    Args:
        backend_url: The URL of the backend to poll.

    Returns:
        True if the backend is up, False otherwise.
    """
    try:
        console.debug(f"Polling backend at {backend_url}")
        resp = httpx.get(f"{backend_url}/ping", timeout=1)
        resp.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def poll_frontend(frontend_url: str) -> bool:
    """Poll the frontend to check if it is up.

    Args:
        frontend_url: The URL of the frontend to poll.

    Returns:
        True if the frontend is up, False otherwise.
    """
    try:
        console.debug(f"Polling frontend at {frontend_url}")
        resp = httpx.get(f"{frontend_url}", timeout=1)
        resp.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


class DeploymentDeleteParam(Base):
    """Params for hosted instance DELETE request."""

    # key is the name of the deployment, it becomes part of the site URL
    key: str


def delete_deployment(key: str):
    """Send a DELETE request to Control Plane to delete a deployment.

    Args:
        key: The deployment name.

    Raises:
        ValueError: If the key is not provided.
        Exception: If the operation fails. The exception message is the reason.
    """
    if not (token := requires_authenticated()):
        raise Exception("not authenticated")
    if not key:
        raise ValueError("Valid key is required for the delete.")

    try:
        response = httpx.delete(
            f"{DELETE_DEPLOYMENTS_ENDPOINT}/{key}",
            headers=authorization_header(token),
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        response.raise_for_status()

    except httpx.TimeoutException as te:
        console.error("Unable to delete deployment due to request timeout.")
        raise Exception("request timeout") from te
    except httpx.HTTPError as he:
        console.error(f"Unable to delete deployment due to {he}.")
        raise Exception("internal errors") from he
    except Exception as ex:
        console.error(f"Unexpected errors {ex}.")
        raise Exception("internal errors") from ex


class SiteStatus(Base):
    """Deployment status info."""

    # The frontend URL
    frontend_url: Optional[str] = None
    # The backend URL
    backend_url: Optional[str] = None
    # Whether the frontend/backend URL is reachable
    reachable: bool
    # The last updated iso formatted timestamp if site is reachable
    updated_at: Optional[str] = None

    @root_validator(pre=True)
    def ensure_one_of_urls(cls, values):
        """Ensure at least one of the frontend/backend URLs is provided.

        Args:
            values: The values passed in.

        Raises:
            ValueError: If none of the URLs is provided.

        Returns:
            The values passed in.
        """
        if values.get("frontend_url") is None and values.get("backend_url") is None:
            raise ValueError("At least one of the URLs is required.")
        return values


class DeploymentStatusResponse(Base):
    """Response for deployment status request."""

    # The frontend status
    frontend: SiteStatus
    # The backend status
    backend: SiteStatus


def get_deployment_status(key: str) -> DeploymentStatusResponse:
    """Get the deployment status.

    Args:
        key: The deployment name.

    Raises:
        ValueError: If the key is not provided.
        Exception: If the operation fails. The exception message is the reason.

    Returns:
        The deployment status response including backend and frontend.
    """
    if not key:
        raise ValueError(
            "A non empty key is required for querying the deployment status."
        )

    if not (token := requires_authenticated()):
        raise Exception("not authenticated")

    try:
        response = httpx.get(
            f"{GET_DEPLOYMENT_STATUS_ENDPOINT}/{key}/status",
            headers=authorization_header(token),
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        response_json = response.json()
        return DeploymentStatusResponse(
            frontend=SiteStatus(
                frontend_url=response_json["frontend"]["url"],
                reachable=response_json["frontend"]["reachable"],
                updated_at=response_json["frontend"]["updated_at"],
            ),
            backend=SiteStatus(
                backend_url=response_json["backend"]["url"],
                reachable=response_json["backend"]["reachable"],
                updated_at=response_json["backend"]["updated_at"],
            ),
        )
    except Exception as ex:
        console.error(f"Unable to get deployment status due to {ex}.")
        raise Exception("internal errors") from ex


def convert_to_local_time_with_tz(iso_timestamp: str) -> datetime | None:
    """Helper function to convert the iso timestamp to local time.

    Args:
        iso_timestamp: The iso timestamp to convert.

    Returns:
        The converted timestamp with timezone.
    """
    try:
        return datetime.fromisoformat(iso_timestamp).astimezone()
    except (TypeError, ValueError) as ex:
        console.error(f"Unable to convert iso timestamp {iso_timestamp} due to {ex}.")
        return None


def convert_to_local_time_str(iso_timestamp: str) -> str:
    """Convert the iso timestamp to local time.

    Args:
        iso_timestamp: The iso timestamp to convert.

    Returns:
        The converted timestamp string.
    """
    if (local_dt := convert_to_local_time_with_tz(iso_timestamp)) is None:
        return iso_timestamp
    return local_dt.strftime("%Y-%m-%d %H:%M:%S.%f %Z")


class LogType(str, enum.Enum):
    """Enum for log types."""

    # Logs printed from the user code, the "app"
    APP_LOG = "app"
    # Build logs are the server messages while building/running user deployment
    BUILD_LOG = "build"
    # Deploy logs are specifically for the messages at deploy time
    # returned to the user the current stage of the deployment, such as building, uploading.
    DEPLOY_LOG = "deploy"
    # All the logs which can be printed by all above types.
    ALL_LOG = "all"


async def get_logs(
    key: str,
    log_type: LogType = LogType.APP_LOG,
    from_iso_timestamp: datetime | None = None,
):
    """Get the deployment logs and stream on console.

    Args:
        key: The deployment name.
        log_type: The type of logs to query from server.
                  See the LogType definitions for how they are used.
        from_iso_timestamp: An optional timestamp with timezone info to limit
                            where the log queries should start from.

    Raises:
        ValueError: If the key is not provided.
        Exception: If the operation fails. The exception message is the reason.

    """
    if not (token := requires_authenticated()):
        raise Exception("not authenticated")
    if not key:
        raise ValueError("Valid key is required for querying logs.")
    try:
        logs_endpoint = f"{DEPLOYMENT_LOGS_ENDPOINT}/{key}/logs?access_token={token}&log_type={log_type.value}"
        console.debug(f"log server endpoint: {logs_endpoint}")
        if from_iso_timestamp is not None:
            logs_endpoint += (
                f"&from_iso_timestamp={from_iso_timestamp.astimezone().isoformat()}"
            )
        _ws = websockets.connect(logs_endpoint)  # type: ignore
        async with _ws as ws:
            while True:
                row_json = json.loads(await ws.recv())
                console.debug(f"Server responded with logs: {row_json}")
                if row_json and isinstance(row_json, dict):
                    row_to_print = {}
                    for k, v in row_json.items():
                        if v is None:
                            row_to_print[k] = str(v)
                        elif k == "timestamp":
                            row_to_print[k] = convert_to_local_time_str(v)
                        else:
                            row_to_print[k] = v
                    print(" | ".join(row_to_print.values()))
                else:
                    console.debug("Server responded, no new logs, this is normal")
    except Exception as ex:
        console.debug(f"Unable to get more deployment logs due to {ex}.")
        console.print("Log server disconnected ...")
        console.print(
            "Note that the server has limit to only stream logs for several minutes"
        )


def check_requirements_txt_exist() -> bool:
    """Check if requirements.txt exists in the top level app directory.

    Returns:
        True if requirements.txt exists, False otherwise.
    """
    return os.path.exists(constants.RequirementsTxt.FILE)


def check_requirements_for_non_nextpy_packages() -> bool:
    """Check the requirements.txt file for packages other than nextpy.

    Returns:
        True if packages other than nextpy are found, False otherwise.
    """
    if not check_requirements_txt_exist():
        return False
    try:
        with open(constants.RequirementsTxt.FILE) as fp:
            for req_line in fp.readlines():
                package_name = re.search(r"^([^=<>!~]+)", req_line.lstrip())
                # If we find a package that is not nextpy
                if (
                    package_name
                    and package_name.group(1) != constants.Nextpy.MODULE_NAME
                ):
                    return True
    except Exception as ex:
        console.warn(f"Unable to scan requirements.txt for dependencies due to {ex}")

    return False


def authenticate_on_browser(invitation_code: str) -> str:
    """Open the browser to authenticate the user.

    Args:
        invitation_code: The invitation code if it exists.

    Returns:
        The access token if valid, empty otherwise.
    """
    console.print(f"Opening {config.cp_web_url} ...")
    request_id = uuid.uuid4().hex
    auth_url = f"{config.cp_web_url}?request-id={request_id}&code={invitation_code}"
    if not webbrowser.open(auth_url):
        console.warn(
            f"Unable to automatically open the browser. Please go to {auth_url} to authenticate."
        )
    access_token = invitation_code = ""
    with console.status("Waiting for access token ..."):
        for _ in range(constants.Hosting.WEB_AUTH_RETRIES):
            access_token, invitation_code = fetch_token(request_id)
            if access_token:
                break
            else:
                time.sleep(constants.Hosting.WEB_AUTH_SLEEP_DURATION)

    if access_token and validate_token_with_retries(access_token):
        save_token_to_config(access_token, invitation_code)
    else:
        access_token = ""
    return access_token


def validate_token_with_retries(access_token: str) -> bool:
    """Validate the access token with retries.

    Args:
        access_token: The access token to validate.

    Returns:
        True if the token is valid,
        False if invalid or unable to validate.
    """
    with console.status("Validating access token ..."):
        for _ in range(constants.Hosting.WEB_AUTH_RETRIES):
            try:
                validate_token(access_token)
                return True
            except ValueError:
                console.error(f"Access denied")
                delete_token_from_config()
                break
            except Exception as ex:
                console.debug(f"Unable to validate token due to: {ex}, trying again")
                time.sleep(constants.Hosting.WEB_AUTH_SLEEP_DURATION)
    return False


def is_valid_deployment_key(key: str):
    """Helper function to check if the deployment key is valid. Must be a domain name safe string.

    Args:
        key: The deployment key to check.

    Returns:
        True if the key contains only domain name safe characters, False otherwise.
    """
    return re.match(r"^[a-zA-Z0-9-]*$", key)


def interactive_get_deployment_key_from_user_input(
    pre_deploy_response: DeploymentPrepareResponse,
    app_name: str,
    frontend_hostname: str | None = None,
) -> tuple[str, str, str]:
    """Interactive get the deployment key from user input.

    Args:
        pre_deploy_response: The response from the initial prepare call to server.
        app_name: The app name.
        frontend_hostname: The frontend hostname to deploy to. This is used to deploy at hostname not in the regular domain.

    Returns:
        The deployment key, backend URL, frontend URL.
    """
    key_candidate = api_url = deploy_url = ""
    if reply := pre_deploy_response.reply:
        api_url = reply.api_url
        deploy_url = reply.deploy_url
        key_candidate = reply.key
    elif pre_deploy_response.existing:
        # validator already checks existing field is not empty list
        # Note: keeping this simple as we only allow one deployment per app
        existing = pre_deploy_response.existing[0]
        console.print(f"Overwrite deployment [ {existing.key} ] ...")
        key_candidate = existing.key
        api_url = existing.api_url
        deploy_url = existing.deploy_url
    elif suggestion := pre_deploy_response.suggestion:
        key_candidate = suggestion.key
        api_url = suggestion.api_url
        deploy_url = suggestion.deploy_url

        # If user takes the suggestion, we will use the suggested key and proceed
        while key_input := console.ask(
            f"Choose a name for your deployed app. Enter to use default.",
            default=key_candidate,
        ):
            if not is_valid_deployment_key(key_input):
                console.error(
                    "Invalid key input, should only contain domain name safe characters: letters, digits, or hyphens."
                )
                continue

            elif any(x.isupper() for x in key_input):
                key_input = key_input.lower()
                console.info(
                    f"Domain name is case insensitive, automatically converting to all lower cases: {key_input}"
                )

            try:
                pre_deploy_response = prepare_deploy(
                    app_name,
                    key=key_input,
                    frontend_hostname=frontend_hostname,
                )
                if (
                    pre_deploy_response.reply is None
                    or key_input != pre_deploy_response.reply.key
                ):
                    # Rejected by server, try again
                    continue
                key_candidate = pre_deploy_response.reply.key
                api_url = pre_deploy_response.reply.api_url
                deploy_url = pre_deploy_response.reply.deploy_url
                # we get the confirmation, so break from the loop
                break
            except Exception:
                console.error(
                    "Cannot deploy at this name, try picking a different name"
                )

    return key_candidate, api_url, deploy_url


def process_envs(envs: list[str]) -> dict[str, str]:
    """Process the environment variables.

    Args:
        envs: The environment variables expected in key=value format.

    Raises:
        SystemExit: If the envs are not in valid format.

    Returns:
        The processed environment variables in a dict.
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


def log_out_on_browser():
    """Open the browser to authenticate the user."""
    # Fetching existing invitation code so user sees the log out page without having to enter it
    invitation_code = None
    with contextlib.suppress(Exception):
        _, invitation_code = get_existing_access_token()
        console.debug("Found existing invitation code in config")
        delete_token_from_config()
    console.print(f"Opening {config.cp_web_url} ...")
    if not webbrowser.open(f"{config.cp_web_url}?code={invitation_code}"):
        console.warn(
            f"Unable to open the browser automatically. Please go to {config.cp_web_url} to log out."
        )


def poll_deploy_milestones(key: str, from_iso_timestamp: datetime) -> bool | None:
    """Periodically poll the hosting server for deploy milestones.

    Args:
        key: The deployment key.
        from_iso_timestamp: The timestamp of the deployment request time, this helps with the milestone query.

    Raises:
        ValueError: If a non-empty key is not provided.
        Exception: If the user is not authenticated.

    Returns:
        False if server reports back failure, True otherwise. None if do not receive the end of deployment message.
    """
    if not key:
        raise ValueError("Non-empty key is required for querying deploy status.")
    if not (token := requires_authenticated()):
        raise Exception("not authenticated")

    for _ in range(DEPLOYMENT_EVENT_MESSAGES_RETRIES):
        try:
            response = httpx.post(
                POST_DEPLOYMENT_LOGS_ENDPOINT,
                json={
                    "key": key,
                    "log_type": LogType.DEPLOY_LOG.value,
                    "from_iso_timestamp": from_iso_timestamp.astimezone().isoformat(),
                },
                headers=authorization_header(token),
            )
            response.raise_for_status()
            # The return is expected to be a list of dicts
            response_json = response.json()
            for row in response_json:
                console.print(
                    " | ".join(
                        [
                            convert_to_local_time_str(row["timestamp"]),
                            row["message"],
                        ]
                    )
                )
                # update the from timestamp to the last timestamp of received message
                if (
                    maybe_timestamp := convert_to_local_time_with_tz(row["timestamp"])
                ) is not None:
                    console.debug(
                        f"Updating from {from_iso_timestamp} to {maybe_timestamp}"
                    )
                    # Add a small delta so does not poll the same logs
                    from_iso_timestamp = maybe_timestamp + timedelta(microseconds=1e5)
                else:
                    console.warn(f"Unable to parse timestamp {row['timestamp']}")
                server_message = row["message"].lower()
                if "fail" in server_message:
                    console.debug(
                        "Received failure message, stop event message streaming"
                    )
                    return False
                if any(msg in server_message for msg in END_OF_DEPLOYMENT_MESSAGES):
                    console.debug(
                        "Received end of deployment message, stop event message streaming"
                    )
                    return True
            time.sleep(1)
        except httpx.HTTPError as he:
            # This includes HTTP server and client error
            console.debug(f"Unable to get more deployment events due to {he}.")
        except Exception as ex:
            console.warn(f"Unable to parse server response due to {ex}.")


async def display_deploy_milestones(key: str, from_iso_timestamp: datetime) -> bool:
    """Display the deploy milestone messages reported back from the hosting server.

    Args:
        key: The deployment key.
        from_iso_timestamp: The timestamp of the deployment request time, this helps with the milestone query.

    Raises:
        ValueError: If a non-empty key is not provided.
        Exception: If the user is not authenticated.

    Returns:
        False if server reports back failure, True otherwise.
    """
    if not key:
        raise ValueError("Non-empty key is required for querying deploy status.")
    if not (token := requires_authenticated()):
        raise Exception("not authenticated")

    try:
        logs_endpoint = f"{DEPLOYMENT_LOGS_ENDPOINT}/{key}/logs?access_token={token}&log_type={LogType.DEPLOY_LOG.value}&from_iso_timestamp={from_iso_timestamp.astimezone().isoformat()}"
        console.debug(f"log server endpoint: {logs_endpoint}")
        _ws = websockets.connect(logs_endpoint)  # type: ignore
        async with _ws as ws:
            # Stream back the deploy events reported back from the server
            for _ in range(DEPLOYMENT_EVENT_MESSAGES_RETRIES):
                row_json = json.loads(await ws.recv())
                console.debug(f"Server responded with: {row_json}")
                if row_json and isinstance(row_json, dict):
                    # Only show the timestamp and actual message
                    console.print(
                        " | ".join(
                            [
                                convert_to_local_time_str(row_json["timestamp"]),
                                row_json["message"],
                            ]
                        )
                    )
                    server_message = row_json["message"].lower()
                    if "fail" in server_message:
                        console.debug(
                            "Received failure message, stop event message streaming"
                        )
                        return False
                    if any(msg in server_message for msg in END_OF_DEPLOYMENT_MESSAGES):
                        console.debug(
                            "Received end of deployment message, stop event message streaming"
                        )
                        return True
                else:
                    console.debug("Server responded, no new events yet, this is normal")
    except Exception as ex:
        console.debug(f"Unable to get more deployment events due to {ex}.")
    return False


def wait_for_server_to_pick_up_request():
    """Wait for server to pick up the request. Right now is just sleep."""
    with console.status(
        f"Waiting for server to pick up request ~ {DEPLOYMENT_PICKUP_DELAY} seconds ..."
    ):
        for _ in range(DEPLOYMENT_PICKUP_DELAY):
            time.sleep(1)


def interactive_prompt_for_envs() -> list[str]:
    """Interactive prompt for environment variables.

    Returns:
        The list of environment variables in key=value string format.
    """
    envs = []
    envs_finished = False
    env_count = 1
    env_key_prompt = f" * env-{env_count} name (enter to skip)"
    console.print("Environment variables for your production App ...")
    while not envs_finished:
        env_key = console.ask(env_key_prompt)
        if not env_key:
            envs_finished = True
            if envs:
                console.print("Finished adding envs.")
            else:
                console.print("No envs added. Continuing ...")
            break
        # If it possible to have empty values for env, so we do not check here
        env_value = console.ask(f"   env-{env_count} value")
        envs.append(f"{env_key}={env_value}")
        env_count += 1
        env_key_prompt = f" * env-{env_count} name (enter to skip)"
    return envs


def get_regions() -> list[dict]:
    """Get the supported regions from the hosting server.

    Returns:
        A list of dict representation of the region information.
    """
    try:
        response = httpx.get(
            GET_REGIONS_ENDPOINT,
            timeout=HTTP_REQUEST_TIMEOUT,
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
        return response_json
    except Exception as ex:
        console.error(f"Unable to get regions due to {ex}.")
        return []
