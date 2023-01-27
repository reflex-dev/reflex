"""Import all the components."""

from pynecone import utils
from pynecone.components.layout.propcond import PropCond

from .component import Component
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

# Add the convenience methods for all the components.
locals().update(
    {
        utils.to_snake_case(name): value.create
        for name, value in locals().items()
        if isinstance(value, type) and issubclass(value, Component)
    }
)


# Add responsive styles shortcuts.
def mobile_only(*children, **props):
    """Create a component that is only visible on mobile.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["block", "none", "none", "none"])


def tablet_only(*children, **props):
    """Create a component that is only visible on tablet.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["none", "block", "block", "none"])


def desktop_only(*children, **props):
    """Create a component that is only visible on desktop.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["none", "none", "none", "block"])


def tablet_and_desktop(*children, **props):
    """Create a component that is only visible on tablet and desktop.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["none", "block", "block", "block"])


def mobile_and_tablet(*children, **props):
    """Create a component that is only visible on mobile and tablet.

    Args:
        *children: The children to pass to the component.
        **props: The props to pass to the component.

    Returns:
        The component.
    """
    return Box.create(*children, **props, display=["block", "block", "block", "none"])


def cond(cond, comp1, comp2=None):
    """Create a conditional component.

    Args:
        cond: The cond to determine which component to render.
        comp1: The component or prop to render if the cond is true.
        comp2: The component or prop to render if the cond is false.

    Returns:
        The conditional component.
    """
    if isinstance(comp1, Component) and isinstance(comp2, Component):
        return Cond.create(cond, comp1, comp2)
    else:
        return PropCond.create(cond, comp1, comp2)
