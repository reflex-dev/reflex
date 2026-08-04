"""Tests for reflex_base.constants.base."""

from __future__ import annotations

from typing import get_args

from reflex_base.constants.base import LITERAL_ENV, Env


def test_literal_env_matches_env_enum():
    """LITERAL_ENV must stay in sync with the Env enum values."""
    assert set(get_args(LITERAL_ENV)) == {env.value for env in Env}
