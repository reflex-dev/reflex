"""Define the base Reflex class."""

from importlib.util import find_spec

if find_spec("pydantic") and find_spec("pydantic.v1"):
    from pydantic.v1 import BaseModel

    from reflex.utils.compat import ModelMetaclassLazyAnnotations

    class Base(BaseModel, metaclass=ModelMetaclassLazyAnnotations):
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

        def __init_subclass__(cls):
            """Warn that rx.Base is deprecated."""
            from reflex.utils import console

            console.deprecate(
                feature_name="rx.Base",
                reason=f"{cls!r} is subclassing rx.Base. You can subclass from `pydantic.BaseModel` directly instead or use dataclasses if possible.",
                deprecation_version="0.8.15",
                removal_version="0.9.0",
            )
            super().__init_subclass__()

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

else:

    class PydanticNotFoundFallback:
        """Fallback base class for environments without Pydantic."""

        def __init__(self, *args, **kwargs):
            """Initialize the base class.

            Args:
                *args: Positional arguments.
                **kwargs: Keyword arguments.

            Raises:
                ImportError: As Pydantic is not installed.
            """
            msg = (
                "Pydantic is not installed. Please install it to use rx.Base."
                "You can install it with `pip install pydantic`."
            )
            raise ImportError(msg)

    Base = PydanticNotFoundFallback  # pyright: ignore[reportAssignmentType]
