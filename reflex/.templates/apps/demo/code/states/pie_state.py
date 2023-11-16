from typing import Any

import reflex as rx

from ..state import State


class PieChartState(State):
    """Pie Chart State."""

    resources: list[dict[str, Any]] = [
        dict(type_="🏆", count=1),
        dict(type_="🪵", count=1),
        dict(type_="🥑", count=1),
        dict(type_="🧱", count=1),
    ]

    @rx.cached_var
    def resource_types(self) -> list[str]:
        """Get the resource types.

        Returns:
            The resource types.
        """
        return [r["type_"] for r in self.resources]

    def increment(self, type_: str):
        """Increment the count of a resource type.

        Args:
            type_: The type of resource to increment.
        """
        for resource in self.resources:
            if resource["type_"] == type_:
                resource["count"] += 1
                break

    def decrement(self, type_: str):
        """Decrement the count of a resource type.

        Args:
            type_: The type of resource to decrement.
        """
        for resource in self.resources:
            if resource["type_"] == type_ and resource["count"] > 0:
                resource["count"] -= 1
                break
