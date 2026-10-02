"""Helpers for resolving integration asset URLs from the local integrations_docs package."""

from pathlib import Path
from typing import Literal

import integrations_docs
from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import EnvironmentVariables
from reflex_base.utils.decorator import once

RAW_DOC_IMAGES_PREFIX = (
    "https://raw.githubusercontent.com/reflex-dev/integrations-docs/"
    "refs/heads/main/images/docs/"
)


def _integrations_images_url(subdir: str) -> str:
    """Symlink integrations_docs/images/<subdir> into assets/external and return its public URL.

    Args:
        subdir: The image subdirectory to expose (e.g. ``"logos"`` or ``"docs"``).

    Returns:
        The public frontend URL prefix for the integrations_docs images subdirectory.

    Raises:
        RuntimeError: If the integrations_docs images directory cannot be found.
    """
    src = Path(integrations_docs.__file__).parent / "images" / subdir
    if not src.is_dir():
        msg = f"integrations_docs images directory not found at {src}"
        raise RuntimeError(msg)
    relative_path = f"/{constants.Dirs.EXTERNAL_APP_ASSETS}/integrations_docs/{subdir}/"
    if not EnvironmentVariables.REFLEX_BACKEND_ONLY.get():
        dst = (
            Path.cwd()
            / constants.Dirs.APP_ASSETS
            / constants.Dirs.EXTERNAL_APP_ASSETS
            / "integrations_docs"
            / subdir
        )
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_symlink() or dst.resolve() != src.resolve():
            if dst.is_symlink() or dst.exists():
                dst.unlink()
            dst.symlink_to(src)
    return get_config().prepend_frontend_path(relative_path)


@once
def _integrations_logos_url() -> str:
    """Return the public URL prefix for the integrations_docs logos directory.

    Returns:
        The public frontend URL prefix for the integrations_docs logos directory.
    """
    return _integrations_images_url("logos")


@once
def _integrations_doc_images_url() -> str:
    """Return the public URL prefix for the integrations_docs screenshots directory.

    Returns:
        The public frontend URL prefix for the integrations_docs docs images directory.
    """
    return _integrations_images_url("docs")


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


def rewrite_integration_doc_images_in_source(source: str) -> str:
    """Rewrite raw GitHub integrations-docs screenshot URLs in a markdown source to local URLs.

    Operates on the raw markdown text before parsing.

    Args:
        source: The markdown document source.

    Returns:
        The source with every raw GitHub doc screenshot URL replaced by its local asset URL.
    """
    if RAW_DOC_IMAGES_PREFIX not in source:
        return source
    return source.replace(RAW_DOC_IMAGES_PREFIX, _integrations_doc_images_url())
