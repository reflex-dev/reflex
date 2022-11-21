"""Define the base Pynecone class."""
from __future__ import annotations

from typing import Any, Dict, TypeVar

import pydantic

# Typevar to represent any class subclassing Base.
PcType = TypeVar("PcType")


class Base(pydantic.BaseModel):
    """The base class subclassed by all Pynecone classes.

    This class wraps Pydantic and provides common methods such as
    serialization and setting fields.

    Any data structure that needs to be transferred between the
    frontend and backend should subclass this class.
    """

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
        use_enum_values = True

    def json(self) -> str:
        """Convert the object to a json string.

        Returns:
            The object as a json string.
        """
        return self.__config__.json_dumps(self.dict())

    def set(self: PcType, **kwargs) -> PcType:
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
    def get_fields(cls) -> Dict[str, Any]:
        """Get the fields of the object.

        Returns:
            The fields of the object.
        """
        return cls.__fields__

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
