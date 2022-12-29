"""Import all the components."""

from pynecone import utils
from pynecone.event import EventSpec
from pynecone.var import Var

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
