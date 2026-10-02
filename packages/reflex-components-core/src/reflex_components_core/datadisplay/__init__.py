"""Data grid components."""

from __future__ import annotations

from reflex_base.utils import lazy_loader

# `code_block` and `data_editor` ship as the standalone reflex-components-code
# and reflex-components-dataeditor packages, which `reflex.components.datadisplay`
# maps onto.
_SUBMOD_ATTRS: dict[str, list[str]] = {
    "logo": ["logo"],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submod_attrs=_SUBMOD_ATTRS,
)
