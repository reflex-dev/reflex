"""Independently authored realistic nested-inventory update reproduction."""

import json
import os
from pathlib import Path
import reflex as rx

assert str(Path(os.environ["REFLEX_EXPECT_ENV"]) / "lib") in rx.__file__, rx.__file__
print("INVENTORY_VERIFIER", rx.__file__, flush=True)


class Warehouse(rx.State):
    """Stocks reserved by a normal public event with a pure cached total."""

    inventory: dict[str, dict[str, int]] = {
        "tea": {"stock": 10},
        "coffee": {"stock": 20},
    }
    audit: str = ""

    @rx.var
    def total(self) -> int:
        """Compute total remaining stock without side effects.

        Returns:
            Sum of current item stock counts.
        """
        return sum(item["stock"] for item in self.inventory.values())

    def _audit(self, operation: str):
        """Expose a backend snapshot independently of the raw inventory UI.

        Args:
            operation: Action performed.
        """
        self.audit = json.dumps(
            {
                "operation": operation,
                "backend": {
                    key: self.inventory[key]["stock"] for key in self.inventory
                },
                "cached_total": self.total,
            },
            sort_keys=True,
        )
        print("AUDIT", self.audit, flush=True)

    @rx.event
    def reserve_values(self):
        """Reserve one of each product using normal dictionary values iteration."""
        for item in self.inventory.values():
            item["stock"] -= 1
        self._audit("values")

    @rx.event
    def reserve_items(self):
        """Reserve one of each product using normal dictionary items iteration."""
        for _, item in self.inventory.items():
            item["stock"] -= 1
        self._audit("items")

    @rx.event
    def reserve_keys(self):
        """Reserve through indexed mutation as a positive control."""
        for key in self.inventory:
            self.inventory[key]["stock"] -= 1
        self._audit("keys")

    @rx.event
    def reassign(self):
        """Copy and reassign current values to invalidate their dependencies."""
        self.inventory = {
            key: {"stock": self.inventory[key]["stock"]} for key in self.inventory
        }
        self._audit("reassign")

    @rx.event
    def inspect_backend(self):
        """Read current backend data without modifying inventory."""
        self._audit("inspect")

    @rx.event
    def reset_inventory(self):
        """Reset the independent scenario to its known initial state."""
        self.inventory = {"tea": {"stock": 10}, "coffee": {"stock": 20}}
        self._audit("reset")


def index() -> rx.Component:
    """Build an inventory screen with visible positive/negative controls.

    Returns:
        Stock values, pure cached total and public operation controls.
    """
    return rx.vstack(
        rx.heading("Warehouse reservations"),
        rx.text("Tea: ", Warehouse.inventory["tea"]["stock"], id="tea"),
        rx.text("Coffee: ", Warehouse.inventory["coffee"]["stock"], id="coffee"),
        rx.text("Total: ", Warehouse.total, id="total"),
        rx.hstack(
            rx.button(
                "Reserve via values", id="values", on_click=Warehouse.reserve_values
            ),
            rx.button(
                "Reserve via items", id="items", on_click=Warehouse.reserve_items
            ),
            rx.button("Reserve via keys", id="keys", on_click=Warehouse.reserve_keys),
        ),
        rx.hstack(
            rx.button("Reassign inventory", id="reassign", on_click=Warehouse.reassign),
            rx.button(
                "Inspect backend", id="inspect", on_click=Warehouse.inspect_backend
            ),
            rx.button("Reset", id="reset", on_click=Warehouse.reset_inventory),
        ),
        rx.text(Warehouse.audit, id="audit"),
        spacing="3",
        padding="24px",
        width="100%",
    )


app = rx.App()
app.add_page(index)
