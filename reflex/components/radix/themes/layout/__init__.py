"""Layout components."""
import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submod_attrs={
        "box": [
            "box",
            "Box",
        ],
        "center": [
            "center",
            "Center",
        ],
        "container": [
            "container",
            "Container"
        ],
        "flex": [
            "flex",
            "Flex"
        ],
        "grid": [
            "grid",
            "Grid",
        ],
        "section": [
            "section",
            "Section",
        ],
        "spacer": [
            "spacer",
            "Spacer"
        ],
        "stack": [
            "stack",
            "Stack",
            "Hstack",
            "hstack",
            "Vstack",
            "vstack"
        ],
        "list": [
            "list",
            "list_item",
            "ordered_list",
            "unordered_list"
        ],
    },
)