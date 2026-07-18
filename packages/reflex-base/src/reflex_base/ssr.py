"""Server-side rendering (SSR) config gate for the base package.

The request-time backend (the ``/_ssr_data`` endpoint) lives in ``reflex.ssr``
because it depends on the state/app machinery that is not part of
``reflex_base``.  Only the config gate lives here so ``reflex_base`` code can
check whether SSR is enabled without importing the top-level ``reflex`` package.

SSR is a no-op unless ``config.ssr_mode`` is not ``OFF``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reflex_base import constants
from reflex_base.config import get_config

if TYPE_CHECKING:
    from reflex_base.config import Config


def is_enabled(config: Config | None = None) -> bool:
    """Whether SSR is enabled.

    Args:
        config: The config to read from, or the global config when omitted.

    Returns:
        True when ``config.ssr_mode`` is not ``OFF``.
    """
    config = config if config is not None else get_config()
    return config.ssr_mode != constants.SsrMode.OFF
