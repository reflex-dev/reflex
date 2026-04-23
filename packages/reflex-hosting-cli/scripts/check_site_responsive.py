"""Script to check if the backend and frontend of a deployed reflex app are responsive."""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def _ping_site_with_retries(url: str, retries: int) -> tuple[bool, str]:
    import httpx

    print(f"Checking {url} for responsiveness in {retries} retries.")
    for i in range(retries):
        try:
            response = httpx.get(url)
            response.raise_for_status()
        except httpx.HTTPError:  # noqa: PERF203
            time.sleep(1)
            continue
        else:
            return True, f"{url} is responsive after {i} retries"
    return False, f"{url} not responsive after {retries} retries."


ENV_TO_RUN_DOMAIN = {
    "dev": "dev.reflexcorp.run",
    "staging": "staging.reflexcorp.run",
    "prod": "reflex.run",
}


def get_frontend_url(key: str, env: str = "dev") -> str:
    """Return the frontend url for a deployment.

    Args:
        key: the deployment key
        env: dev/staging/prod.

    Returns:
        The frontend URL by the given deployment key

    """
    return f"https://{key}.{ENV_TO_RUN_DOMAIN[env]}"


ENV_TO_APP_PREFIX = {
    "dev": "rxh-dev-",
    "staging": "rxh-staging-",
    "prod": "rxh-prod-",
}


def get_backend_url(key: str, env: str = "dev"):
    """Return the expected API URL for a deployment based on its key.

    Args:
        key: the deployment key
        env: dev/staging/prod

    Returns:
        The backend URL by the given deployment key

    """
    return f"https://{ENV_TO_APP_PREFIX[env]}{key}.fly.dev"


def main():
    """Wait for ports to start listening."""
    parser = argparse.ArgumentParser(
        description="Check the backend and frontend are responsive."
    )
    parser.add_argument("--deployment-key", type=str, required=True)
    parser.add_argument("--frontend-retries", type=int, default=30)
    parser.add_argument("--backend-retries", type=int, default=90)
    parser.add_argument("--env", type=str, required=True)
    args = parser.parse_args()

    executor = ThreadPoolExecutor(max_workers=2)
    futures = []
    print(f"Checking frontend and backend for: {args.deployment_key}")
    frontend_url = get_frontend_url(key=args.deployment_key, env=args.env)
    backend_url = get_backend_url(key=args.deployment_key, env=args.env)

    futures.append(
        executor.submit(_ping_site_with_retries, frontend_url, args.frontend_retries)
    )
    futures.append(
        executor.submit(
            _ping_site_with_retries,
            f"{backend_url}/ping",  # Note here, we need the ping endpoint instead of `/`
            args.backend_retries,
        )
    )

    all_successful = True
    for f in as_completed(futures):
        ok, msg = f.result()
        if ok:
            print(f"OK: {msg}")
        else:
            print(f"FAIL: {msg}")
            all_successful = False

    if not all_successful:
        exit(1)


if __name__ == "__main__":
    main()
