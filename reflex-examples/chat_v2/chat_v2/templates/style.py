from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Style:
    parent: dict[str, str] = field(
        default_factory=lambda: {
            "gap": "40px",
            "z_index": "10",
            "width": "100%",
            "height": "100%",
        },
    )
    body: dict[str, str] = field(
        default_factory=lambda: {
            "width": "100%",
            "max_width": "50em",
            "height": "100%",
            "display": "flex",
            "overflow": "hidden",
            "padding_bottom": "30px",
            "margin_inline": "auto",
        },
    )
