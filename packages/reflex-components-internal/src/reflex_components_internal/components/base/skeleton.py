"""Custom skeleton component."""

from reflex_components_core.el.elements.typography import Div

from reflex.components.component import Component
from reflex.components.memo import EMPTY_VAR_COMPONENT, memo
from reflex.vars.base import EMPTY_VAR_STR, Var
from reflex_components_internal.utils.twmerge import cn


class ClassNames:
    """Class names for skeleton component."""

    ROOT = "animate-pulse bg-secondary-6"


@memo
def skeleton_component(
    children: Var[Component] = EMPTY_VAR_COMPONENT,
    class_name: Var[str] = EMPTY_VAR_STR,
) -> Component:
    """Skeleton component.

    Returns:
        The component.
    """
    return Div.create(children, class_name=cn(ClassNames.ROOT, class_name))


skeleton = skeleton_component
