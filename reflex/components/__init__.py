"""Import all the components."""
from __future__ import annotations

import reflex.utils.format

from .base import Script
from .component import Component
from .component import NoSSRComponent as NoSSRComponent
from .datadisplay import *
from .disclosure import *
from .feedback import *
from .forms import *
from .graphing import *
from .layout import *
from .media import *
from .navigation import *
from .overlay import *
from .typography import *

# Dynamic Convenience methods for all the components.
locals().update(
    {
        reflex.utils.format.to_snake_case(name): value.create
        for name, value in locals().items()
        if isinstance(value, type) and issubclass(value, Component)
    }
)
