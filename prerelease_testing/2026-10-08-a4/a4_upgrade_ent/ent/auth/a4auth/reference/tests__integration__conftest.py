"""Shared fixtures for the ``AuthPlugin`` end-to-end tests.

``mock_idp`` runs a real local OIDC identity provider (``oidc-provider-mock``)
on a background thread and points the ``OIDC_*`` env vars at it, so the full
authorization-code + PKCE flow (token exchange, JWKS validation, userinfo) runs
end-to-end with no cloud IdP.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from auth_harness import ALICE_CLAIMS, BOB_CLAIMS
from oidc_provider_mock import User as IdpUser
from oidc_provider_mock import run_server_in_thread


@pytest.fixture(scope="session")
def mock_idp() -> Generator[str, None, None]:
    """Run the mock OIDC IdP and point the ``OIDC_*`` env vars at it.

    The backend under test runs in this process (AppHarness), so the env vars
    are visible to the provider's lazy ``_get_config_value`` lookups.
    ``AUTHLIB_INSECURE_TRANSPORT`` lets the IdP accept plain-http localhost.

    Yields:
        The issuer URI of the running mock IdP.
    """
    env = {
        "AUTHLIB_INSECURE_TRANSPORT": "1",
        "CI": "true",  # bypass reflex-enterprise login check
        "OIDC_CLIENT_ID": "reflex-integration-test",
        "OIDC_CLIENT_SECRET": "reflex-integration-test-secret",
    }
    saved = {key: os.environ.get(key) for key in [*env, "OIDC_ISSUER_URI"]}
    os.environ.update(env)
    users = [
        IdpUser(sub="alice", claims=ALICE_CLAIMS),
        IdpUser(sub="bob", claims=BOB_CLAIMS),
    ]
    with run_server_in_thread(user_claims=users) as server:
        issuer = f"http://localhost:{server.server_port}"
        os.environ["OIDC_ISSUER_URI"] = issuer
        yield issuer
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
