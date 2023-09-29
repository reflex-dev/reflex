"""Hosting related utilities."""
import json
import os
from http import HTTPStatus
from typing import Optional

import httpx
from pydantic import BaseModel, Field, root_validator

from reflex import constants
from reflex.config import get_config
from reflex.utils import console

config = get_config()

POST_DEPLOYMENTS_ENDPOINT = f"{config.cp_backend_url}/deployments"
POST_APPS_ENDPOINT = f"{config.cp_backend_url}/apps"
GET_APPS_ENDPOINT = f"{config.cp_backend_url}/apps"
GET_DEPLOYMENTS_ENDPOINT = f"{config.cp_backend_url}/deployments"
POST_DEPLOYMENTS_PREPARE_ENDPOINT = f"{config.cp_backend_url}/deployments/prepare"
POST_VALIDATE_ME_ENDPOINT = f"{config.cp_backend_url}/validate/me"
FETCH_TOKEN_ENDPOINT = f"{config.cp_backend_url}/validate"
DELETE_DEPLOYMENTS_ENDPOINT = f"{config.cp_backend_url}/deployments"


class DeploymentPrepareResponse(BaseModel):
    """The params/settings returned from the prepare endpoint,
    used in the CLI for the subsequent launch request.
    """

    app_prefix: str
    api_url: Optional[str]
    suggested_key_and_api_url: Optional[tuple[str, str]]
    existing_deployments_same_app_and_api_urls: Optional[list[tuple[str, str]]]

    @root_validator(pre=True)
    def ensure_at_least_one_api_url(cls, values):
        """Ensure at least one API_URL is returned for any of the cases we try to prepare.

        Args:
            values: The values passed in.

        Raises:
            ValueError: If all of the API_URLs are None.

        Returns:
            The values passed in.
        """
        if (
            values.get("api_url") is None
            and values.get("suggested_key_and_api_url") is None
            and values.get("existing_deployments_same_app_and_api_urls") is None
        ):
            raise ValueError("At least one API_URL is required from control plane.")
        return values


class DeploymentGetResponse(BaseModel):
    """The params/settings returned from the GET endpoint."""

    key: str
    regions: list[str]
    app_name: str
    vm_type: str
    cpus: int
    memory_mb: int
    url: str
    envs: list[str]


class DeploymentPostResponse(BaseModel):
    """The URL for the deployed site."""

    url: str


class DeploymentsPreparePostParam(BaseModel):
    """Params for app API URL creation backend API."""

    key: Optional[str]  # the deployment name
    app_name: Optional[str] = None


class AppsPostParam(BaseModel):
    """Params for project creation POST request."""

    name: str
    description: Optional[str] = None


class AppsGetParam(BaseModel):
    """Params for projects GET request."""

    name: str


class AppGetResponse(BaseModel):
    """The params/settings returned from the GET endpoint."""

    name: str


class DeploymentsPostParam(BaseModel):
    """Params for hosted instance deployment POST request."""

    # key is the name of the deployment, it becomes part of the URL
    key: str = Field(..., regex=r"^[a-zA-Z0-9-]+$")
    app_name: str = Field(..., min_length=1)
    regions_json: str = Field(..., min_length=1)
    app_prefix: str = Field(..., min_length=1)
    reflex_version: str = Field(..., min_length=1)
    cpus: Optional[int] = None
    memory_mb: Optional[int] = None
    auto_start: Optional[bool] = None
    auto_stop: Optional[bool] = None
    description: Optional[str] = None
    envs_json: Optional[str] = None


class DeploymentsGetParam(BaseModel):
    """Params for hosted instance GET request."""

    app_name: Optional[str]


class DeploymentDeleteParam(BaseModel):
    """Params for hosted instance DELETE request."""

    key: str


def get_existing_access_token() -> Optional[str]:
    """Fetch the access token from the existing config if applicable.

    Returns:
        The access token if it exists, None otherwise.
    """
    token = None
    if os.path.exists(constants.Hosting.HOSTING_JSON):
        console.debug("Fetching token from existing config.")
        try:
            with open(constants.Hosting.HOSTING_JSON, "r") as config_file:
                hosting_config = json.load(config_file)
                token = hosting_config.get("access_token")
        except Exception as ex:
            console.debug(
                f"Unable to fetch token from the hosting config file due to: {ex}"
            )
            return None
    if not token:
        console.error("Unable to fetch the token from existing config.")
    console.debug(f"Token: {token}")
    return token


def validate_token(token: str) -> bool:
    """Validate the token with the control plane.

    Args:
        token: The access token to validate.

    Returns:
        True if the token is valid, False otherwise.
    """
    config = get_config()
    response = httpx.post(
        POST_VALIDATE_ME_ENDPOINT,
        headers=authorization_header(token),
        timeout=config.http_request_timeout,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPError:
        if response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            console.debug(f"Reason: {response.reason_phrase}")
            console.error("Internal server error. Please contact support.")
        elif response and (detail := response.json().get("detail")):
            console.debug(f"Details: {detail}")
        else:
            console.error(
                f"Unable to validate the token due to: {response.reason_phrase}."
            )
            console.debug(f'Details: {response.json().get("detail")}')
        return False
    return True


def authenticated_token() -> Optional[str]:
    """Fetch the access token from the existing config if applicable and validate it.

    Returns:
        The access token if it is valid, None otherwise.
    """
    # Check if the user is authenticated
    token = get_existing_access_token()
    if not token:
        console.error("Please authenticate using `reflex login` first.")
        return None
    if not validate_token(token):
        console.error("Access denied, exiting.")
        return None
    return token


def is_set_up() -> bool:
    """Check if the hosting config is set up.

    Returns:
        True if the hosting config is set up, False otherwise.
    """
    if get_config().cp_web_url is None:
        console.info("This feature is coming soon!")
        return False
    return True


def authorization_header(token: str) -> dict[str, str]:
    """Construct an authorization header with the specified token as bearer token.

    Args:
        token: The access token to use.

    Returns:
        The authorization header in dict format.
    """
    return {"Authorization": f"Bearer {token}"}


def prepare_deploy(
    key: Optional[str], app_name: str
) -> Optional[DeploymentPrepareResponse]:
    """Send a POST request to Control Plane to prepare a new deployment.
    Control Plane checks if there is conflict with the key if provided.
    If the key is absent, it will return a suggested key based on the app_name in the response.

    Args:
        key: The deployment name.
        app_name: The app name.

    Returns:
        The response containing the backend URLs if successful, None otherwise.
    """
    # Check if the user is authenticated
    if not (token := authenticated_token()):
        return None
    url_response = httpx.post(
        POST_DEPLOYMENTS_PREPARE_ENDPOINT,
        headers=authorization_header(token),
        json=DeploymentsPreparePostParam(key=key, app_name=app_name).dict(
            exclude_none=True
        ),
        timeout=config.http_request_timeout,
    )
    try:
        url_response.raise_for_status()
        url_json = url_response.json()
        return DeploymentPrepareResponse(
            app_prefix=url_json["app_prefix"],
            api_url=url_json["api_url"],
            suggested_key_and_api_url=url_json["suggested_key_and_api_url"],
            existing_deployments_same_app_and_api_urls=url_json[
                "existing_deployments_same_app_and_api_urls"
            ],
        )
    except httpx.TimeoutException:
        console.error("Unable to prepare launch due to request timeout.")
        return None
    except httpx.HTTPError as ex:
        console.error(f"Unable to prepare launch due to {ex}.")
    except Exception as ex:
        console.error(f"Unable to prepare launch due to internal errors: {ex}.")
        return None
    return None


def deploy(
    frontend_file_name: str,
    backend_file_name: str,
    key: str,
    app_name: str,
    regions: list[str],
    app_prefix: str,
    vm_type: Optional[str] = None,
    cpus: Optional[int] = None,
    memory_mb: Optional[int] = None,
    auto_start: Optional[bool] = None,
    auto_stop: Optional[bool] = None,
    envs: Optional[dict[str, str]] = None,
) -> Optional[DeploymentPostResponse]:
    """Send a POST request to Control Plane to launch a new deployment.

    Args:
        frontend_file_name: The frontend file name.
        backend_file_name: The backend file name.
        key: The deployment name.
        app_name: The app name.
        regions: The list of regions to deploy to.
        app_prefix: The app prefix.
        vm_type: The VM type.
        cpus: The number of CPUs.
        memory_mb: The memory in MB.
        auto_start: Whether to auto start.
        auto_stop: Whether to auto stop.
        envs: The environment variables.

    Returns:
        The response containing the URL of the site to be deployed if successful, None otherwise.
    """
    # Check if the user is authenticated
    if not (token := authenticated_token()):
        return None

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
        reflex_version=constants.Reflex.VERSION,
    )
    console.debug(f"{params.dict(exclude_none=True)}")
    try:
        with open(frontend_file_name, "rb") as frontend_file, open(
            backend_file_name, "rb"
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
        response.raise_for_status()
        response_json = response.json()
        return DeploymentPostResponse(url=response_json["url"])
    except httpx.TimeoutException:
        console.error("Unable to deploy due to request timeout.")
        return None
    except Exception as ex:
        console.error(f"Unable to deploy due to internal errors: {ex}.")
        return None


def list_deployments(
    app_name: Optional[str] = None,
) -> Optional[list[DeploymentGetResponse]]:
    """Send a GET request to Control Plane to list deployments.

    Args:
        app_name: An optional app name as the filter when listing deployments.

    Returns:
        The list of deployments if successful, None otherwise.
    """
    if not (token := authenticated_token()):
        return None

    params = DeploymentsGetParam(app_name=app_name)
    response = httpx.get(
        GET_DEPLOYMENTS_ENDPOINT,
        headers=authorization_header(token),
        params=params.dict(exclude_none=True),
        timeout=config.http_request_timeout,
    )

    try:
        response.raise_for_status()
        return [
            DeploymentGetResponse(
                key=deployment["key"],
                regions=deployment["regions"],
                app_name=deployment["app_name"],
                vm_type=deployment["vm_type"],
                cpus=deployment["cpus"],
                memory_mb=deployment["memory_mb"],
                url=deployment["url"],
                envs=deployment["envs"],
            )
            for deployment in response.json()
        ]
    except httpx.TimeoutException:
        console.error("Unable to list hosted instances due to request timeout.")
        return None
    except Exception as ex:
        console.error(f"Unable to list hosted instances due to {ex}.")
        return None


def fetch_token(request_id: str) -> Optional[str]:
    """Fetch the access token for the request_id from Control Plane.

    Args:
        request_id: The request ID used when the user opens the browser for authentication.

    Raises:
        SystemExit: If the response format is ill-formed, indicating internal error.

    Returns:
        The access token if it exists, None otherwise.
    """
    resp = httpx.get(
        f"{FETCH_TOKEN_ENDPOINT}/{request_id}", timeout=config.http_request_timeout
    )
    try:
        resp.raise_for_status()
        return resp.json()["access_token"]
    except httpx.HTTPError:
        return None
    except KeyError:
        console.error("Unable to authenticate. Please contact support.")
        raise SystemExit(1) from None


def poll_backend(backend_url: str) -> bool:
    """Poll the backend to check if it is up.

    Args:
        backend_url: The URL of the backend to poll.

    Returns:
        True if the backend is up, False otherwise.
    """
    try:
        console.debug(f"Polling backend at {backend_url}")
        resp = httpx.get(f"{backend_url}/ping", timeout=config.http_request_timeout)
        resp.raise_for_status()
        return resp.json() == "pong"
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
        resp = httpx.get(f"{frontend_url}", timeout=config.http_request_timeout)
        resp.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def clean_up():
    """Helper function to perform cleanup before exiting."""
    frontend_zip = constants.ComponentName.FRONTEND.zip()
    backend_zip = constants.ComponentName.BACKEND.zip()
    if os.path.exists(frontend_zip):
        os.remove(frontend_zip)
    if os.path.exists(backend_zip):
        os.remove(backend_zip)


def delete_deployment(key: str) -> bool:
    """Send a DELETE request to Control Plane to delete a deployment.

    Args:
        key: The deployment name.

    Raises:
        ValueError: If the key is not provided.

    Returns:
        True if the deployment is deleted successfully, False otherwise.
    """
    if not (token := authenticated_token()):
        return False
    if not key:
        raise ValueError("key is required for delete operation.")
    response = httpx.delete(
        f"{DELETE_DEPLOYMENTS_ENDPOINT}/{key}",
        headers=authorization_header(token),
        timeout=config.http_request_timeout,
    )
    try:
        response.raise_for_status()
        return True
    except httpx.TimeoutException:
        console.error("Unable to delete deployment due to request timeout.")
        return False
    except Exception as ex:
        console.error(f"Unable to delete deployment due to {ex}.")
        return False
