"""Base class for the Reflex UI component library.

UI components are plain HTML elements styled with Tailwind CSS classes and
themed through CSS custom properties, so their appearance can be customized
with regular CSS, Tailwind classes, or a :class:`~reflex_components_core.ui.theme.Theme`.
"""

from __future__ import annotations

from typing import Any, ClassVar

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var

from reflex_components_core.ui.styling import cn

# Whether any UI component was created in this process. Read by the
# UIComponentsPlugin so the theme stylesheet also ships for UI components
# that never pass through the page compiler hooks (e.g. inside rx.memo).
_ui_component_created = False


def ui_component_created() -> bool:
    """Report whether any UI component has been created in this process.

    Returns:
        True if a UI component was created.
    """
    return _ui_component_created


class UIComponent(Component):
    """Base class for Reflex UI components."""

    # The data-slot attribute value identifying this component in the DOM.
    _slot: ClassVar[str | None] = None

    unstyled: Var[bool] = field(
        doc="Drop the component's built-in Tailwind classes, keeping only user-provided styling."
    )

    @classmethod
    def _apply_class_name(
        cls, default_class_name: str | Var | list, props: dict[str, Any]
    ) -> None:
        """Merge the component's default classes with user-provided ones.

        User classes win conflicts via ``tailwind-merge``. Passing
        ``unstyled=True`` drops the default classes entirely.

        Args:
            default_class_name: The component's built-in class string.
            props: The props passed to ``create``, updated in place.

        Raises:
            TypeError: If ``unstyled`` is not a static bool.
        """
        global _ui_component_created
        _ui_component_created = True
        if cls._slot is not None:
            props.setdefault("data_slot", cls._slot)
        unstyled = props.pop("unstyled", False)
        if isinstance(unstyled, Var):
            msg = "The unstyled prop must be a static bool, not a Var."
            raise TypeError(msg)
        if unstyled:
            return
        user_class_name = props.get("class_name")
        if user_class_name is None or (
            isinstance(user_class_name, str) and not user_class_name
        ):
            props["class_name"] = default_class_name
        else:
            props["class_name"] = cn(default_class_name, user_class_name)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "unstyled",
        ]
