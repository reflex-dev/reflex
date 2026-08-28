"""Test app: pydantic v2 models as state vars (mutations, nesting, foreach, event args)."""

import pydantic

import reflex as rx


class Address(pydantic.BaseModel):
    """Nested model."""

    city: str = "Zurich"
    zip_code: str = "8000"


class User(pydantic.BaseModel):
    """Top-level model with a nested model and a list field."""

    name: str = "Ada"
    age: int = 36
    address: Address = Address()
    tags: list[str] = []


class Item(pydantic.BaseModel):
    """Item for the foreach list."""

    label: str
    qty: int = 1


class State(rx.State):
    """State holding pydantic models."""

    user: rx.Field[User] = rx.field(default_factory=User)
    items: rx.Field[list[Item]] = rx.field(
        default_factory=lambda: [Item(label="apple"), Item(label="pear", qty=2)]
    )
    received: rx.Field[str] = rx.field("")

    @rx.var
    def user_json(self) -> str:
        """Serialize the user model to JSON as a computed var.

        Returns:
            The model dump as a JSON string.
        """
        return self.user.model_dump_json()

    @rx.event
    def bump_age(self):
        """Mutate a top-level model field in place."""
        self.user.age += 1

    @rx.event
    def set_city(self, value: str):
        """Mutate a nested model field in place."""
        self.user.address.city = value

    @rx.event
    def add_tag(self):
        """Append to a list inside a model."""
        self.user.tags.append(f"tag-{len(self.user.tags)}")

    @rx.event
    def add_item(self):
        """Append a model instance to a list var."""
        self.items.append(Item(label=f"item-{len(self.items)}"))

    @rx.event
    def receive_user(self, u: User):
        """Event handler with a pydantic-model-hinted arg (dict from frontend).

        Args:
            u: The user model validated from the frontend dict payload.
        """
        self.received = f"{u.name}:{u.age}:{u.address.city}:{type(u).__name__}"


def item_row(it: Item) -> rx.Component:
    """Render one item row.

    Args:
        it: The item var.

    Returns:
        A row component.
    """
    return rx.hstack(
        rx.text(it.label, class_name="item-label"),
        rx.text(it.qty, class_name="item-qty"),
    )


def index() -> rx.Component:
    """Index page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("pydantic v2 app", id="title"),
        rx.text(State.user.name, id="user-name"),
        rx.text(State.user.age, id="user-age"),
        rx.text(State.user.address.city, id="user-city"),
        rx.text(State.user.tags.join(","), id="user-tags"),
        rx.text(State.user_json, id="user-json"),
        rx.text(State.received, id="received"),
        rx.input(id="city-input", placeholder="city", on_change=State.set_city),
        rx.button("bump age", id="bump-age", on_click=State.bump_age),
        rx.button("add tag", id="add-tag", on_click=State.add_tag),
        rx.button("add item", id="add-item", on_click=State.add_item),
        rx.button(
            "send user dict",
            id="send-user",
            on_click=State.receive_user(
                {
                    "name": "Grace",
                    "age": 45,
                    "address": {"city": "Paris", "zip_code": "75001"},
                    "tags": [],
                }
            ),
        ),
        rx.vstack(rx.foreach(State.items, item_row), id="item-list"),
    )


app = rx.App()
app.add_page(index)
