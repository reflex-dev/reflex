"""Shared fixtures for the docs app tests."""

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _session_token_compatibility_mode() -> Generator[None, None, None]:
    """Run the tests in the session mode that allows tokens without a session.

    The example tests address state with a plain token and no browser session,
    which the default enforce mode rejects.

    Yields:
        Control while the mode is set.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("REFLEX_SESSION_TOKEN_MODE", "warn")
        yield
