"""Data grid components."""

from __future__ import annotations

from reflex.utils import lazy_loader

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "code": [
        "CodeBlock",
        "code_block",
        "LiteralCodeBlockTheme",
        "LiteralCodeLanguage",
    ],
    "dataeditor": ["data_editor", "data_editor_theme", "DataEditorTheme"],
    "logo": ["logo"],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submod_attrs=_SUBMOD_ATTRS,
)
