"""URL helpers shared across the Reflex site packages."""

from __future__ import annotations

from reflex_base.config import get_config

from reflex.utils.exec import is_prod_mode


def public_url(path: str = "", fallback_base: str | None = None) -> str:
    """Build a public URL from ``deploy_url`` + ``frontend_path`` in rxconfig.

    The same combination is used for canonical URLs, ``llms.txt`` asset
    references, and the docs home URL. Centralizing here keeps the rules
    consistent across call sites.

    Args:
        path: Path segment to append. Should start with ``/`` to form a
            clean URL, or be empty to return the base alone.
        fallback_base: Base URL (already including any frontend_path prefix,
            e.g. ``https://reflex.dev/docs``) to use outside of prod mode.
            When ``None``, the returned URL may be relative (no scheme/host).

    Returns:
        The combined URL. If neither a deploy URL, frontend path, nor a
        fallback base is configured, returns ``path`` unchanged.
    """
    if fallback_base is not None and not is_prod_mode():
        return fallback_base.rstrip("/") + path

    config = get_config()
    deploy_url = (config.deploy_url or "").removesuffix("/")
    frontend_path = (config.frontend_path or "").strip("/")
    if frontend_path:
        base = f"{deploy_url}/{frontend_path}" if deploy_url else f"/{frontend_path}"
    else:
        base = deploy_url
    return f"{base}{path}" if base else path
