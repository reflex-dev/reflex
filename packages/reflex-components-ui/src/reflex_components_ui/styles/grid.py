"""The look of the grid container."""

from reflex_components_ui.style import ComponentStyles

GRID: ComponentStyles = {
    "base": {
        "box_sizing": "border-box",
        "display": "grid",
        "align_items": "stretch",
        "justify_content": "flex-start",
        "grid_template_columns": "minmax(0, 1fr)",
        "grid_template_rows": "none",
    },
}
