"""Local media, toast and icon interaction smoke."""

import reflex as rx


class MediaState(rx.State):
    """Track media and icon interactions."""

    playing: bool = False
    plays: int = 0
    pauses: int = 0
    selected: bool = False

    @rx.event
    def toggle_play(self):
        """Toggle the local video's controlled playback."""
        self.playing = not self.playing

    @rx.event
    def on_play(self):
        """Count native playback callbacks."""
        self.plays += 1

    @rx.event
    def on_pause(self):
        """Count native pause callbacks."""
        self.pauses += 1

    @rx.event
    def toggle_selected(self):
        """Switch the icon state."""
        self.selected = not self.selected


def new_components() -> rx.Component:
    """Render deterministic media, toast and icon checks.

    Returns:
        A page using local assets only.
    """
    return rx.vstack(
        rx.heading("Published component smoke"),
        rx.video(
            src="/probe.mp4",
            playing=MediaState.playing,
            muted=True,
            loop=True,
            on_play=MediaState.on_play,
            on_pause=MediaState.on_pause,
            width="320px",
            height="180px",
            id="local-video",
        ),
        rx.button("Play or pause", id="media-toggle", on_click=MediaState.toggle_play),
        rx.text(MediaState.plays, id="media-plays"),
        rx.text(MediaState.pauses, id="media-pauses"),
        rx.button(
            rx.cond(
                MediaState.selected,
                rx.icon("heart", color="red"),
                rx.icon("heart", color="gray"),
            ),
            "Select icon",
            id="icon-toggle",
            on_click=MediaState.toggle_selected,
        ),
        rx.text(MediaState.selected.to_string(), id="icon-selected"),
        rx.button(
            "Show toast",
            id="show-toast",
            on_click=rx.toast.success("Local toast passed", duration=5000),
        ),
        padding="2em",
    )
