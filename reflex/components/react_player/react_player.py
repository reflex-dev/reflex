"""React-Player component."""

from __future__ import annotations

from reflex.components.component import NoSSRComponent
from reflex.event import EventHandler
from reflex.vars import Var


class ReactPlayer(NoSSRComponent):
    """Using react-player and not implement all props and callback yet.
    reference: https://github.com/cookpete/react-player.
    """

    library = "react-player@2.12.0"

    tag = "ReactPlayer"

    is_default = True

    # The url of a video or song to play
    url: Var[str]

    # Set to true or false to pause or play the media
    playing: Var[bool]

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

    # Called when media is loaded and ready to play. If playing is set to true, media will play immediately.
    on_ready: EventHandler[lambda: []]

    # Called when media starts playing.
    on_start: EventHandler[lambda: []]

    # Called when media starts or resumes playing after pausing or buffering.
    on_play: EventHandler[lambda: []]

    # Callback containing played and loaded progress as a fraction, and playedSeconds and loadedSeconds in seconds. eg { played: 0.12, playedSeconds: 11.3, loaded: 0.34, loadedSeconds: 16.7 }
    on_progress: EventHandler[lambda progress: [progress]]

    # Callback containing duration of the media, in seconds.
    on_duration: EventHandler[lambda seconds: [seconds]]

    # Called when media is paused.
    on_pause: EventHandler[lambda: []]

    # Called when media starts buffering.
    on_buffer: EventHandler[lambda: []]

    # Called when media has finished buffering. Works for files, YouTube and Facebook.
    on_buffer_end: EventHandler[lambda: []]

    # Called when media seeks with seconds parameter.
    on_seek: EventHandler[lambda seconds: [seconds]]

    # Called when playback rate of the player changed. Only supported by YouTube, Vimeo (if enabled), Wistia, and file paths.
    on_playback_rate_change: EventHandler[lambda e0: []]

    # Called when playback quality of the player changed. Only supported by YouTube (if enabled).
    on_playback_quality_change: EventHandler[lambda e0: []]

    # Called when media finishes playing. Does not fire when loop is set to true.
    on_ended: EventHandler[lambda: []]

    # Called when an error occurs whilst attempting to play media.
    on_error: EventHandler[lambda: []]

    # Called when user clicks the light mode preview.
    on_click_preview: EventHandler[lambda: []]

    # Called when picture-in-picture mode is enabled.
    on_enable_pip: EventHandler[lambda: []]

    # Called when picture-in-picture mode is disabled.
    on_disable_pip: EventHandler[lambda: []]
