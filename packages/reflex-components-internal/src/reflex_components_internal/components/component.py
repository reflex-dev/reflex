"""Core component for all components."""

from typing import Any

from reflex.components.component import Component
from reflex.vars.base import Var
from reflex_ui.utils.twmerge import cn


class CoreComponent(Component):
    """Core component for all components."""

    # Whether the component should be unstyled
    unstyled: Var[bool]

    @classmethod
    def set_class_name(
        cls, default_class_name: str | Var[str], props: dict[str, Any]
    ) -> None:
        """Set the class name in props, merging with the default if necessary.

        Args:
            props: The component props dictionary
            default_class_name: The default class name to use

        """
        if "render_" in props:
            return

        props_class_name = props.get("class_name", "")

        if props.pop("unstyled", False):
            props["class_name"] = props_class_name
            return

        props["class_name"] = cn(default_class_name, props_class_name)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "unstyled",
        ]
