from collections.abc import Generator

import pytest

from .fixtures import evaluated_page, unevaluated_page

__all__ = ["evaluated_page", "unevaluated_page"]


@pytest.fixture(autouse=True)
def _session_token_checks_off() -> Generator[None, None, None]:
    """Run benchmarks without session ownership checks.

    The benchmarks address state with a plain token and no browser session,
    which the default enforce mode rejects.

    Yields:
        Control while the mode is set.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("REFLEX_SESSION_TOKEN_MODE", "off")
        yield
