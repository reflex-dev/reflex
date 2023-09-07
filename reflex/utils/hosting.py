"""Hosting related utilities."""
import json
import os
from http import HTTPStatus
from typing import Optional

import requests
from pydantic import BaseModel

from reflex import constants
from reflex.config import get_config
from reflex.utils import console


class PresignedUrlPostParam(BaseModel):
    """Params for presigned url GET request."""

    instance_name: str  # name of the hosted instance
    file_name: str  # name of the file to be uploaded


class ProjectPostParam(BaseModel):
    """Params for project creation POST request."""

    name: str
    description: Optional[str] = None


class ProjectGetParam(BaseModel):
    """Params for projects GET request."""

    name: str


class HostedInstancePostParam(BaseModel):
    """Params for hosted instance deployment POST request."""

    key: str  # name of the hosted instance
    backend_initial_region: str
    project_name: str
    backend_file_name: str
    frontend_file_name: str
    description: Optional[str] = None
    backend_cpus: Optional[int] = None
    backend_memory_mb: Optional[int] = None


class HostedInstanceGetParam(BaseModel):
    """Params for hosted instance GET request."""

    project_name: str


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
                f"Unable to fetch token from the hosting config file due to {ex}"
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
    response = requests.post(
        f"{config.cp_backend_url}/validate/me",
        headers=authorization_header(token),
        timeout=config.http_request_timeout,
    )
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        if response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            console.debug(f"Reason: {response.content}")
            console.error("Internal server error. Please contact support.")
        else:
            console.error(f"Unable to validate the token due to {response.reason}.")
        return False

    console.info("You are logged in.")
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
