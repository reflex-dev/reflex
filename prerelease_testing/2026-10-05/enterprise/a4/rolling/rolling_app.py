"""Declare identical app state in the old and alpha published wheel envs."""

import reflex as rx


class Rolling(rx.State):
    """Keep frontend, backend, and mutable vars shared by rolling workers."""

    count: int = 1
    label: str = "seed"
    values: list[int] = [1]
    _secret: int = 2
    _items: list[str] = ["seed"]

    @rx.var
    def checksum(self) -> int:
        """Compute a value depending on both public and backend fields.

        Returns:
            The combined field checksum.
        """
        return self.count + self._secret + len(self._items) + sum(self.values)
