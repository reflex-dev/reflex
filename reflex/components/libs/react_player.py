"""React-Player component."""

from __future__ import annotations

from typing import Optional

from reflex.components.component import Component
from reflex.utils import imports
from reflex.vars import Var


class ReactPlayerComponent(Component):
    """Using react-player and not implement all props and callback yet.
    reference: https://github.com/cookpete/react-player.
    """

    library = "react-player"

    tag = "ReactPlayer"

    # The url of a video or song to play
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

    # Mutes the player
    muted: Var[bool]

    # Set the width of the player: ex:640px
    width: Var[str]

    # Set the height of the player: ex:640px
    height: Var[str]

    def _get_imports(self) -> Optional[imports.ImportDict]:
        return {}

    def _get_custom_code(self) -> Optional[str]:
        return """
import dynamic from "next/dynamic";
const ReactPlayer = dynamic(() => import("react-player/lazy"), { ssr: false });
"""
