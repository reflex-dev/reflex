"""Avatar components."""
from __future__ import annotations

from typing import Any, Optional, Union

from reflex.components.chakra import ChakraComponent, LiteralAvatarSize
from reflex.vars import Var


class Avatar(ChakraComponent):
    """The image that represents the user."""

    tag = "Avatar"

    # The default avatar used as fallback when name, and src is not specified.
    icon: Optional[Var[str]] = None

    # The label of the icon.
    icon_label: Optional[Var[str]] = None

    # If true, opt out of the avatar's fallback logic and renders the img at all times.
    ignore_fallback: Optional[Var[bool]] = None

    # The name of the person in the avatar.
    name: Optional[Var[str]] = None

    # If true, the Avatar will show a border around it. Best for a group of avatars.
    show_border: Optional[Var[bool]] = None

    # The image url of the Avatar.
    src: Optional[Var[str]] = None

    # List of sources to use for different screen resolutions.
    src_set: Optional[Var[str]] = None

    # "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "full"
    size: Optional[Var[LiteralAvatarSize]] = None

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_error": lambda: [],
        }


class AvatarBadge(ChakraComponent):
    """A wrapper that displays its content on the right corner of the avatar."""

    tag = "AvatarBadge"


class AvatarGroup(ChakraComponent):
    """A wrapper to stack multiple Avatars together."""

    tag = "AvatarGroup"

    # The maximum number of visible avatars.
    max_: Optional[Var[int]] = None

    # The space between the avatars in the group.
    spacing: Optional[Var[int]] = None
