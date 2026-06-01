"""Helpers for resolving integration asset URLs from the local integrations_docs package."""

from functools import cache
from pathlib import Path
from typing import Literal

import integrations_docs
from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import EnvironmentVariables

RAW_DOC_IMAGES_PREFIX = (
    "https://raw.githubusercontent.com/reflex-dev/integrations-docs/"
    "refs/heads/main/images/docs/"
)


@cache
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


def _integrations_logos_url() -> str:
    """Return the public URL prefix for the integrations_docs logos directory.

    Returns:
        The public frontend URL prefix for the integrations_docs logos directory.
    """
    return _integrations_images_url("logos")


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


def get_integration_doc_image_url(filename: str) -> str:
    """Build the public URL for an integration doc screenshot served from the local package.

    Args:
        filename: The screenshot filename (e.g. ``"databricks_integration_1.webp"``).

    Returns:
        The public URL for the doc screenshot.
    """
    return f"{_integrations_images_url('docs')}{filename}"


def rewrite_integration_doc_image_src(src: str) -> str:
    """Rewrite a raw GitHub integrations-docs screenshot URL to its local asset URL.

    Args:
        src: The image source URL as written in the markdown.

    Returns:
        The local asset URL when ``src`` is a raw GitHub doc screenshot URL, otherwise
        ``src`` unchanged.
    """
    if src.startswith(RAW_DOC_IMAGES_PREFIX):
        return get_integration_doc_image_url(src[len(RAW_DOC_IMAGES_PREFIX) :])
    return src
