"""This module provides functionality to take screenshots of a Reflex app using Playwright."""

from importlib.util import find_spec

from reflex import constants


def take_screenshots(
    backend_url: str,
    frontend_url: str,
    delay: int,
    full_page: bool,
    width: int,
    height: int,
    headed: bool,
    stateful: bool,
) -> tuple[str | None, dict[str, bytes]]:
    """Take screenshots of the app in the current directory.

    Requires an app with active_connections and all_routes endpoints enabled.
    """
    if not find_spec("playwright"):
        msg = "Playwright is not installed. Please install it with `pip install playwright`."
        raise ImportError(msg)

    import urllib.parse

    import playwright.sync_api

    from reflex.route import replace_brackets_with_keywords
    from reflex.utils.net import get, post

    backend_url_parsed = urllib.parse.urlsplit(backend_url)
    all_routes_url = backend_url_parsed._replace(
        path=backend_url_parsed.path.removesuffix("/")
        + "/"
        + constants.Endpoint.ALL_ROUTES.value
    )

    endpoints: list[str] = []

    try:
        response = get(all_routes_url.geturl())
        response.raise_for_status()
        endpoints = response.json()
    except Exception as e:
        msg = (
            f"Failed to fetch all routes from {all_routes_url.geturl()}: {e}\n"
            "Make sure that the url is the backend url and that the app has the all_routes endpoint enabled."
        )
        raise ValueError(msg) from e

    token = ""

    if stateful:
        active_connections_url = backend_url_parsed._replace(
            path=backend_url_parsed.path.removesuffix("/")
            + "/"
            + constants.Endpoint.ACTIVE_CONNECTIONS.value
        )

        try:
            response = get(active_connections_url.geturl())
            response.raise_for_status()
            active_connections = response.json()
            if active_connections:
                token = list(active_connections.keys())[-1]
        except Exception:
            token = ""

        if token:
            clone_state_url = backend_url_parsed._replace(
                path=backend_url_parsed.path.removesuffix("/")
                + "/"
                + constants.Endpoint.CLONE_STATE.value
            )
            try:
                response = post(clone_state_url.geturl(), json=token)
                response.raise_for_status()
                token = response.json()
            except Exception:
                token = ""

    frontend_url_parsed = urllib.parse.urlsplit(frontend_url)

    images = {}

    with playwright.sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        page = browser.new_page()
        page.set_viewport_size({"width": width, "height": height})
        if token:
            page.add_init_script(f"window.sessionStorage.setItem('token', '{token}')")

        for endpoint in endpoints:
            normalized_endpoint = endpoint
            if not normalized_endpoint.startswith("/"):
                normalized_endpoint = "/" + normalized_endpoint
            if normalized_endpoint == "/index":
                normalized_endpoint = "/"

            if (
                replace_brackets_with_keywords(normalized_endpoint)
                != normalized_endpoint
            ):
                continue

            full_url = frontend_url_parsed._replace(
                path=frontend_url_parsed.path.removesuffix("/") + normalized_endpoint
            ).geturl()

            page.goto(full_url)
            page.wait_for_load_state("networkidle")
            if delay > 0:
                page.wait_for_timeout(delay)
            image = page.screenshot(
                full_page=full_page,
            )
            images[endpoint] = image

        browser.close()

    return (token, images)
