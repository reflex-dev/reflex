"""A video component."""

from typing import Optional, Union, Any

from reflex.components.libs.react_player import ReactPlayerComponent
from reflex.components.component import Component
from reflex.vars import Var

class Video(ReactPlayerComponent):
    """Video component share with audio component."""

    library = "react-player@^2.12.0"

    tag = "ReactPlayer"

    is_default = True

    # The url of a video to play
    url: Var[str]

    # Set to true or false to pause or play the media
    playing: Var[str]

    # Set to true or false to loop the media
    loop: Var[bool]

    # Set to true or false to display native player controls.
    controls: Var[bool] = True  # type: ignore

    # Set to true to show just the video thumbnail, which loads the full player on click
    light: Var[bool]

    # Set the volume of the player, between 0 and 1
    volume: Var[float]

    # Mutes the player (only works if volume is set)
    muted: Var[bool]

    # Set the width of the player: ex:640px
    width: Var[str]

    # Set the height of the player: ex:640px
    height: Var[str]

    # Fallback Reflex component to use as a fallback if you are using lazy loading
    #fallback: Optional[Component] = None

    # Component to use as the play icon in light mode
    #play_icon: Optional[Component]


    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_error": lambda: [],
        }

