"""Use typed State callbacks in a small inventory app without suppression."""

from collections.abc import Callable
from typing import Any, assert_type

import reflex as rx
from reflex_base.event import EventCallback


class Inventory(rx.State):
    """Expose callbacks with each supported fixed argument count."""

    quantity: int = 3
    product: str = "Notebook"

    @rx.event
    def refresh(self) -> None:
        """Refresh the current inventory."""

    @rx.event
    def receive(self, quantity: int) -> None:
        """Receive inventory.

        Args:
            quantity: Number of incoming items.
        """
        self.quantity += quantity

    @rx.event
    def rename(self, quantity: int, name: str) -> None:
        """Update the inventory record.

        Args:
            quantity: Inventory amount.
            name: Product description.
        """
        self.quantity, self.product = quantity, name

    @rx.event
    def flag(self, quantity: int, name: str, enabled: bool) -> None:
        """Receive a record and its availability flag.

        Args:
            quantity: Inventory amount.
            name: Product description.
            enabled: Availability flag.
        """

    @rx.event
    def quote(self, quantity: int, name: str, enabled: bool, price: float) -> None:
        """Receive a priced inventory record.

        Args:
            quantity: Inventory amount.
            name: Product description.
            enabled: Availability flag.
            price: Unit price.
        """


assert_type(Inventory.refresh(), EventCallback[()])
assert_type(Inventory.receive(2), EventCallback[()])
assert_type(Inventory.receive(Inventory.quantity), EventCallback[()])
assert_type(Inventory.rename(Inventory.quantity, Inventory.product), EventCallback[()])
assert_type(Inventory.flag(2, "Notebook", True), EventCallback[()])
assert_type(Inventory.quote(2, "Notebook", True, 4.5), EventCallback[()])
assert_type(Inventory.rename(Inventory.quantity), EventCallback[str])
assert_type(Inventory.flag(Inventory.quantity), EventCallback[str, bool])
assert_type(Inventory.quote(Inventory.quantity, "Notebook", True), EventCallback[float])
receive_callback: Callable[[int], Any] = Inventory.receive
rename_callback: Callable[[int, str], Any] = Inventory.rename
quote_callback: Callable[[int, str, bool, float], Any] = Inventory.quote
