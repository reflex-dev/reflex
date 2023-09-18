"""A component that wraps a recharts lib."""

from typing import List

from reflex.components.component import Component


class Recharts(Component):
    """A component that wraps a victory lib."""

    library = "recharts"

    lib_dependencies: List[str] = ["recharts@^1.8.5"]
