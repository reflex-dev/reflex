"""Markdown rendering with Rust acceleration.

Exposes ``markdown_to_html(text) -> str``. The implementation is selected by
``REFLEX_MARKDOWN``:

* ``auto`` (default): use ``reflex_markdown_rust`` if importable; fall back
  to ``mistletoe``.
* ``rust``: require the Rust wheel; raise on import failure.
* ``python``: skip the Rust wheel even if installed.

The Rust path is roughly 100× faster than the legacy ``mistletoe`` path
on Reflex-docs-sized pages — see plan §13.
"""

from __future__ import annotations

import os
from typing import Final, Literal

_BACKEND_ENV: Final[str] = "REFLEX_MARKDOWN"

Backend = Literal["auto", "rust", "python"]


def selected_backend() -> Backend:
    """Read the ``REFLEX_MARKDOWN`` env var. Defaults to ``auto``."""
    raw = os.environ.get(_BACKEND_ENV, "auto").strip().lower()
    if raw in ("auto", "rust", "python"):
        return raw  # type: ignore[return-value]
    return "auto"


def _try_rust():
    try:
        from reflex_markdown_rust import markdown_to_html as _rust

        return _rust
    except ImportError:
        return None


def _try_python():
    try:
        import mistletoe

        return mistletoe.markdown
    except ImportError:
        return None


def _resolve(backend: Backend):
    if backend == "rust":
        impl = _try_rust()
        if impl is None:
            raise RuntimeError(
                "REFLEX_MARKDOWN=rust but the reflex_markdown_rust wheel "
                "could not be imported."
            )
        return impl
    if backend == "python":
        impl = _try_python()
        if impl is None:
            raise RuntimeError(
                "REFLEX_MARKDOWN=python but mistletoe is not installed."
            )
        return impl
    # auto
    return _try_rust() or _try_python()


_impl = None


def markdown_to_html(text: str) -> str:
    """Render markdown source to HTML using the selected backend.

    Args:
        text: the markdown source.

    Returns:
        The rendered HTML.

    Raises:
        RuntimeError: if no markdown backend is available (neither Rust nor
            mistletoe).
    """
    global _impl
    if _impl is None:
        _impl = _resolve(selected_backend())
        if _impl is None:
            msg = (
                "No markdown backend available. Install reflex-markdown-rust "
                "or mistletoe."
            )
            raise RuntimeError(msg)
    return _impl(text)


def is_rust() -> bool:
    """Return True if the current backend is the Rust wheel."""
    if _impl is None:
        try:
            markdown_to_html("")
        except RuntimeError:
            return False
    rust = _try_rust()
    return rust is not None and _impl is rust
