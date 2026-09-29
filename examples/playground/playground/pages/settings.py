"""The settings page: radix controls bound to a state with a dict of switches."""

import reflex as rx

from playground.layout import layout
from playground.states.settings import ACCENTS, SettingsState


def setting(label: str, control: rx.Component) -> rx.Component:
    """Render one setting.

    Args:
        label: What it sets.
        control: The control.

    Returns:
        The label and the control, side by side.
    """
    return rx.hstack(
        rx.text(label, weight="medium", class_name="w-40"), control, align="center"
    )


def settings() -> rx.Component:
    """Render the settings page.

    Returns:
        The settings, in tabs.
    """
    return layout(
        rx.vstack(
            rx.heading("Settings"),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger(
                        "Profile", value="profile", id="settings-tab-profile"
                    ),
                    rx.tabs.trigger(
                        "Notifications",
                        value="notifications",
                        id="settings-tab-notifications",
                    ),
                    rx.tabs.trigger(
                        "Appearance", value="appearance", id="settings-tab-appearance"
                    ),
                ),
                rx.tabs.content(
                    rx.vstack(
                        setting(
                            "Display name",
                            rx.input(
                                value=SettingsState.display_name,
                                on_change=SettingsState.set_display_name,
                                id="settings-name",
                            ),
                        ),
                        setting(
                            "Volume",
                            rx.slider(
                                default_value=[50],
                                on_value_commit=SettingsState.set_volume,
                                width="12rem",
                                id="settings-volume",
                            ),
                        ),
                        rx.text("Hello, ", SettingsState.display_name, "!"),
                        padding_top="1em",
                    ),
                    value="profile",
                ),
                rx.tabs.content(
                    rx.vstack(
                        *[
                            setting(
                                name.capitalize(),
                                rx.switch(
                                    checked=SettingsState.switches[name],
                                    on_change=lambda _, name=name: SettingsState.flip(
                                        name
                                    ),
                                    id=f"settings-switch-{name}",
                                ),
                            )
                            for name in ("emails", "sounds", "beta")
                        ],
                        rx.text(
                            "On: ", SettingsState.enabled_switches, id="settings-on"
                        ),
                        padding_top="1em",
                    ),
                    value="notifications",
                ),
                rx.tabs.content(
                    rx.vstack(
                        setting(
                            "Accent",
                            rx.radio_group(
                                list(ACCENTS),
                                value=SettingsState.accent,
                                on_change=SettingsState.set_accent,
                                direction="row",
                                id="settings-accent",
                            ),
                        ),
                        setting(
                            "Compact",
                            rx.checkbox(
                                checked=SettingsState.compact,
                                on_change=SettingsState.set_compact,
                                id="settings-compact",
                            ),
                        ),
                        setting(
                            "Color mode", rx.color_mode.switch(id="settings-color-mode")
                        ),
                        rx.callout(
                            "The accent previews here; the app theme stays violet.",
                            icon="info",
                            color_scheme=SettingsState.accent,  # pyright: ignore[reportArgumentType]
                            size=rx.cond(SettingsState.compact, "1", "2"),
                            id="settings-preview",
                        ),
                        padding_top="1em",
                    ),
                    value="appearance",
                ),
                default_value="profile",
                width="100%",
            ),
            width="100%",
        )
    )
