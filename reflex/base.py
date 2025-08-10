"""Define the base Reflex class."""

from pydantic.v1 import BaseModel


class Base(BaseModel):
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
        from reflex.utils.serializers import serialize

        return self.__config__.json_dumps(
            self.dict(),
            default=serialize,
        )

    def set(self, **kwargs: object):
        """Set multiple fields and return the object.

        Args:
            **kwargs: The fields and values to set.

        Returns:
            The object with the fields set.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self
