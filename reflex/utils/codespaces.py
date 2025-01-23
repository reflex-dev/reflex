"""Utilities for working with Github Codespaces."""

from __future__ import annotations

import os

from fastapi.responses import HTMLResponse

from reflex.components.base.script import Script
from reflex.components.component import Component
from reflex.components.core.banner import has_connection_errors
from reflex.components.core.cond import cond
from reflex.constants import Endpoint

redirect_script = """
const thisUrl = new URL(window.location.href);
const params = new URLSearchParams(thisUrl.search)

function doRedirect(url) {
    if (!window.sessionStorage.getItem("authenticated_github_codespaces")) {
        const a = document.createElement("a");
        if (params.has("redirect_to")) {
            a.href = params.get("redirect_to")
        } else if (!window.location.href.startsWith(url)) {
            a.href = url + `?redirect_to=${window.location.href}`
        } else {
            return
        }
        a.hidden = true;
        a.click();
        a.remove();
        window.sessionStorage.setItem("authenticated_github_codespaces", "true")
    }
}
doRedirect("%s")
""" % Endpoint.AUTH_CODESPACE.get_url()


def codespaces_port_forwarding_domain() -> str | None:
    """Get the domain for port forwarding in Github Codespaces.

    Returns:
        The domain for port forwarding in Github Codespaces, or None if not running in Codespaces.
    """
    return os.getenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")


def is_running_in_codespaces() -> bool:
    """Check if the app is running in Github Codespaces.

    Returns:
        True if running in Github Codespaces, False otherwise.
    """
    return codespaces_port_forwarding_domain() is not None


def codespaces_auto_redirect() -> list[Component]:
    """Get the components for automatically redirecting back to the app after authenticating a codespace port forward.

    Returns:
        A list containing the conditional redirect component, or empty list.
    """
    if is_running_in_codespaces():
        return [cond(has_connection_errors, Script.create(redirect_script))]
    return []


async def auth_codespace() -> HTMLResponse:
    """Page automatically redirecting back to the app after authenticating a codespace port forward.

    Returns:
        An HTML response with an embedded script to redirect back to the app.
    """
    return HTMLResponse(
        """
    <html>
        <head>
            <title>Reflex Github Codespace Forward Successfully Authenticated</title>
        </head>
        <body>
            <center>
                <h2>Successfully Authenticated</h2>
            </center>
            <script language="javascript">
                %s
            </script>
        </body>
    </html>
    """
        % redirect_script
    )
