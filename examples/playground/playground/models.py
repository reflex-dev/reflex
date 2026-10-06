"""The database tables of the playground and their seeding when the app loads."""

import reflex as rx

from playground.seed import product_rows

COLUMNS = ("id", "name", "category", "price_cents", "stock", "rating", "listed_day")


class Product(rx.Model, table=True):
    """A product of the catalog, which the data pages list, filter and edit."""

    name: str
    category: str
    price_cents: int
    stock: int
    # Tenths of a star, 10 to 50.
    rating: int
    listed_day: int


def seed_database():
    """Create the tables and fill an empty product table with the seed rows.

    Runs when ``playground.py`` loads. A table that has rows stays as it is, so
    loading the app again (a hot reload, another worker) inserts nothing. The rows
    go in with one ``executemany`` in one transaction, and ``INSERT OR IGNORE``
    keeps two processes seeding at once from inserting a row twice.
    """
    rx.Model.create_all()
    with rx.session() as session:
        connection = session.connection()
        table = Product.__tablename__
        if connection.exec_driver_sql(f"SELECT 1 FROM {table} LIMIT 1").first():
            return
        placeholders = ", ".join("?" for _ in COLUMNS)
        connection.exec_driver_sql(
            f"INSERT OR IGNORE INTO {table} ({', '.join(COLUMNS)}) VALUES ({placeholders})",
            [tuple(row[column] for column in COLUMNS) for row in product_rows()],
        )
        session.commit()
