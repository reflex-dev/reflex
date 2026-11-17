"""User preferences: a dict of switches and a few scalar choices."""

import reflex as rx

ACCENTS = ("violet", "teal", "orange", "crimson")


class SettingsState(rx.State):
    """The preferences the settings page edits."""

    display_name: str = "Guest"
    accent: str = "violet"
    compact: bool = False
    volume: int = 50
    switches: dict[str, bool] = {"emails": True, "sounds": False, "beta": False}

    @rx.var
    def enabled_switches(self) -> str:
        """List the switches that are on.

        Returns:
            Their names, comma separated, or ``none``.
        """
        return ", ".join(name for name, on in self.switches.items() if on) or "none"

    @rx.event
    def set_display_name(self, value: str):
        """Change the display name.

        Args:
            value: The name.
        """
        self.display_name = value

    @rx.event
    def set_accent(self, value: str):
        """Choose an accent color.

        Args:
            value: One of the accents.
        """
        if value in ACCENTS:
            self.accent = value

    @rx.event
    def set_compact(self, value: bool):
        """Turn the compact layout on or off.

        Args:
            value: Whether it is on.
        """
        self.compact = value

    @rx.event
    def set_volume(self, value: list[int | float]):
        """Set the volume.

        Args:
            value: The slider's values; the first is the volume.
        """
        self.volume = int(value[0])

    @rx.event
    def flip(self, name: str):
        """Flip one switch, setting one key of the dict.

        Args:
            name: The switch.
        """
        self.switches[name] = not self.switches.get(name, False)
