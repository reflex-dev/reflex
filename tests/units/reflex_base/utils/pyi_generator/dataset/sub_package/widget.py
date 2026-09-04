"""A widget component for the sub_package.

This is a simple module providing a component for the __init__.py lazy loader test.
"""

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var


class SubWidget(Component):
    """A widget in the sub package."""

    name: Var[str] = field(doc="Widget name.")
