"""Layout components."""

# from .box import Box
# from .center import Center
# from .container import Container
# from .flex import Flex
# from .grid import Grid
# from .list import list_ns as list
# from .section import Section
# from .spacer import Spacer
# from .stack import HStack, Stack, VStack
#
# box = Box.create
# center = Center.create
# container = Container.create
# flex = Flex.create
# grid = Grid.create
# section = Section.create
# spacer = Spacer.create
# stack = Stack.create
# hstack = HStack.create
# vstack = VStack.create
# list_item = list.item
# ordered_list = list.ordered
# unordered_list = list.unordered

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"themes", "primitives"},
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