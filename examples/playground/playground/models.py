"""The database tables of the playground and their seeding when the app loads."""

import reflex as rx
from sqlalchemy.schema import CreateTable

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
    """Create the product table and fill it with the seed rows when it is empty.

    Runs when ``playground.py`` loads, in every process that imports the app. A
    table that has rows stays as it is, so loading the app again inserts nothing.
    ``CREATE TABLE IF NOT EXISTS`` and ``INSERT OR IGNORE`` keep processes that
    start at once from creating the table or inserting a row twice, and the rows
    go in with one ``executemany`` in one transaction.
    """
    with rx.session() as session:
        connection = session.connection()
        product_table = Product.__table__  # pyright: ignore[reportAttributeAccessIssue]
        connection.execute(CreateTable(product_table, if_not_exists=True))
        table = Product.__tablename__
        if connection.exec_driver_sql(f"SELECT 1 FROM {table} LIMIT 1").first():
            return
        placeholders = ", ".join("?" for _ in COLUMNS)
        connection.exec_driver_sql(
            f"INSERT OR IGNORE INTO {table} ({', '.join(COLUMNS)}) VALUES ({placeholders})",
            [tuple(row[column] for column in COLUMNS) for row in product_rows()],
        )
        session.commit()
