"""An alert callout for important messages."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.vars.base import Var

from reflex_components_core.el.elements.typography import Div
from reflex_components_core.ui.base import UIComponent
from reflex_components_core.ui.styling import variant_class

LiteralAlertVariant = Literal["default", "destructive"]

ALERT_CLASS_NAME = (
    "relative w-full rounded-lg border border-border px-4 py-3 text-sm "
    "grid grid-cols-[0_1fr] gap-y-0.5 items-start "
    "has-[>svg]:grid-cols-[calc(var(--spacing)*4)_1fr] has-[>svg]:gap-x-3 "
    "[&>svg]:size-4 [&>svg]:translate-y-0.5 [&>svg]:text-current"
)

ALERT_VARIANTS: dict[str, str] = {
    "default": "bg-card text-card-foreground",
    "destructive": (
        "text-destructive bg-card *:data-[slot=alert-description]:text-destructive/90"
    ),
}

ALERT_TITLE_CLASS_NAME = "col-start-2 line-clamp-1 min-h-4 font-medium tracking-tight"

ALERT_DESCRIPTION_CLASS_NAME = (
    "col-start-2 grid justify-items-start gap-1 text-sm "
    "text-muted-foreground [&_p]:leading-relaxed"
)


class Alert(Div, UIComponent):
    """A callout that draws attention to important information."""

    _slot: ClassVar[str | None] = "alert"

    variant: Var[LiteralAlertVariant] = field(
        doc='Visual style of the alert. Defaults to "default".'
    )

    @classmethod
    def create(cls, *children, **props):
        """Create an alert.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The alert component.
        """
        variant = variant_class(
            props.pop("variant", None),
            ALERT_VARIANTS,
            default="default",
            prop="variant",
            component="rx.ui.alert",
        )
        props.setdefault("role", "alert")
        default_class_name: str | list = (
            f"{ALERT_CLASS_NAME} {variant}"
            if isinstance(variant, str)
            else [ALERT_CLASS_NAME, variant]
        )
        cls._apply_class_name(default_class_name, props)
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "variant",
        ]


class AlertTitle(Div, UIComponent):
    """The title of an alert."""

    _slot: ClassVar[str | None] = "alert-title"

    @classmethod
    def create(cls, *children, **props):
        """Create an alert title.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The alert title component.
        """
        cls._apply_class_name(ALERT_TITLE_CLASS_NAME, props)
        return super().create(*children, **props)


class AlertDescription(Div, UIComponent):
    """The description of an alert."""

    _slot: ClassVar[str | None] = "alert-description"

    @classmethod
    def create(cls, *children, **props):
        """Create an alert description.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The alert description component.
        """
        cls._apply_class_name(ALERT_DESCRIPTION_CLASS_NAME, props)
        return super().create(*children, **props)


class AlertNamespace(ComponentNamespace):
    """Namespace for alert components."""

    root = staticmethod(Alert.create)
    title = staticmethod(AlertTitle.create)
    description = staticmethod(AlertDescription.create)
    __call__ = staticmethod(Alert.create)


alert = AlertNamespace()
