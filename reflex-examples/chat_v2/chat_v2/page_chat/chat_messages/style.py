from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Style:
    default: dict[str, str] = field(
        default_factory=lambda: {
            "gap": "12px",
            "display": "flex",
            "border_radius": "16px",
        },
    )
