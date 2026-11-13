"""Analytics over the whole product table: an expensive computed var and chart data."""

import reflex as rx

from playground.models import Product

TOP = 10


class AnalyticsState(rx.State):
    """Every product, kept on the server, and the aggregates the page shows."""

    min_rating: int = 30
    loaded: bool = False
    # Backend only: the whole table stays on the server.
    _rows: list[dict[str, int | str]] = []

    @rx.event
    def load(self):
        """Read the whole product table: the page's on_load."""
        with rx.session() as session:
            self._rows = [
                {
                    "id": product.id or 0,
                    "name": product.name,
                    "category": product.category,
                    "value": product.price_cents * product.stock,
                    "rating": product.rating,
                }
                for product in session.exec(Product.select()).all()
            ]
        self.loaded = True

    @rx.event
    def set_min_rating(self, value: list[int | float]):
        """Only count products rated at least this many tenths of a star.

        Args:
            value: The slider's values; the first is the minimum.
        """
        self.min_rating = int(value[0])

    @rx.var
    def leaderboard(self) -> list[dict[str, int | str]]:
        """Rank the rated products by stock value: a sort over the whole table.

        Returns:
            The top ten, most valuable first.
        """
        rated = [row for row in self._rows if int(row["rating"]) >= self.min_rating]
        rated.sort(key=lambda row: (-int(row["value"]), int(row["id"])))
        return rated[:TOP]

    @rx.var
    def category_totals(self) -> list[dict[str, int | str]]:
        """Sum the stock value per category, for the bar chart.

        Returns:
            One entry per category, in dollars, sorted by name.
        """
        totals: dict[str, int] = {}
        for row in self._rows:
            if int(row["rating"]) >= self.min_rating:
                category = str(row["category"])
                totals[category] = totals.get(category, 0) + int(row["value"])
        return [
            {"category": category, "value": value // 100}
            for category, value in sorted(totals.items())
        ]

    @rx.var
    def rated_count(self) -> int:
        """Count the products the filter keeps.

        Returns:
            The number of products rated at least ``min_rating``.
        """
        return sum(int(row["rating"]) >= self.min_rating for row in self._rows)
