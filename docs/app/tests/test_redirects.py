"""HTTP semantics for the docs' renamed routes."""

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from reflex_docs.redirects import DocsRedirectMiddleware


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize("suffix", ["", "/"])
def test_legacy_docs_redirect_before_rendering(method, suffix):
    """Old URLs redirect in one hop without JavaScript and retain query strings."""
    app = DocsRedirectMiddleware(
        Starlette(
            routes=[
                Route(
                    "/{path:path}",
                    lambda request: PlainTextResponse("next"),
                    methods=["GET", "HEAD", "POST"],
                )
            ]
        ),
        redirects=[("/old/", "/new/")],
        frontend_path="/docs",
    )
    with TestClient(app, follow_redirects=False) as client:
        response = client.request(method, f"/docs/old{suffix}?q=one%20two")
    assert response.status_code == 301
    assert response.headers["location"] == "/docs/new/?q=one%20two"


@pytest.mark.parametrize(
    "method,path", [("GET", "/old/"), ("GET", "/docs/new/"), ("POST", "/docs/old/")]
)
def test_non_redirect_requests_pass_through(method, path):
    """Only GET/HEAD requests to known legacy docs paths are redirected."""
    app = DocsRedirectMiddleware(
        Starlette(
            routes=[
                Route(
                    "/{path:path}",
                    lambda request: PlainTextResponse("next"),
                    methods=["GET", "HEAD", "POST"],
                )
            ]
        ),
        redirects=[("/old/", "/new/")],
        frontend_path="/docs",
    )
    with TestClient(app, follow_redirects=False) as client:
        response = client.request(method, path)
    assert response.status_code == 200
    assert response.text == "next"
