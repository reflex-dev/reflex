"""App with one table holding a datetime column."""

import datetime as dt

import sqlmodel

import reflex as rx


class Reading(sqlmodel.SQLModel, table=True):
    """A sensor reading with a timestamp."""

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    value: float = 0.0
    taken_at: dt.datetime


def index() -> rx.Component:
    return rx.text("db app")


app = rx.App()
app.add_page(index)
