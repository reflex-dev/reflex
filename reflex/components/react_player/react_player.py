"""React-Player component."""
from __future__ import annotations

from typing import Optional

from reflex.components.component import NoSSRComponent
from reflex.vars import Var


class ReactPlayer(NoSSRComponent):
    """Using react-player and not implement all props and callback yet.
    reference: https://github.com/cookpete/react-player.
    """

    library = "react-player@2.12.0"

    tag = "ReactPlayer"

    is_default = True

    # The url of a video or song to play
    url: Optional[Var[str]] = None

    # Set to true or false to pause or play the media
    playing: Optional[Var[bool]] = None

    # Set to true or false to loop the media
    loop: Optional[Var[bool]] = None

    # Set to true or false to display native player controls.
    controls: Var[bool] = True  # type: ignore

    # Set to true to show just the video thumbnail, which loads the full player on click
    light: Optional[Var[bool]] = None

    # Set the volume of the player, between 0 and 1
    volume: Optional[Var[float]] = None

    # Mutes the player
    muted: Optional[Var[bool]] = None

    # Set the width of the player: ex:640px
    width: Optional[Var[str]] = None

    # Set the height of the player: ex:640px
    height: Optional[Var[str]] = None
