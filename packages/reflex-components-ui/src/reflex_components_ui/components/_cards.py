"""What radio cards and checkbox cards share: a grid of labels around inputs."""

from __future__ import annotations

from typing import Any, ClassVar

from reflex_base.components.component import Component
from reflex_base.components.tags import CommonTag

from reflex_components_ui.base import UIComponent
from reflex_components_ui.components._group import GroupInput, GroupMember, GroupRoot


class CardsRoot(GroupRoot):
    """The root of a grid of cards to choose from."""

    tag = "div"

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the items off the element.

        Returns:
            The props read as styles, what the group hands its items, and
            what says how the arrow keys move through a group of Radix: the
            browser moves through native inputs.
        """
        return [
            *super()._exclude_props(),
            "variant",
            "high_contrast",
            "value",
            "default_value",
            "disabled",
            "name",
            "required",
            "orientation",
            "loop",
        ]


class CardsItem(GroupMember, UIComponent):
    """A card of a group: a label around the input that is its state."""

    tag = "label"

    # The input of the card, and whether it comes after the children.
    _input: ClassVar[type[GroupInput]]
    _input_last: ClassVar[bool] = False

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a card: a label that holds its input and the children.

        Args:
            *children: What the card shows.
            **props: The props of the card. Its styles are those of the
                label, and everything else is given to the input.

        Returns:
            The label.
        """
        fields = cls._input.get_fields()
        own = {
            key: props.pop(key)
            for key in list(props)
            if key in fields or key.startswith(("on_", "aria_", "data_"))
        }
        field = cls._input.create(**own)
        if cls._input_last:
            return super().create(*children, field, **props)
        return super().create(field, *children, **props)

    def _post_init(self, *args, **kwargs):
        """Initialize the card, with the look of a group without props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as variants: the group sets both.
        self._variant: Any = None
        self._high_contrast: Any = None
        super()._post_init(*args, **kwargs)

    def _join(self, group: Any) -> None:
        """Take the look of the card from the group.

        Args:
            group: The group the card is in.
        """
        self._variant = group.variant
        self._high_contrast = group.high_contrast
        self._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the input off the label.

        Returns:
            The props read as styles, and the ones of the input.
        """
        return [*super()._exclude_props(), "value", "disabled", "required"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the card.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, marked for the rule that keeps the pointer off what a
            card holds.
        """
        return super()._render(props).add_props(**{"data-rx-cards-item": ""})
