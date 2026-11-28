"""The look of a form and of its parts: what the Radix wrappers give them."""

from __future__ import annotations

from reflex_components_ui.style import ComponentStyles

FORM: ComponentStyles = {"base": {"width": "100%"}}

FORM_FIELD: ComponentStyles = {"base": {"display": "grid", "margin_bottom": "10px"}}

FORM_LABEL: ComponentStyles = {
    "base": {"font_size": "15px", "font_weight": "500", "line_height": "35px"}
}

FORM_MESSAGE: ComponentStyles = {
    "base": {"font_size": "13px", "opacity": "0.8", "color": "white"}
}
