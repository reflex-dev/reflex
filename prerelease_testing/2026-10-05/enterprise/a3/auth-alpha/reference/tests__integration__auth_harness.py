"""Shared helpers for the ``AuthPlugin`` end-to-end tests.

``AuthPluginHarness`` generates an app whose ``rxconfig.py`` registers the
``AuthPlugin``; subclasses override ``rxconfig_template`` / ``extra_app_files``
to vary the plugin configuration. The login helpers drive the mock IdP's
authorize page (see the ``mock_idp`` fixture in ``conftest.py``).
"""

from __future__ import annotations

import re
from typing import ClassVar

from playwright.sync_api import Page
from reflex.testing import AppHarness

# Claims for the predefined IdP users (mirrors examples/auth_mock/users.yaml):
# Alice is in the ``admins`` group, Bob is not, so authz checks split on them.
ALICE_CLAIMS = {
    "name": "Alice Admin",
    "email": "alice@example.com",
    "groups": ["admins", "staff"],
}
BOB_CLAIMS = {
    "name": "Bob Member",
    "email": "bob@example.com",
    "groups": ["staff"],
}

DEFAULT_RXCONFIG = """
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="{app_name}",
    plugins=[rxe.AuthPlugin()],
)
"""


def base_url(harness: AppHarness) -> str:
    """The app's frontend URL without a trailing slash.

    ``AppHarness.frontend_url`` ends with ``/``; concatenating paths onto it
    raw produces ``//path``, which the router treats as a 404.

    Args:
        harness: The running app harness.

    Returns:
        The frontend URL, safe to concatenate ``/path`` onto.
    """
    assert harness.frontend_url is not None
    return harness.frontend_url.rstrip("/")


class AuthPluginHarness(AppHarness):
    """AppHarness whose generated rxconfig registers the ``AuthPlugin``.

    The plugin must live in ``rxconfig.py``: reflex reloads the config from
    that module, so plugins appended to a loaded config at app-module import
    are dropped. Subclasses override ``rxconfig_template`` (formatted with
    ``app_name``) and ``extra_app_files`` (filename -> raw content, written
    into the app package).
    """

    rxconfig_template: ClassVar[str] = DEFAULT_RXCONFIG
    extra_app_files: ClassVar[dict[str, str]] = {}

    def _initialize_app(self):
        # Each harness is an independent app; reset module-level enforcement
        # state so the new plugin can bind and sweep without hitting the
        # rebind guard left over from the previous harness in this process.
        from reflex_enterprise.auth import enforcement

        enforcement._active_plugin = None
        enforcement._PROTECTION.clear()

        # Write the config before the base class runs `reflex init` (which
        # keeps an existing rxconfig) and imports + compiles the app. With an
        # existing rxconfig, init skips the app template, so create the
        # package skeleton the base class writes the app source into.
        self.app_path.mkdir(parents=True, exist_ok=True)
        (self.app_path / "rxconfig.py").write_text(
            self.rxconfig_template.format(app_name=self.app_name)
        )
        self.app_module_path.parent.mkdir(parents=True, exist_ok=True)
        (self.app_module_path.parent / "__init__.py").touch()
        self.app_module_path.touch()
        for filename, content in self.extra_app_files.items():
            (self.app_module_path.parent / filename).write_text(content)
        super()._initialize_app()


def authorize_as(page: Page, sub: str) -> None:
    """Complete the mock IdP's authorize page as the given predefined user.

    Args:
        page: The Playwright page, mid-navigation to the IdP.
        sub: The predefined user's subject (e.g. ``"alice"``).
    """
    page.wait_for_url(re.compile(r"/oauth2/authorize"))
    # Select by name+value, not CSS class: the predefined-user button's class
    # differs across oidc-provider-mock versions (``authorize-button`` in
    # >=0.4, ``outline`` in 0.3.x, which the resolver picks on Python < 3.12),
    # but ``name="sub"`` and the subject value are stable. Predefined users are
    # excluded from the "recent users" list, so this stays unambiguous.
    page.locator(f'button[name="sub"][value="{sub}"]').click()


def login_via_palette(
    page: Page, sub: str, *, button_text: str = "Login with Generic"
) -> None:
    """From the app's login page, run the full OIDC login flow as ``sub``.

    Clicks the provider's login button, authorizes on the mock IdP, and
    returns once navigation leaves the IdP.

    Args:
        page: The Playwright page, currently on the app's login page.
        sub: The predefined IdP user to authorize as.
        button_text: The provider login button label to click.
    """
    page.get_by_role("button", name=button_text).click()
    authorize_as(page, sub)


def login_and_open(
    page: Page,
    frontend_url: str,
    sub: str,
    path: str,
    *,
    login_path: str = "/login",
    button_text: str = "Login with Generic",
) -> None:
    """Open a protected path, complete the full login flow, and land on it.

    The post-login ``redirect_to`` round-trip is pinned by its own dedicated
    test; this helper navigates to the target explicitly after the IdP hands
    control back, so other tests don't cascade-fail on that surface.

    Args:
        page: The Playwright page.
        frontend_url: The app's frontend URL (no trailing slash).
        sub: The predefined IdP user to authorize as.
        path: The protected path to end up on (e.g. ``"/dashboard"``).
        login_path: The configured login endpoint.
        button_text: The provider login button label to click.
    """
    frontend_url = frontend_url.rstrip("/")
    page.goto(frontend_url + path)
    page.wait_for_url(re.compile(re.escape(login_path)))
    login_via_palette(page, sub, button_text=button_text)
    # Back on the app with the auth callback completed (tokens delivered).
    page.wait_for_url(
        lambda url: url.startswith(frontend_url) and "callback" not in url
    )
    if path not in page.url:
        page.goto(frontend_url + path)
    page.wait_for_url(re.compile(re.escape(path)))
