"""Helpers for resolving integration logo asset URLs from the local integrations_docs package."""

from pathlib import Path
from typing import Literal

import integrations_docs
from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import EnvironmentVariables
from reflex_base.utils.decorator import once


@once
def _integrations_logos_url() -> str:
    """Symlink the integrations_docs logos into assets/external and return the public URL.

    Returns:
        The public frontend URL prefix for the integrations_docs logos directory.

    Raises:
        RuntimeError: If the integrations_docs logos directory cannot be found.
    """
    src = Path(integrations_docs.__file__).parent / "images" / "logos"
    if not src.is_dir():
        msg = f"integrations_docs logos directory not found at {src}"
        raise RuntimeError(msg)
    relative_path = f"/{constants.Dirs.EXTERNAL_APP_ASSETS}/integrations_docs/logos/"
    if not EnvironmentVariables.REFLEX_BACKEND_ONLY.get():
        dst = (
            Path.cwd()
            / constants.Dirs.APP_ASSETS
            / constants.Dirs.EXTERNAL_APP_ASSETS
            / "integrations_docs"
            / "logos"
        )
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_symlink() or dst.resolve() != src.resolve():
            if dst.is_symlink() or dst.exists():
                dst.unlink()
            dst.symlink_to(src)
    return get_config().prepend_frontend_path(relative_path)


def format_integration_name(integration_name: str) -> str:
    """Normalize an integration name into the slug used by its logo filename.

    Args:
        integration_name: The human-readable integration name.

    Returns:
        The lowercase, underscore-separated slug.
    """
    return integration_name.lower().replace(" ", "_")


def get_integration_logo_url(
    integration_name: str, theme: Literal["light", "dark"]
) -> str:
    """Build the public URL for an integration logo SVG.

    Args:
        integration_name: The human-readable integration name.
        theme: The color theme variant to load.

    Returns:
        The public URL for the SVG logo.
    """
    return f"{_integrations_logos_url()}{theme}/{format_integration_name(integration_name)}.svg"
