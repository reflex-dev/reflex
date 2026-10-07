"""Isolate Pydantic state rendering from the new ABC mixin feature."""

import os

import pydantic
import reflex as rx

assert f"/envs/{os.environ['REFLEX_TEST_ENV']}/" in rx.__file__, rx.__file__


class Item(pydantic.BaseModel):
    """A public Pydantic v2 model with a string field."""

    name: str = "tea"


class Inventory(rx.State):
    """Expose a Pydantic model as a public state variable."""

    item: Item = Item()


component = rx.text(Inventory.item.name)
print("COMPONENT_CREATED", component)
