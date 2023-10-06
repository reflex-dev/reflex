"""Hosting related utilities."""
import json
import os
from http import HTTPStatus
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError, root_validator

from reflex import constants
from reflex.config import get_config
from reflex.utils import console

config = get_config()

POST_DEPLOYMENTS_ENDPOINT = f"{config.cp_backend_url}/deployments"
POST_APPS_ENDPOINT = f"{config.cp_backend_url}/apps"
GET_APPS_ENDPOINT = f"{config.cp_backend_url}/apps"
GET_DEPLOYMENTS_ENDPOINT = f"{config.cp_backend_url}/deployments"
POST_DEPLOYMENTS_PREPARE_ENDPOINT = f"{config.cp_backend_url}/deployments/prepare"
POST_VALIDATE_ME_ENDPOINT = f"{config.cp_backend_url}/authenticate/me"
FETCH_TOKEN_ENDPOINT = f"{config.cp_backend_url}/authenticate"
DELETE_DEPLOYMENTS_ENDPOINT = f"{config.cp_backend_url}/deployments"
GET_DEPLOYMENT_STATUS_ENDPOINT = f"{config.cp_backend_url}/deployments"


def get_existing_access_token() -> tuple[str, str]:
    """Fetch the access token from the existing config if applicable.

    Raises:
        Exception: if runs into any issues, file not exist, ill-formatted, etc.

    Returns:
        The access token and optionally the invitation code if it is valid, otherwise empty string for the.
    """
    console.debug("Fetching token from existing config...")
    try:
        with open(constants.Hosting.HOSTING_JSON, "r") as config_file:
            hosting_config = json.load(config_file)
        access_token = hosting_config["access_token"]
        assert access_token
        return access_token, hosting_config.get("code")
    except Exception as ex:
        console.debug(
            f"Unable to fetch token from the hosting config file due to: {ex}"
        )
        raise Exception("no existing login found") from ex


def validate_token(token: str):
    """Validate the token with the control plane.

    Args:
        token: The access token to validate.

    Raises:
        ValueError: if access denied.
        Exception: if runs into timeout, failed requests, unexpected errors. These should be tried again.
    """
    config = get_config()
    try:
        response = httpx.post(
            POST_VALIDATE_ME_ENDPOINT,
            headers=authorization_header(token),
            timeout=config.http_request_timeout,
        )
        if response.status_code == HTTPStatus.FORBIDDEN:
            raise ValueError
        response.raise_for_status()
    except httpx.TimeoutException as te:
        console.debug("Unable to validate the token due to request timeout.")
        raise Exception("request timeout") from te
    except httpx.HTTPError as ex:
        console.debug(f"Unable to validate the token due to: {ex}.")
        raise Exception("server error") from ex
    except ValueError as ve:
        console.debug(f"Access denied {token}.")
        raise ValueError("access denied") from ve
    except Exception as ex:
        console.debug(f"Unexpected error: {ex}.")
        raise Exception("internal errors") from ex


def authenticated_token() -> Optional[str]:
    """Fetch the access token from the existing config if applicable and validate it.

    Returns:
        The access token if it is valid, None otherwise.
    """
    # Check if the user is authenticated
    try:
        token, _ = get_existing_access_token()
        if not token:
            console.debug("No token found from the existing config.")
            return None
        validate_token(token)
        return token
    except Exception as ex:
        console.debug(f"Unable to validate the token from the existing config: {ex}")
        console.debug("Try to delete the invalid token from config file")
        try:
            with open(constants.Hosting.HOSTING_JSON, "rw") as config_file:
                hosting_config = json.load(config_file)
                del hosting_config["access_token"]
                json.dump(hosting_config, config_file)
        except Exception as ex:
            console.debug(f"Unable to delete the invalid token from config file: {ex}")
        return None


def is_set_up() -> bool:
    """Check if the hosting config is set up.

    Returns:
        True if the hosting config is set up, False otherwise.
    """
    if get_config().cp_web_url is None:
        console.info("This feature is coming soon!")
        return False
    return True


def authorization_header(token: str) -> Dict[str, str]:
    """Construct an authorization header with the specified token as bearer token.

    Args:
        token: The access token to use.

    Returns:
        The authorization header in dict format.
    """
    return {"Authorization": f"Bearer {token}"}


class DeploymentPrepInfo(BaseModel):
    """The params/settings returned from the prepare endpoint
    including the deployment key and the frontend/backend URLs based on the key.
    """

    key: str
    api_url: str
    deploy_url: str


class DeploymentPrepareResponse(BaseModel):
    """The params/settings returned from the prepare endpoint,
    used in the CLI for the subsequent launch request.
    """

    app_prefix: str
    reply: Optional[DeploymentPrepInfo] = None
    existing: Optional[List[DeploymentPrepInfo]] = None
    suggestion: Optional[DeploymentPrepInfo] = None

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
            and not values.get("existing")
            and values.get("suggestion") is None
        ):
            raise ValueError(
                "At least one set of params for deploy is required from control plane."
            )
        return values


class DeploymentGetResponse(BaseModel):
    """The params/settings returned from the GET endpoint."""

    key: str
    regions: List[str]
    app_name: str
    vm_type: str
    cpus: int
    memory_mb: int
    url: str
    envs: List[str]


class DeploymentPostResponse(BaseModel):
    """The URL for the deployed site."""

    frontend_url: str = Field(..., regex=r"^https?://", min_length=8)
    backend_url: str = Field(..., regex=r"^https?://", min_length=8)


class DeploymentsPreparePostParam(BaseModel):
    """Params for app API URL creation backend API."""

    app_name: str
    key: Optional[str] = None  #  name of the deployment
    frontend_hostname: Optional[str] = None


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
    frontend_hostname: Optional[str] = None
    description: Optional[str] = None
    envs_json: Optional[str] = None


class DeploymentsGetParam(BaseModel):
    """Params for hosted instance GET request."""

    app_name: Optional[str]


class DeploymentDeleteParam(BaseModel):
    """Params for hosted instance DELETE request."""

    key: str


def prepare_deploy(
    app_name: str,
    key: Optional[str] = None,
    frontend_hostname: Optional[str] = None,
) -> DeploymentPrepareResponse:
    """Send a POST request to Control Plane to prepare a new deployment.
    Control Plane checks if there is conflict with the key if provided.
    If the key is absent, it will return existing deployments and a suggested name based on the app_name in the response.

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
    if not (token := authenticated_token()):
        raise Exception("not authenticated")
    try:
        response = httpx.post(
            POST_DEPLOYMENTS_PREPARE_ENDPOINT,
            headers=authorization_header(token),
            json=DeploymentsPreparePostParam(
                app_name=app_name, key=key, frontend_hostname=frontend_hostname
            ).dict(exclude_none=True),
            timeout=config.http_request_timeout,
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
        )
    except httpx.TimeoutException as te:
        console.debug("Unable to prepare launch due to request timeout.")
        raise Exception("request timeout") from te
    except httpx.HTTPError as he:
        console.debug(f"Unable to prepare deploy due to {he}.")
        raise Exception(f"{he}") from he
    except json.JSONDecodeError as jde:
        console.debug(f"Server did not respond with valid json: {jde}")
        raise Exception("internal errors") from jde
    except (KeyError, ValidationError) as kve:
        console.debug(f"The server response format is unexpected {kve}")
        raise Exception("internal errors") from kve
    except ValueError as ve:
        # This is a recognized client error
        raise Exception(f"{ve}") from ve
    except Exception as ex:
        console.debug(f"Unexpected error: {ex}.")
        raise Exception("internal errors") from ex


def deploy(
    frontend_file_name: str,
    backend_file_name: str,
    key: str,
    app_name: str,
    regions: List[str],
    app_prefix: str,
    vm_type: Optional[str] = None,
    cpus: Optional[int] = None,
    memory_mb: Optional[int] = None,
    auto_start: Optional[bool] = None,
    auto_stop: Optional[bool] = None,
    frontend_hostname: Optional[str] = None,
    envs: Optional[Dict[str, str]] = None,
) -> DeploymentPostResponse:
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
        frontend_hostname: The frontend hostname to deploy to. This is used to deploy at hostname not in the regular domain.
        envs: The environment variables.

    Raises:
        Exception: If the operation fails. The exception message is the reason.

    Returns:
        The response containing the URL of the site to be deployed if successful, None otherwise.
    """
    # Check if the user is authenticated
    if not (token := authenticated_token()):
        raise Exception("not authenticated")

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
        reflex_version=constants.Reflex.VERSION,
    )
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
        return DeploymentPostResponse(
            frontend_url=response_json["frontend_url"],
            backend_url=response_json["backend_url"],
        )
    except httpx.TimeoutException as te:
        console.debug("Unable to deploy due to request timeout.")
        raise Exception("request timeout") from te
    except httpx.HTTPError as he:
        console.debug(f"Unable to deploy due to {he}.")
        raise Exception("internal errors") from he
    except json.JSONDecodeError as jde:
        console.debug(f"Server did not respond with valid json: {jde}")
        raise Exception("internal errors") from jde
    except (KeyError, ValidationError) as kve:
        console.debug(f"Server response format unexpected: {kve}")
        raise Exception("internal errors") from kve
    except Exception as ex:
        console.debug(f"Unable to deploy due to internal errors: {ex}.")
        raise Exception("internal errors") from ex


def list_deployments(
    app_name: Optional[str] = None,
) -> List[Dict]:
    """Send a GET request to Control Plane to list deployments.

    Args:
        app_name: An optional app name as the filter when listing deployments.

    Raises:
        Exception: If the operation fails. The exception message is the reason.

    Returns:
        The list of deployments if successful, None otherwise.
    """
    if not (token := authenticated_token()):
        raise Exception("not authenticated")

    params = DeploymentsGetParam(app_name=app_name)

    try:
        response = httpx.get(
            GET_DEPLOYMENTS_ENDPOINT,
            headers=authorization_header(token),
            params=params.dict(exclude_none=True),
            timeout=config.http_request_timeout,
        )
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
            ).dict()
            for deployment in response.json()
        ]
    except httpx.TimeoutException as te:
        console.debug("Unable to list deployments due to request timeout.")
        raise Exception("request timeout") from te
    except httpx.HTTPError as he:
        console.debug(f"Unable to list deployments due to {he}.")
        raise Exception("internal errors") from he
    except (ValidationError, KeyError, json.JSONDecodeError) as vkje:
        console.debug(f"Server response format unexpected: {vkje}")
        raise Exception("internal errors") from vkje
    except Exception as ex:
        console.error(f"Unexpected error: {ex}.")
        raise Exception("internal errors") from ex


def fetch_token(request_id: str) -> tuple[str, str]:
    """Fetch the access token for the request_id from Control Plane.

    Args:
        request_id: The request ID used when the user opens the browser for authentication.

    Raises:
        Exception: for request timeout, failed requests, ill-formed responses, unexpected errors.

    Returns:
        The access token if it exists, None otherwise.
    """
    try:
        resp = httpx.get(
            f"{FETCH_TOKEN_ENDPOINT}/{request_id}", timeout=config.http_request_timeout
        )
        resp.raise_for_status()
        return resp.json()["access_token"], resp.json().get("code", "")
    except httpx.TimeoutException as te:
        console.debug("Unable to fetch token due to request timeout.")
        raise Exception("request timeout") from te
    except httpx.HTTPError as he:
        console.debug(f"Unable to fetch token due to {he}.")
        raise Exception("not found") from he
    except json.JSONDecodeError as jde:
        console.debug(f"Server did not respond with valid json: {jde}")
        raise Exception("internal errors") from jde
    except KeyError as ke:
        console.debug(f"Server response format unexpected: {ke}")
        raise Exception("internal errors") from ke
    except Exception as ex:
        console.debug("Unexpected errors: {ex}")
        raise Exception("internal errors") from ex


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


def delete_deployment(key: str):
    """Send a DELETE request to Control Plane to delete a deployment.

    Args:
        key: The deployment name.

    Raises:
        ValueError: If the key is not provided.
        Exception: If the operation fails. The exception message is the reason.
    """
    if not (token := authenticated_token()):
        raise Exception("not authenticated")
    if not key:
        raise ValueError("Valid key is required for the delete.")

    try:
        response = httpx.delete(
            f"{DELETE_DEPLOYMENTS_ENDPOINT}/{key}",
            headers=authorization_header(token),
            timeout=config.http_request_timeout,
        )
        response.raise_for_status()

    except httpx.TimeoutException as te:
        console.debug("Unable to delete deployment due to request timeout.")
        raise Exception("request timeout") from te
    except httpx.HTTPError as he:
        console.debug(f"Unable to delete deployment due to {he}.")
        raise Exception("internal errors") from he
    except Exception as ex:
        console.debug(f"Unexpected errors {ex}.")
        raise Exception("internal errors") from ex


class SiteStatus(BaseModel):
    """Deployment status info."""

    frontend_url: Optional[str] = None
    backend_url: Optional[str] = None
    reachable: bool
    updated_at: Optional[str] = None  # iso-formatted datetime string if reachable

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


class DeploymentStatusResponse(BaseModel):
    """Response for deployment status request."""

    frontend: SiteStatus
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
    if not (token := authenticated_token()):
        raise Exception("not authenticated")
    if not key:
        raise ValueError("Valid key is required for the delete.")

    try:
        response = httpx.get(
            f"{GET_DEPLOYMENT_STATUS_ENDPOINT}/{key}/status",
            headers=authorization_header(token),
            timeout=config.http_request_timeout,
        )
        response.raise_for_status()
        return DeploymentStatusResponse(
            frontend=SiteStatus(
                frontend_url=response.json()["frontend"]["url"],
                reachable=response.json()["frontend"]["reachable"],
                updated_at=response.json()["frontend"]["updated_at"],
            ),
            backend=SiteStatus(
                backend_url=response.json()["backend"]["url"],
                reachable=response.json()["backend"]["reachable"],
                updated_at=response.json()["backend"]["updated_at"],
            ),
        )
    except Exception as ex:
        console.debug(f"Unable to get deployment status due to {ex}.")
        raise Exception("internal errors") from ex
