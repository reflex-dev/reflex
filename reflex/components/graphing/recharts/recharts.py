from typing import Any, Dict, List, Optional, Union

from reflex.components.component import Component
from reflex.style import Style
from reflex.vars import Var


class Recharts(Component):
    """A component that wraps a victory lib."""

    library = "recharts"

    lib_dependencies: List[str] = ["recharts@^1.8.5"]
