"""The product table: filter, sort and pagination over the database."""

import reflex as rx

from playground.models import Product

PAGE_SIZE = 20
CATEGORIES = ("all", "books", "garden", "games", "kitchen", "music", "outdoor", "tools")
SORTABLE = ("id", "name", "category", "price_cents", "stock", "rating")


def pages_for(total: int) -> int:
    """Count the pages a number of products fills.

    Args:
        total: The number of products.

    Returns:
        At least one page.
    """
    return max(1, -(-total // PAGE_SIZE))


class DataState(rx.State):
    """One page of products and the controls that pick it."""

    products: list[Product] = []
    total: int = 0
    query: str = ""
    category: str = "all"
    sort_by: str = "id"
    descending: bool = False
    page: int = 0

    @rx.var
    def page_count(self) -> int:
        """Count the pages of the filtered products.

        Returns:
            At least one page.
        """
        return pages_for(self.total)

    @rx.var
    def page_label(self) -> str:
        """Describe the page.

        Returns:
            E.g. ``Page 1 of 100 (2000 products)``.
        """
        return f"Page {self.page + 1} of {self.page_count} ({self.total} products)"

    @rx.event
    def load(self):
        """Query the first page shown: the page's on_load, the first query of a session."""
        self._query()

    def _query(self):
        """Query the current page of the filtered, sorted products."""
        statement = Product.select()
        if self.query:
            statement = statement.where(Product.name.contains(self.query))  # pyright: ignore[reportAttributeAccessIssue]
        if self.category != "all":
            statement = statement.where(Product.category == self.category)
        column = getattr(Product, self.sort_by)
        with rx.session() as session:
            # Product.id is typed as its value; sqlalchemy takes the column.
            ids = statement.with_only_columns(Product.id)  # pyright: ignore[reportCallIssue, reportArgumentType]
            self.total = len(session.exec(ids).all())
            self.page = min(self.page, pages_for(self.total) - 1)
            self.products = list(
                session.exec(
                    statement
                    .order_by(column.desc() if self.descending else column, Product.id)  # pyright: ignore[reportArgumentType]
                    .offset(self.page * PAGE_SIZE)
                    .limit(PAGE_SIZE)
                ).all()
            )

    @rx.event
    def set_query(self, value: str):
        """Filter by name.

        Args:
            value: The text the names must contain.
        """
        self.query = value
        self.page = 0
        self._query()

    @rx.event
    def set_category(self, value: str):
        """Filter by category.

        Args:
            value: A category, or ``all``.
        """
        if value in CATEGORIES:
            self.category = value
            self.page = 0
            self._query()

    @rx.event
    def sort(self, column: str):
        """Sort by a column; sorting by the same column again reverses the order.

        Args:
            column: The column.
        """
        if column not in SORTABLE:
            return
        self.descending = column == self.sort_by and not self.descending
        self.sort_by = column
        self._query()

    @rx.event
    def next_page(self):
        """Show the next page."""
        if self.page + 1 < pages_for(self.total):
            self.page += 1
            self._query()

    @rx.event
    def previous_page(self):
        """Show the previous page."""
        if self.page > 0:
            self.page -= 1
            self._query()

    @rx.event
    def reset_filters(self):
        """Clear the filter and the sort."""
        self.query = ""
        self.category = "all"
        self.sort_by = "id"
        self.descending = False
        self.page = 0
        self._query()
