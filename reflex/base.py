"""Define the base Reflex class."""
from __future__ import annotations

from typing import Any

import pydantic
from pydantic.fields import ModelField


class Base(pydantic.BaseModel):
    """The base class subclassed by all Reflex classes.

    This class wraps Pydantic and provides common methods such as
    serialization and setting fields.

    Any data structure that needs to be transferred between the
    frontend and backend should subclass this class.
    """

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
        use_enum_values = True
        extra = "allow"

    def json(self) -> str:
        """Convert the object to a json string.

        Returns:
            The object as a json string.
        """
        return self.__config__.json_dumps(self.dict(), default=list)

    def set(self, **kwargs):
        """Set multiple fields and return the object.

        Args:
            **kwargs: The fields and values to set.

        Returns:
            The object with the fields set.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self

    @classmethod
    def get_fields(cls) -> dict[str, Any]:
        """Get the fields of the object.

        Returns:
            The fields of the object.
        """
        return cls.__fields__

    @classmethod
    def add_field(cls, var: Any, default_value: Any):
        """Add a pydantic field after class definition.

        Used by State.add_var() to correctly handle the new variable.

        Args:
            var: The variable to add a pydantic field for.
            default_value: The default value of the field
        """
        new_field = ModelField.infer(
            name=var.name,
            value=default_value,
            annotation=var.type_,
            class_validators=None,
            config=cls.__config__,
        )
        cls.__fields__.update({var.name: new_field})

    def get_value(self, key: str) -> Any:
        """Get the value of a field.

        Args:
            key: The key of the field.

        Returns:
            The value of the field.
        """
        return self._get_value(
            key,
            to_dict=True,
            by_alias=False,
            include=None,
            exclude=None,
            exclude_unset=False,
            exclude_defaults=False,
            exclude_none=False,
        )
