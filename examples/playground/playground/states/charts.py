"""Chart data: a series for recharts and a figure for plotly, both computed from the state."""

import math

import reflex as rx

KINDS = ("line", "area", "bar")


class ChartsState(rx.State):
    """The chart's resolution, phase and kind."""

    points: int = 24
    phase: int = 0
    kind: str = "line"

    @rx.var
    def series(self) -> list[dict[str, float | int]]:
        """Sample two waves.

        Returns:
            One entry per point: ``x``, ``sine`` and ``cosine``.
        """
        step = 2 * math.pi / self.points
        return [
            {
                "x": index,
                "sine": round(100 * math.sin(index * step + self.phase / 4), 2),
                "cosine": round(100 * math.cos(index * step + self.phase / 4), 2),
            }
            for index in range(self.points + 1)
        ]

    @rx.var
    def figure(self) -> dict:
        """Build a plotly figure as a plain dict.

        Returns:
            The figure: one scatter trace and a layout.
        """
        series = self.series
        return {
            "data": [
                {
                    "type": "scatter",
                    "mode": "lines+markers",
                    "name": "sine",
                    "x": [point["x"] for point in series],
                    "y": [point["sine"] for point in series],
                }
            ],
            "layout": {"title": {"text": f"{self.points} points"}, "height": 320},
        }

    @rx.event
    def set_points(self, value: list[int | float]):
        """Change the resolution.

        Args:
            value: The slider's values; the first is the number of points.
        """
        self.points = max(4, int(value[0]))

    @rx.event
    def shift(self):
        """Move the waves along."""
        self.phase += 1

    @rx.event
    def set_kind(self, value: str):
        """Choose the recharts chart.

        Args:
            value: One of ``line``, ``area`` and ``bar``.
        """
        if value in KINDS:
            self.kind = value
