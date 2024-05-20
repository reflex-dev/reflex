"""Radix primitive components (https://www.radix-ui.com/primitives)."""
import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submod_attrs={
        "accordion": [
            "accordion",
        ],
        "drawer": [
            "drawer",
        ],
        "form": [
            "form",
        ],
        "progress": [
            "progress",
        ],
        "slider": [
            "slider",
        ]
    },
)

