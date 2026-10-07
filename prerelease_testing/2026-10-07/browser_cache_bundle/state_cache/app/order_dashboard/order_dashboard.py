"""Realistic nested order state with independent browser assertions."""

import asyncio
import dataclasses
import json
import os

import reflex as rx

assert f"/envs/{os.environ['REFLEX_TEST_ENV']}/" in rx.__file__, rx.__file__


@dataclasses.dataclass
class Options:
    """Per-line fulfillment options with independent mutable defaults."""

    tags: list[str] = dataclasses.field(default_factory=lambda: ["fresh"])
    attributes: dict[str, dict[str, str]] = dataclasses.field(
        default_factory=lambda: {"warehouse": {"zone": "A"}}
    )


@dataclasses.dataclass
class Line:
    """One order line and its nested fulfillment metadata."""

    sku: str
    unit_cents: int
    qty: int
    options: Options = dataclasses.field(default_factory=Options)


def seed_lines() -> list[Line]:
    """Create independent initial line objects.

    Returns:
        Initial tea and mug lines.
    """
    return [Line("tea", 700, 2), Line("mug", 1200, 1)]


def seed_inventory() -> dict[str, dict[str, int]]:
    """Create independently owned inventory dictionaries.

    Returns:
        The initial stock map.
    """
    return {"tea": {"stock": 10}, "mug": {"stock": 20}}


class Cart(rx.State):
    """Cart data plus cached and uncached independent projections."""

    lines: list[Line] = rx.field(default_factory=seed_lines)
    inventory: dict[str, dict[str, int]] = rx.field(default_factory=seed_inventory)
    rules: dict[str, dict[str, int]] = {"discount": {"percent": 0}}
    default_matrix: list[list[int]] = [[1]]
    _notes: list[str] = rx.field(default_factory=list)
    receipt: str = ""

    @rx.var(cache=True)
    def subtotal(self) -> int:
        """Sum cached line totals.

        Returns:
            The cart subtotal in cents.
        """
        return sum(line.qty * line.unit_cents for line in self.lines)

    @rx.var(cache=False)
    def uncached_subtotal(self) -> int:
        """Compute the same total without a cache.

        Returns:
            The cart subtotal in cents.
        """
        return sum(line.qty * line.unit_cents for line in self.lines)

    @rx.var(cache=True)
    def net(self) -> int:
        """Apply a nested discount to another computed var.

        Returns:
            The discounted subtotal in cents.
        """
        return self.subtotal * (100 - self.rules["discount"]["percent"]) // 100

    @rx.var(cache=True)
    def cached_lines(self) -> str:
        """Serialize proxied nested dataclasses through the cached path.

        Returns:
            A JSON array of full order lines.
        """
        return json.dumps(
            [dataclasses.asdict(line) for line in self.lines], sort_keys=True
        )

    @rx.var(cache=False)
    def uncached_lines(self) -> str:
        """Serialize the same lines without a cache.

        Returns:
            A JSON array of full order lines.
        """
        return json.dumps(
            [dataclasses.asdict(line) for line in self.lines], sort_keys=True
        )

    @rx.var(cache=True)
    def ranked(self) -> list[str]:
        """Read dataclasses through sorted iteration.

        Returns:
            SKUs sorted by descending quantity, then name.
        """
        return [
            line.sku
            for line in sorted(self.lines, key=lambda line: (-line.qty, line.sku))
        ]

    @rx.var(cache=True)
    def stock_total(self) -> int:
        """Read nested dictionaries through values iteration.

        Returns:
            Total stock across the catalog.
        """
        return sum(item["stock"] for item in self.inventory.values())

    @rx.var(cache=True)
    def notes(self) -> str:
        """Expose the backend-only audit trail through a cached projection.

        Returns:
            JSON audit entries.
        """
        return json.dumps(self._notes)

    @rx.event
    def mutate(self, operation: str):
        """Apply one ordinary order-management operation.

        Args:
            operation: The requested operation identifier.
        """
        if operation == "quantity":
            selected = self.lines[0]
            selected.qty += 1
        elif operation == "nested":
            selected = self.lines[0].options
            selected.tags.append("gift")
            selected.attributes["warehouse"]["zone"] = "B"
        elif operation == "iterate":
            for line in self.lines:
                line.qty += 1
        elif operation == "sorted":
            for line in sorted(self.lines, key=lambda line: line.unit_cents):
                line.unit_cents += 25
        elif operation == "slice":
            for line in self.lines[:1]:
                line.qty += 2
        elif operation == "list_alias":
            selected = list(self.lines)
            selected[0].qty += 1
        elif operation == "append":
            self.lines.append(Line("cocoa", 450, 2))
            self.lines[-1].options.tags.append("new")
        elif operation == "dict_values":
            for item in self.inventory.values():
                item["stock"] -= 1
        elif operation == "dict_items":
            for _, item in sorted(self.inventory.items()):
                item["stock"] -= 1
        elif operation == "dict_keys":
            for sku in self.inventory:
                self.inventory[sku]["stock"] -= 1
        elif operation == "inventory_assign":
            self.inventory = {
                sku: {"stock": item["stock"]} for sku, item in self.inventory.items()
            }
        elif operation == "dict_get":
            self.inventory.get("tea")["stock"] -= 2
        elif operation == "setdefault":
            self.inventory.setdefault("cocoa", {"stock": 8})["stock"] -= 1
        elif operation == "dict_update":
            self.inventory["tea"].update({"stock": 3})
        elif operation == "discount":
            self.rules["discount"]["percent"] = 10
        elif operation == "private":
            self._notes.append("packed")
        elif operation == "defaults":
            self.default_matrix[0].append(2)
        elif operation == "reverse":
            self.lines.reverse()
        elif operation == "sort_inplace":
            self.lines.sort(key=lambda line: line.sku)
        elif operation == "replace":
            self.lines[0] = dataclasses.replace(self.lines[0], qty=7)
        elif operation == "pop":
            self.lines.pop()
        elif operation == "slice_replace":
            self.lines[:] = seed_lines()
        elif operation == "cache_between":
            before = self.subtotal
            self.lines[0].qty += 1
            self.receipt = json.dumps({"before": before, "after": self.subtotal})
        elif operation == "read_only":
            before = self.subtotal
            dataclasses.astuple(self.lines[0])
            dataclasses.asdict(self.lines[0])
            sorted(self.lines, key=lambda line: line.sku)
            list(self.lines)
            self.receipt = json.dumps({"before": before, "after": self.subtotal})
        elif operation == "reset":
            self.reset()
        else:
            raise ValueError(operation)


class Fulfillment(Cart):
    """Substate consuming inherited data and cached computed dependencies."""

    service_fee: int = 50
    background_steps: int = 0

    @rx.var(cache=True)
    def invoice(self) -> int:
        """Extend a parent computed var with this substate's fee.

        Returns:
            Final invoiced amount in cents.
        """
        return self.net + self.service_fee

    @rx.event(background=True)
    async def background_pack(self):
        """Mutate inherited nested data and private notes in locked transactions."""
        for _ in range(3):
            await asyncio.sleep(0.15)
            async with self:
                self.lines[0].qty += 1
                self._notes.append("bg")
                self.background_steps += 1


class Review(rx.State):
    """Sibling state reading and modifying the cart through public accessors."""

    @rx.var(cache=True)
    async def quote(self) -> int:
        """Read a derived value across sibling and parent state dependencies.

        Returns:
            The current invoice amount.
        """
        fulfillment = await self.get_state(Fulfillment)
        return fulfillment.invoice

    @rx.event
    async def sibling_add(self):
        """Modify an independently declared sibling through get_state."""
        cart = await self.get_state(Cart)
        cart.lines[0].qty += 3


OPERATIONS = (
    "quantity",
    "nested",
    "iterate",
    "sorted",
    "slice",
    "list_alias",
    "append",
    "dict_values",
    "dict_items",
    "dict_keys",
    "inventory_assign",
    "dict_get",
    "setdefault",
    "dict_update",
    "discount",
    "private",
    "defaults",
    "reverse",
    "sort_inplace",
    "replace",
    "cache_between",
    "read_only",
    "pop",
    "slice_replace",
    "reset",
)


def index() -> rx.Component:
    """Render the dashboard and inspectable correctness projections.

    Returns:
        The order dashboard.
    """
    return rx.vstack(
        rx.heading("Order fulfillment dashboard"),
        rx.hstack(
            rx.text("Subtotal: ", Cart.subtotal, id="subtotal"),
            rx.text(Cart.uncached_subtotal, id="uncached-subtotal"),
            rx.text(Cart.net, id="net"),
            rx.text(Fulfillment.invoice, id="invoice"),
            rx.text(Review.quote, id="quote"),
        ),
        rx.hstack(
            *[
                rx.button(
                    operation, id=f"op-{operation}", on_click=Cart.mutate(operation)
                )
                for operation in OPERATIONS
            ],
            rx.button(
                "Background pack",
                id="op-background",
                on_click=Fulfillment.background_pack,
            ),
            rx.button("Sibling add", id="op-sibling", on_click=Review.sibling_add),
            wrap="wrap",
        ),
        rx.foreach(
            Cart.lines,
            lambda line: rx.text(
                line.sku, " × ", line.qty, " @ ", line.unit_cents, class_name="line-row"
            ),
        ),
        rx.text(Cart.lines.to_string(), id="raw-lines"),
        rx.text(Cart.cached_lines, id="cached-lines"),
        rx.text(Cart.uncached_lines, id="uncached-lines"),
        rx.text(Cart.inventory.to_string(), id="inventory"),
        rx.text(Cart.stock_total, id="stock"),
        rx.text(Cart.ranked.to_string(), id="ranked"),
        rx.text(Cart.rules.to_string(), id="rules"),
        rx.text(Cart.default_matrix.to_string(), id="matrix"),
        rx.text(Cart.notes, id="notes"),
        rx.text(Cart.receipt, id="receipt"),
        rx.text(Fulfillment.background_steps, id="background-steps"),
        padding="2em",
        width="100%",
    )


app = rx.App()
app.add_page(index)
