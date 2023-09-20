"""Hosting related utilities."""
import json
import os
from http import HTTPStatus
from typing import Optional

import httpx
from pydantic import BaseModel, Field

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


class DeploymentPrepareResponse(BaseModel):
    """The params/settings returned from the prepare endpoint,
    used in the CLI for the subsequent launch request.
    """

    api_url: str
    app_prefix: str
    suggested_deployment_key: str


class DeploymentGetResponse(BaseModel):
    """The params/settings returned from the GET endpoint."""

    key: str
    regions: list[str]
    app_name: str
    vm_type: str
    cpus: int
    memory_mb: int
    url: str


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
    app_name: str
    regions_json: str
    app_prefix: str = Field(...)
    vm_type: Optional[str] = None
    cpus: Optional[int] = None
    memory_mb: Optional[int] = None
    auto_start: Optional[bool] = None
    auto_stop: Optional[bool] = None
    description: Optional[str] = None
    secrets_json: Optional[str] = None


class DeploymentsGetParam(BaseModel):
    """Params for hosted instance GET request."""

    app_name: Optional[str]


def get_existing_access_token() -> Optional[str]:
    """Fetch the access token from the existing config if applicable.

    Returns:
        The access token if it exists, None otherwise.
    """
    token = None
    if os.path.exists(constants.HOSTING_JSON):
        console.debug("Fetching token from existing config.")
        try:
            with open(constants.HOSTING_JSON, "r") as config_file:
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


def create_app(app_name: str):
    """Send a POST request to Control Plane to create a new App.

    Args:
        app_name: The name of the app to create
    """
    # Check if the user is authenticated
    if not (token := authenticated_token()):
        return
    project_params = AppsPostParam(name=app_name)
    response = httpx.post(
        POST_APPS_ENDPOINT,
        headers=authorization_header(token),
        json=project_params.dict(exclude_none=True),
        timeout=config.http_request_timeout,
    )
    try:
        response.raise_for_status()
    except httpx.TimeoutException:
        console.error("Unable to create project due to request timeout.")
    except httpx.HTTPError:
        if response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            console.debug(f"Reason: {response.reason_phrase}")
        elif response and (detail := response.json().get("detail")):
            console.debug(f"Details: {detail}")
            console.error("Internal server error. Please contact support.")
    else:
        console.print(f"New project created: {app_name}")


# TODO: maybe a stronger return type?
def list_apps() -> Optional[list[AppGetResponse]]:
    """Send a GET request to Control Plane to list all apps.

    Returns:
        The list of apps if successful, None otherwise.
    """
    # Check if the user is authenticated
    if not (token := authenticated_token()):
        return None

    response = httpx.get(
        GET_APPS_ENDPOINT,
        headers=authorization_header(token),
        timeout=config.http_request_timeout,
    )

    if response.status_code != 200:
        console.error(f"Unable to list projects due to {response.reason_phrase}.")
        if response and (detail := response.json().get("detail")):
            console.debug(f"Details: {detail}")
        else:
            console.debug(f"Details: {response}")
        return None
    try:
        response_json = response.json()
        return [
            AppGetResponse(
                name=app["name"],
            )
            for app in response_json
        ]
    except Exception as ex:
        console.debug(f"Unable to parse the response due to {ex}.")
        console.error("Unable to list projects due to internal errors.")
        return None


def prepare_launch(
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
            api_url=url_json["api_url"],
            app_prefix=url_json["app_prefix"],
            suggested_deployment_key=url_json["suggested_deployment_key"],
        )
    except httpx.TimeoutException:
        console.error("Unable to prepare launch due to request timeout.")
        return None
    except httpx.HTTPError as ex:
        if url_response and (detail := url_response.json().get("detail")):
            console.error(f"Unable to prepare launch due to {detail}.")
        else:
            console.error(f"Unable to prepare launch due to {ex}.")
    except KeyError as ex:
        console.error(f"Unable to prepare launch due to internal errors: {ex}.")
        return None
    except Exception as ex:
        console.error(f"Unable to prepare launch due to {ex}.")
        return None
    return None


def launch(
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
        vm_type=vm_type,
        cpus=cpus,
        memory_mb=memory_mb,
        auto_start=auto_start,
        auto_stop=auto_stop,
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
    except httpx.HTTPError as http_error:
        # Need a better way to print this
        console.error(
            f'Unable to deploy due to: {locals().get("response", {}).json().get("detail") or http_error}.'
        )
        return None
    except KeyError as key_error:
        console.error(f"Unable to deploy due to internal errors: {key_error}.")
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
            )
            for deployment in response.json()
        ]
    except httpx.TimeoutException:
        console.error("Unable to list hosted instances due to request timeout.")
        return None
    except httpx.HTTPError:
        if response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            console.error("Internal server error. Please contact support.")
        elif response and (detail := response.json().get("detail")):
            console.error(f"Unable to list hosted instances due to: {detail}.")
        else:
            console.error(
                f"Unable to list hosted instances due to: {response.reason_phrase}."
            )
        return None
    except KeyError as ex:
        console.error(f"Unable to list hosted instances due to internal errors: {ex}.")
        return None
    except Exception as ex:
        console.error(f"Unable to list hosted instances due to {ex}.")
        return None
