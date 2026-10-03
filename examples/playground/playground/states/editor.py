"""The product detail page: an edit form that creates, updates and deletes rows."""

from typing import Any

import reflex as rx

from playground.models import Product
from playground.states import route_arg
from playground.states.data import CATEGORIES


def validate_product(form: dict[str, str]) -> tuple[dict[str, object], dict[str, str]]:
    """Check a submitted product form.

    Args:
        form: The form's fields, as strings.

    Returns:
        The typed values and the errors per field; no errors means valid.
    """
    values: dict[str, object] = {}
    errors: dict[str, str] = {}
    name = form.get("name", "").strip()
    if len(name) < 3:
        errors["name"] = "At least 3 characters."
    values["name"] = name
    category = form.get("category", "")
    if category not in CATEGORIES[1:]:
        errors["category"] = "Pick a category."
    values["category"] = category
    for field, low, high in (
        ("price_cents", 1, 1_000_000),
        ("stock", 0, 100_000),
        ("rating", 10, 50),
    ):
        text = form.get(field, "").strip()
        if not text.isdigit() or not low <= int(text) <= high:
            errors[field] = f"A whole number from {low} to {high}."
        else:
            values[field] = int(text)
    return values, errors


class ProductEditState(rx.State):
    """The product being edited, or a new one, and the form's errors."""

    product: Product | None = None
    errors: rx.Field[dict[str, str]] = rx.field(default_factory=dict)
    saved_count: int = 0

    @rx.var
    def form_values(self) -> dict[str, str]:
        """Fill the form: the product's fields, or a new product's defaults.

        Returns:
            The value of each field, and ``key``, which changes with the product
            so the form starts over.
        """
        product = self.product
        if product is None:
            return {"key": "new", "category": "books", "rating": "30"}
        return {
            "key": str(product.id),
            "name": product.name,
            "category": product.category,
            "price_cents": str(product.price_cents),
            "stock": str(product.stock),
            "rating": str(product.rating),
        }

    @rx.var
    def heading(self) -> str:
        """Title the page.

        Returns:
            ``New product`` or the product's name.
        """
        return self.product.name if self.product is not None else "New product"

    @rx.event
    def load_product(self):
        """Read the product the URL names: the detail page's on_load.

        Returns:
            A toast when no product has that id.
        """
        self.errors = {}
        product_id = route_arg(self.router.url.path)
        with rx.session() as session:
            self.product = (
                session.get(Product, int(product_id)) if product_id.isdigit() else None
            )
        if self.product is None:
            return rx.toast.error(f"No product {product_id}.")
        return None

    @rx.event
    def new_product(self):
        """Start a blank form: the create page's on_load."""
        self.product = None
        self.errors = {}

    @rx.event
    def save(self, form_data: dict[str, Any]):
        """Validate the form, then insert or update the product.

        Args:
            form_data: The submitted fields.

        Returns:
            A toast, and a redirect to a created product's page.
        """
        values, self.errors = validate_product(form_data)
        if self.errors:
            return rx.toast.error("Fix the highlighted fields.")
        with rx.session() as session:
            if self.product is None:
                product = Product(listed_day=0, **values)  # pyright: ignore[reportArgumentType]
            else:
                product = session.get(Product, self.product.id)
                if product is None:
                    return rx.toast.error("The product was deleted.")
                for field, value in values.items():
                    setattr(product, field, value)
            session.add(product)
            session.commit()
            session.refresh(product)
            created = self.product is None
            self.product = product
        self.saved_count += 1
        if created:
            return [
                rx.toast.success("Product created."),
                rx.redirect(f"/data/product/{product.id}"),
            ]
        return rx.toast.success("Product saved.")

    @rx.event
    def delete(self):
        """Delete the product and go back to the table.

        Returns:
            A toast and the redirect.
        """
        if self.product is None:
            return None
        with rx.session() as session:
            if (product := session.get(Product, self.product.id)) is not None:
                session.delete(product)
                session.commit()
        self.product = None
        return [rx.toast.success("Product deleted."), rx.redirect("/data")]
