"""React-Player component."""

from __future__ import annotations

from typing import Any, TypedDict

from reflex.components.component import Component
from reflex.components.core.cond import cond
from reflex.event import EventHandler, no_args_event_spec
from reflex.utils import console
from reflex.vars.base import Var
from reflex.vars.object import ObjectVar

ReactPlayerEvent = ObjectVar[dict[str, dict[str, dict[str, Any]]]]


class Progress(TypedDict):
    """Callback containing played and loaded progress as a fraction, and playedSeconds and loadedSeconds in seconds."""

    played: float
    playedSeconds: float
    loaded: float
    loadedSeconds: float
    duration: float


def _on_progress_signature(event: ReactPlayerEvent) -> list[Var[Progress]]:
    """Type signature for on_progress event.

    Args:
        event: The event variable.

    Returns:
        The progress information extracted from the event.
    """
    player_info = event["target"]["api"]["playerInfo"].to(dict)
    progress_state = player_info["progressState"].to(dict)
    current = progress_state["current"].to(float)
    loaded = progress_state["loaded"].to(float)
    duration = progress_state["duration"].to(float)
    return [
        cond(
            progress_state,
            {
                "played": cond(duration, current / duration, 0.0),
                "playedSeconds": current,
                "loaded": cond(duration, loaded / duration, 0.0),
                "loadedSeconds": loaded,
                "duration": duration,
            },
            {
                "played": 0.0,
                "playedSeconds": 0.0,
                "loaded": 0.0,
                "loadedSeconds": 0.0,
                "duration": 0.0,
            },
        ).to(Progress)
    ]


def _player_info_key_or_zero(event: ReactPlayerEvent, key: str) -> Var[float]:
    """Helper to extract a value from playerInfo or return 0.0 if not available.

    Args:
        event: The event variable.
        key: The key to extract from playerInfo.

    Returns:
        The extracted value or 0.0 if not available.
    """
    player_info = event["target"]["api"]["playerInfo"].to(dict)
    return cond(
        player_info[key],
        player_info[key],
        0.0,
    ).to(float)


def _on_time_update_signature(event: ReactPlayerEvent) -> list[Var[float]]:
    """Type signature for on_time_update event.

    Args:
        event: The event variable.

    Returns:
        The current timestamp in seconds.
    """
    return [_player_info_key_or_zero(event, "currentTime")]


def _on_duration_change_signature(event: ReactPlayerEvent) -> list[Var[float]]:
    """Type signature for on_duration_change event.

    Args:
        event: The event variable.

    Returns:
        The active media's duration in seconds.
    """
    return [_player_info_key_or_zero(event, "duration")]


def _on_rate_change_signature(event: ReactPlayerEvent) -> list[Var[float]]:
    """Type signature for on_rate_change event.

    Args:
        event: The event variable.

    Returns:
        The current playback rate.
    """
    return [_player_info_key_or_zero(event, "playbackRate")]


_DEPRECATED_PROP_MAP = {
    "url": "src",
    "on_duration": "on_duration_change",
    "on_playback_rate_change": "on_rate_change",
    "on_seek": "on_seeked",
    "on_buffer": "on_waiting",
    "on_buffer_end": "on_playing",
    "on_enable_pip": "on_enter_picture_in_picture",
    "on_disable_pip": "on_leave_picture_in_picture",
}


class ReactPlayer(Component):
    """Using react-player and not implement all props and callback yet.
    reference: https://github.com/cookpete/react-player.
    """

    library = "react-player@3.4.0"

    tag = "ReactPlayer"

    is_default = True

    # The url of a video or song to play
    src: Var[str | list[str] | list[dict[str, str]]]

    # Set to true or false to pause or play the media
    playing: Var[bool]

    # Set to true or false to loop the media
    loop: Var[bool]

    # Set to true or false to display native player controls.
    controls: Var[bool] = Var.create(True)

    # Set to true to show just the video thumbnail, which loads the full player on click
    light: Var[bool]

    # Set the volume of the player, between 0 and 1
    volume: Var[float]

    # Mutes the player
    muted: Var[bool]

    # Player-specific configuration parameters.
    config: Var[dict[str, Any]]

    # Set to true to disable the default remote playback option on supported devices.
    disable_remote_playback: Var[bool]

    # Called when media is loaded and ready to play. If playing is set to true, media will play immediately.
    on_ready: EventHandler[no_args_event_spec]

    # Called when media starts playing.
    on_start: EventHandler[no_args_event_spec]

    # Called when playing is set to true.
    on_play: EventHandler[no_args_event_spec]

    # Called when media starts or resumes playing after pausing or buffering.
    on_playing: EventHandler[no_args_event_spec]

    # Called while the video is loading only. Contains played and loaded progress as a fraction, and playedSeconds and loadedSeconds in seconds. eg { played: 0.12, playedSeconds: 11.3, loaded: 0.34, loadedSeconds: 16.7 }
    on_progress: EventHandler[_on_progress_signature]

    # Called when the media's current time changes (~4Hz, use .throttle to limit calls to backend).
    on_time_update: EventHandler[_on_time_update_signature]

    # Callback containing duration of the media, in seconds.
    on_duration_change: EventHandler[_on_duration_change_signature]

    # Called when media is paused.
    on_pause: EventHandler[no_args_event_spec]

    # Called when media starts buffering.
    on_waiting: EventHandler[no_args_event_spec]

    # Called when the media is seeking.
    on_seeking: EventHandler[no_args_event_spec]

    # Called when media seeks with seconds parameter.
    on_seeked: EventHandler[_on_time_update_signature]

    # Called when playback rate of the player changed. Only supported by YouTube, Vimeo (if enabled), Wistia, and file paths.
    on_rate_change: EventHandler[_on_rate_change_signature]

    # Called when media finishes playing. Does not fire when loop is set to true.
    on_ended: EventHandler[no_args_event_spec]

    # Called when an error occurs whilst attempting to play media.
    on_error: EventHandler[no_args_event_spec]

    # Called when user clicks the light mode preview.
    on_click_preview: EventHandler[no_args_event_spec]

    # Called when picture-in-picture mode is enabled.
    on_enter_picture_in_picture: EventHandler[no_args_event_spec]

    # Called when picture-in-picture mode is disabled.
    on_leave_picture_in_picture: EventHandler[no_args_event_spec]

    @classmethod
    def create(cls, *children, **props) -> ReactPlayer:
        """Create a component.

        Args:
            children: The children of the component.
            props: The props of the component.

        Returns:
            The created component.

        Raises:
            ValueError: If both a deprecated prop and its replacement are both passed.
        """
        for prop, new_prop in _DEPRECATED_PROP_MAP.items():
            if prop in props:
                if new_prop in props:
                    msg = (
                        f"The prop {prop!r} is deprecated, but the replacement {new_prop!r} is also passed. Please remove {prop!r}.",
                    )
                    raise ValueError(msg)
                console.warn(
                    f"The prop {prop!r} has been replaced by {new_prop!r}, please update your code.",
                )
                props[new_prop] = props.pop(prop)
        return super().create(*children, **props)  # type: ignore[return-value]

    def _render(self, props: dict[str, Any] | None = None):
        """Render the component. Adds width and height set to None because
        react-player will set them to some random value that overrides the
        css width and height.

        Args:
            props: The props to pass to the component.

        Returns:
            The rendered component.
        """
        return (
            super()
            ._render(props)
            .add_props(
                width=Var.create(None),
                height=Var.create(None),
            )
        )
