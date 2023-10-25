from ..state import State
from typing import Any
import reflex as rx


class PieChartState(State):
    resources: list[dict[str, Any]] = [
        dict(type_="🏆", count=1),
        dict(type_="🪵", count=1),
        dict(type_="🥑", count=1),
        dict(type_="🧱", count=1),
    ]

    @rx.cached_var
    def resource_types(self) -> list[str]:
        return [r["type_"] for r in self.resources]

    def increment(self, type_: str):
        for resource in self.resources:
            if resource["type_"] == type_:
                resource["count"] += 1
                break

    def decrement(self, type_: str):
        for resource in self.resources:
            if (
                resource["type_"] == type_
                and resource["count"] > 0
            ):
                resource["count"] -= 1
                break