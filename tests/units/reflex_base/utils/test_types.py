"""Tests for reflex_base.utils.types."""

from reflex_base import constants
from reflex_base.environment import environment
from reflex_base.utils.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
    _validation_depth,
)
from typing_extensions import TypeAliasType


def test_asgi_aliases_keep_their_names():
    """The ASGI type aliases are TypeAliasTypes so docs render them by name, not expanded."""
    for alias in (Scope, Message, Receive, Send, ASGIApp):
        assert isinstance(alias, TypeAliasType)

    assert Scope.__name__ == "Scope"
    assert Message.__name__ == "Message"
    assert Receive.__name__ == "Receive"
    assert Send.__name__ == "Send"
    assert ASGIApp.__name__ == "ASGIApp"


def test_validation_depth_by_env_mode():
    """Hot-path validation walks containers in dev but stays shallow in prod.

    In-process environment mode changes must take effect immediately, without
    any cache invalidation by the caller.
    """
    initial = environment.REFLEX_ENV_MODE.getenv()
    try:
        environment.REFLEX_ENV_MODE.set(constants.Env.PROD)
        assert _validation_depth() == 0
        environment.REFLEX_ENV_MODE.set(constants.Env.DEV)
        assert _validation_depth() == 1
    finally:
        environment.REFLEX_ENV_MODE.set(initial)
