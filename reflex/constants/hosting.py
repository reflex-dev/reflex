"""Constants related to hosting."""
import os

from reflex.constants.base import Reflex


class Hosting:
    """Constants related to hosting."""

    # The hosting config json file
    HOSTING_JSON = os.path.join(Reflex.DIR, "hosting_v0.json")
    # The hosting service backend URL
    CP_BACKEND_URL = "https://rxcp-dev-control-plane.fly.dev"
    # The hosting service webpage URL
    CP_WEB_URL = "https://control-plane.dev.reflexcorp.run"
    # Endpoint to create or update a deployment
    POST_DEPLOYMENTS_ENDPOINT = f"{CP_BACKEND_URL}/deployments"
    # Endpoint to get all deployments for the user
    GET_DEPLOYMENTS_ENDPOINT = f"{CP_BACKEND_URL}/deployments"
    # Endpoint to fetch information from backend in preparation of a deployment
    POST_DEPLOYMENTS_PREPARE_ENDPOINT = f"{CP_BACKEND_URL}/deployments/prepare"
    # Endpoint to authenticate current user
    POST_VALIDATE_ME_ENDPOINT = f"{CP_BACKEND_URL}/authenticate/me"
    # Endpoint to fetch a login token after user completes authentication on web
    FETCH_TOKEN_ENDPOINT = f"{CP_BACKEND_URL}/authenticate"
    # Endpoint to delete a deployment
    DELETE_DEPLOYMENTS_ENDPOINT = f"{CP_BACKEND_URL}/deployments"
    # Endpoint to get deployment status
    GET_DEPLOYMENT_STATUS_ENDPOINT = f"{CP_BACKEND_URL}/deployments"
    # Websocket endpoint to stream logs of a deployment
    DEPLOYMENT_LOGS_ENDPOINT = f'{CP_BACKEND_URL.replace("http", "ws")}/deployments'
    # The number of times to try and wait for the user to complete web authentication.
    WEB_AUTH_RETRIES = 60
    # The time to sleep between requests to check if for authentication completion. In seconds.
    WEB_AUTH_SLEEP_DURATION = 5
    # The expected number of milestones
    MILESTONES_COUNT = 6
    # Expected server response time to new deployment request. In seconds.
    DEPLOYMENT_PICKUP_DELAY = 30
    # The time to wait for the backend to come up after user initiates deployment. In seconds.
    BACKEND_POLL_RETRIES = 30
    # The time to wait for the frontend to come up after user initiates deployment. In seconds.
    FRONTEND_POLL_RETRIES = 30
    # End of deployment workflow message. Used to determine if it is the last message from server.
    END_OF_DEPLOYMENT_MESSAGES = ["deploy success", "deploy failed"]
    # How many iterations to try and print the deployment event messages from server during deployment.
    DEPLOYMENT_EVENT_MESSAGES_RETRIES = 30
    # Timeout limit for http requests
    HTTP_REQUEST_TIMEOUT = 5  # seconds
