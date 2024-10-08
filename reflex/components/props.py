"""A class that holds props to be passed or applied to a component."""

from __future__ import annotations

from reflex.base import Base
from reflex.utils import format
from reflex.vars.object import LiteralObjectVar


class PropsBase(Base):
    """Base for a class containing props that can be serialized as a JS object."""

    def json(self) -> str:
        """Convert the object to a json-like string.

        Vars will be unwrapped so they can represent actual JS var names and functions.

        Keys will be converted to camelCase.

        Returns:
            The object as a Javascript Object literal.
        """
        return LiteralObjectVar.create(
            {format.to_camel_case(key): value for key, value in self.dict().items()}
        ).json()

    def dict(self, *args, **kwargs):
        """Convert the object to a dictionary.

        Keys will be converted to camelCase.

        Args:
            *args: Arguments to pass to the parent class.
            **kwargs: Keyword arguments to pass to the parent class.

        Returns:
            The object as a dictionary.
        """
        return {
            format.to_camel_case(key): value
            for key, value in super().dict(*args, **kwargs).items()
        }
