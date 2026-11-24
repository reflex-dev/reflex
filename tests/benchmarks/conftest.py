import pytest

from .fixtures import evaluated_page, unevaluated_page

__all__ = ["evaluated_page", "unevaluated_page"]


@pytest.fixture(autouse=True)
def _session_token_checks_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run benchmarks without session ownership checks.

    The benchmarks address state with a plain token and no browser session,
    which the default enforce mode rejects.

    Args:
        monkeypatch: Environment fixture.
    """
    monkeypatch.setenv("REFLEX_SESSION_TOKEN_MODE", "off")
