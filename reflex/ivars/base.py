"""Collection of base classes."""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import dis
import functools
import inspect
import json
import sys
import warnings
from types import CodeType, FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    overload,
)

from typing_extensions import ParamSpec, get_origin, get_type_hints, override

from reflex import constants
from reflex.base import Base
from reflex.constants.colors import Color
from reflex.utils import console, imports, serializers, types
from reflex.utils.exceptions import VarDependencyError, VarTypeError, VarValueError
from reflex.utils.format import format_state_name
from reflex.vars import (
    ComputedVar,
    ImmutableVarData,
    Var,
    VarData,
    _decode_var_immutable,
    _extract_var_data,
    _global_vars,
)

if TYPE_CHECKING:
    from reflex.state import BaseState

    from .function import FunctionVar, ToFunctionOperation
    from .number import (
        BooleanVar,
        NumberVar,
        ToBooleanVarOperation,
        ToNumberVarOperation,
    )
    from .object import ObjectVar, ToObjectOperation
    from .sequence import ArrayVar, StringVar, ToArrayOperation, ToStringOperation


VAR_TYPE = TypeVar("VAR_TYPE")


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ImmutableVar(Var, Generic[VAR_TYPE]):
    """Base class for immutable vars."""

    # The name of the var.
    _var_name: str = dataclasses.field()

    # The type of the var.
    _var_type: types.GenericType = dataclasses.field(default=Any)

    # Extra metadata associated with the Var
    _var_data: Optional[ImmutableVarData] = dataclasses.field(default=None)

    def __str__(self) -> str:
        """String representation of the var. Guaranteed to be a valid Javascript expression.

        Returns:
            The name of the var.
        """
        return self._var_name

    @property
    def _var_is_local(self) -> bool:
        """Whether this is a local javascript variable.

        Returns:
            False
        """
        return False

    @property
    def _var_is_string(self) -> bool:
        """Whether the var is a string literal.

        Returns:
            False
        """
        return False

    @property
    def _var_full_name_needs_state_prefix(self) -> bool:
        """Whether the full name of the var needs a _var_state prefix.

        Returns:
            False
        """
        return False

    def __post_init__(self):
        """Post-initialize the var."""
        # Decode any inline Var markup and apply it to the instance
        _var_data, _var_name = _decode_var_immutable(self._var_name)

        if _var_data or _var_name != self._var_name:
            self.__init__(
                _var_name=_var_name,
                _var_type=self._var_type,
                _var_data=ImmutableVarData.merge(self._var_data, _var_data),
            )

    def __hash__(self) -> int:
        """Define a hash function for the var.

        Returns:
            The hash of the var.
        """
        return hash((self._var_name, self._var_type, self._var_data))

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._var_data

    def _replace(self, merge_var_data=None, **kwargs: Any):
        """Make a copy of this Var with updated fields.

        Args:
            merge_var_data: VarData to merge into the existing VarData.
            **kwargs: Var fields to update.

        Returns:
            A new ImmutableVar with the updated fields overwriting the corresponding fields in this Var.

        Raises:
            TypeError: If _var_is_local, _var_is_string, or _var_full_name_needs_state_prefix is not None.
        """
        if kwargs.get("_var_is_local", False) is not False:
            raise TypeError(
                "The _var_is_local argument is not supported for ImmutableVar."
            )

        if kwargs.get("_var_is_string", False) is not False:
            raise TypeError(
                "The _var_is_string argument is not supported for ImmutableVar."
            )

        if kwargs.get("_var_full_name_needs_state_prefix", False) is not False:
            raise TypeError(
                "The _var_full_name_needs_state_prefix argument is not supported for ImmutableVar."
            )

        field_values = dict(
            _var_name=kwargs.pop("_var_name", self._var_name),
            _var_type=kwargs.pop("_var_type", self._var_type),
            _var_data=ImmutableVarData.merge(
                kwargs.get("_var_data", self._var_data), merge_var_data
            ),
        )
        return dataclasses.replace(self, **field_values)

    @classmethod
    def create(
        cls,
        value: Any,
        _var_is_local: bool | None = None,
        _var_is_string: bool | None = None,
        _var_data: VarData | None = None,
    ) -> ImmutableVar | Var | None:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_is_local: Whether the var is local. Deprecated.
            _var_is_string: Whether the var is a string literal. Deprecated.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.

        Raises:
            VarTypeError: If the value is JSON-unserializable.
            TypeError: If _var_is_local or _var_is_string is not None.
        """
        if _var_is_local is not None:
            raise TypeError(
                "The _var_is_local argument is not supported for ImmutableVar."
            )

        if _var_is_string is not None:
            raise TypeError(
                "The _var_is_string argument is not supported for ImmutableVar."
            )

        from reflex.utils import format

        # Check for none values.
        if value is None:
            return None

        # If the value is already a var, do nothing.
        if isinstance(value, Var):
            return value

        # Try to pull the imports and hooks from contained values.
        if not isinstance(value, str):
            _var_data = VarData.merge(*_extract_var_data(value), _var_data)

        # Try to serialize the value.
        type_ = type(value)
        if type_ in types.JSONType:
            name = value
        else:
            name, _serialized_type = serializers.serialize(value, get_type=True)
        if name is None:
            raise VarTypeError(
                f"No JSON serializer found for var {value} of type {type_}."
            )
        name = name if isinstance(name, str) else format.json_dumps(name)

        return cls(
            _var_name=name,
            _var_type=type_,
            _var_data=(
                ImmutableVarData(
                    state=_var_data.state,
                    imports=_var_data.imports,
                    hooks=_var_data.hooks,
                )
                if _var_data
                else None
            ),
        )

    @classmethod
    def create_safe(
        cls,
        value: Any,
        _var_is_local: bool | None = None,
        _var_is_string: bool | None = None,
        _var_data: VarData | None = None,
    ) -> Var | ImmutableVar:
        """Create a var from a value, asserting that it is not None.

        Args:
            value: The value to create the var from.
            _var_is_local: Whether the var is local. Deprecated.
            _var_is_string: Whether the var is a string literal. Deprecated.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        var = cls.create(
            value,
            _var_is_local=_var_is_local,
            _var_is_string=_var_is_string,
            _var_data=_var_data,
        )
        assert var is not None
        return var

    def __format__(self, format_spec: str) -> str:
        """Format the var into a Javascript equivalent to an f-string.

        Args:
            format_spec: The format specifier (Ignored for now).

        Returns:
            The formatted var.
        """
        hashed_var = hash(self)

        _global_vars[hashed_var] = self

        # Encode the _var_data into the formatted output for tracking purposes.
        return f"{constants.REFLEX_VAR_OPENING_TAG}{hashed_var}{constants.REFLEX_VAR_CLOSING_TAG}{self._var_name}"

    @overload
    def to(
        self, output: Type[NumberVar], var_type: type[int] | type[float] = float
    ) -> ToNumberVarOperation: ...

    @overload
    def to(self, output: Type[BooleanVar]) -> ToBooleanVarOperation: ...

    @overload
    def to(
        self,
        output: Type[ArrayVar],
        var_type: type[list] | type[tuple] | type[set] = list,
    ) -> ToArrayOperation: ...

    @overload
    def to(self, output: Type[StringVar]) -> ToStringOperation: ...

    @overload
    def to(
        self, output: Type[ObjectVar], var_type: types.GenericType = dict
    ) -> ToObjectOperation: ...

    @overload
    def to(
        self, output: Type[FunctionVar], var_type: Type[Callable] = Callable
    ) -> ToFunctionOperation: ...

    @overload
    def to(
        self,
        output: Type[OUTPUT] | types.GenericType,
        var_type: types.GenericType | None = None,
    ) -> OUTPUT: ...

    def to(
        self,
        output: Type[OUTPUT] | types.GenericType,
        var_type: types.GenericType | None = None,
    ) -> Var:
        """Convert the var to a different type.

        Args:
            output: The output type.
            var_type: The type of the var.

        Raises:
            TypeError: If the var_type is not a supported type for the output.

        Returns:
            The converted var.
        """
        from .function import FunctionVar, ToFunctionOperation
        from .number import (
            BooleanVar,
            NumberVar,
            ToBooleanVarOperation,
            ToNumberVarOperation,
        )
        from .object import ObjectVar, ToObjectOperation
        from .sequence import ArrayVar, StringVar, ToArrayOperation, ToStringOperation

        fixed_type = (
            var_type
            if var_type is None or inspect.isclass(var_type)
            else get_origin(var_type)
        )

        fixed_output_type = output if inspect.isclass(output) else get_origin(output)

        if fixed_output_type is dict:
            return self.to(ObjectVar, output)
        if fixed_output_type in (list, tuple, set):
            return self.to(ArrayVar, output)
        if fixed_output_type in (int, float):
            return self.to(NumberVar, output)
        if fixed_output_type is str:
            return self.to(StringVar, output)
        if fixed_output_type is bool:
            return self.to(BooleanVar, output)

        if issubclass(output, NumberVar):
            if fixed_type is not None and not issubclass(fixed_type, (int, float)):
                raise TypeError(
                    f"Unsupported type {var_type} for NumberVar. Must be int or float."
                )
            return ToNumberVarOperation.create(self, var_type or float)

        if issubclass(output, BooleanVar):
            return ToBooleanVarOperation.create(self)

        if issubclass(output, ArrayVar):
            if fixed_type is not None and not issubclass(
                fixed_type, (list, tuple, set)
            ):
                raise TypeError(
                    f"Unsupported type {var_type} for ArrayVar. Must be list, tuple, or set."
                )
            return ToArrayOperation.create(self, var_type or list)

        if issubclass(output, StringVar):
            return ToStringOperation.create(self)

        if issubclass(output, (ObjectVar, Base)):
            return ToObjectOperation.create(self, var_type or dict)

        if issubclass(output, FunctionVar):
            # if fixed_type is not None and not issubclass(fixed_type, Callable):
            #     raise TypeError(
            #         f"Unsupported type {var_type} for FunctionVar. Must be Callable."
            #     )
            return ToFunctionOperation.create(self, var_type or Callable)

        if not issubclass(output, Var) and var_type is None:
            return dataclasses.replace(
                self,
                _var_type=output,
            )

        return dataclasses.replace(
            self,
            _var_type=var_type,
        )

    def guess_type(self) -> ImmutableVar:
        """Guesses the type of the variable based on its `_var_type` attribute.

        Returns:
            ImmutableVar: The guessed type of the variable.

        Raises:
            TypeError: If the type is not supported for guessing.
        """
        from .number import NumberVar
        from .object import ObjectVar
        from .sequence import ArrayVar, StringVar

        if self._var_type is Any:
            return self

        var_type = self._var_type
        if types.is_optional(var_type):
            var_type = types.get_args(var_type)[0]

        fixed_type = var_type if inspect.isclass(var_type) else get_origin(var_type)

        if fixed_type is Union:
            return self

        if not inspect.isclass(fixed_type):
            raise TypeError(f"Unsupported type {var_type} for guess_type.")

        if issubclass(fixed_type, (int, float)):
            return self.to(NumberVar, self._var_type)
        if issubclass(fixed_type, dict):
            return self.to(ObjectVar, self._var_type)
        if issubclass(fixed_type, (list, tuple, set)):
            return self.to(ArrayVar, self._var_type)
        if issubclass(fixed_type, str):
            return self.to(StringVar)
        if issubclass(fixed_type, Base):
            return self.to(ObjectVar, self._var_type)
        return self

    def get_default_value(self) -> Any:
        """Get the default value of the var.

        Returns:
            The default value of the var.

        Raises:
            ImportError: If the var is a dataframe and pandas is not installed.
        """
        if types.is_optional(self._var_type):
            return None

        type_ = (
            get_origin(self._var_type)
            if types.is_generic_alias(self._var_type)
            else self._var_type
        )
        if type_ is Literal:
            args = get_args(self._var_type)
            return args[0] if args else None
        if issubclass(type_, str):
            return ""
        if issubclass(type_, types.get_args(Union[int, float])):
            return 0
        if issubclass(type_, bool):
            return False
        if issubclass(type_, list):
            return []
        if issubclass(type_, dict):
            return {}
        if issubclass(type_, tuple):
            return ()
        if types.is_dataframe(type_):
            try:
                import pandas as pd

                return pd.DataFrame()
            except ImportError as e:
                raise ImportError(
                    "Please install pandas to use dataframes in your app."
                ) from e
        return set() if issubclass(type_, set) else None

    def get_setter_name(self, include_state: bool = True) -> str:
        """Get the name of the var's generated setter function.

        Args:
            include_state: Whether to include the state name in the setter name.

        Returns:
            The name of the setter function.
        """
        var_name_parts = self._var_name.split(".")
        setter = constants.SETTER_PREFIX + var_name_parts[-1]
        if self._var_data is None:
            return setter
        if not include_state or self._var_data.state == "":
            return setter
        return ".".join((self._var_data.state, setter))

    def get_setter(self) -> Callable[[BaseState, Any], None]:
        """Get the var's setter function.

        Returns:
            A function that that creates a setter for the var.
        """
        actual_name = self._var_name.split(".")[-1]

        def setter(state: BaseState, value: Any):
            """Get the setter for the var.

            Args:
                state: The state within which we add the setter function.
                value: The value to set.
            """
            if self._var_type in [int, float]:
                try:
                    value = self._var_type(value)
                    setattr(state, actual_name, value)
                except ValueError:
                    console.debug(
                        f"{type(state).__name__}.{self._var_name}: Failed conversion of {value} to '{self._var_type.__name__}'. Value not set.",
                    )
            else:
                setattr(state, actual_name, value)

        setter.__qualname__ = self.get_setter_name()

        return setter

    def __eq__(self, other: Var | Any) -> BooleanVar:
        """Check if the current variable is equal to the given variable.

        Args:
            other (Var | Any): The variable to compare with.

        Returns:
            BooleanVar: A BooleanVar object representing the result of the equality check.
        """
        from .number import EqualOperation

        return EqualOperation.create(self, other)

    def __ne__(self, other: Var | Any) -> BooleanVar:
        """Check if the current object is not equal to the given object.

        Parameters:
            other (Var | Any): The object to compare with.

        Returns:
            BooleanVar: A BooleanVar object representing the result of the comparison.
        """
        from .number import EqualOperation

        return ~EqualOperation.create(self, other)

    def __gt__(self, other: Var | Any) -> BooleanVar:
        """Compare the current instance with another variable and return a BooleanVar representing the result of the greater than operation.

        Args:
            other (Var | Any): The variable to compare with.

        Returns:
            BooleanVar: A BooleanVar representing the result of the greater than operation.
        """
        from .number import GreaterThanOperation

        return GreaterThanOperation.create(self, other)

    def __ge__(self, other: Var | Any) -> BooleanVar:
        """Check if the value of this variable is greater than or equal to the value of another variable or object.

        Args:
            other (Var | Any): The variable or object to compare with.

        Returns:
            BooleanVar: A BooleanVar object representing the result of the comparison.
        """
        from .number import GreaterThanOrEqualOperation

        return GreaterThanOrEqualOperation.create(self, other)

    def __lt__(self, other: Var | Any) -> BooleanVar:
        """Compare the current instance with another variable using the less than (<) operator.

        Args:
            other: The variable to compare with.

        Returns:
            A `BooleanVar` object representing the result of the comparison.
        """
        from .number import LessThanOperation

        return LessThanOperation.create(self, other)

    def __le__(self, other: Var | Any) -> BooleanVar:
        """Compare if the current instance is less than or equal to the given value.

        Args:
            other: The value to compare with.

        Returns:
            A BooleanVar object representing the result of the comparison.
        """
        from .number import LessThanOrEqualOperation

        return LessThanOrEqualOperation.create(self, other)

    def bool(self) -> BooleanVar:
        """Convert the var to a boolean.

        Returns:
            The boolean var.
        """
        from .number import ToBooleanVarOperation

        return ToBooleanVarOperation.create(self)

    def __and__(self, other: Var | Any) -> ImmutableVar:
        """Perform a logical AND operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical AND operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical AND operation.
        """
        return AndOperation.create(self, other)

    def __rand__(self, other: Var | Any) -> ImmutableVar:
        """Perform a logical AND operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical AND operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical AND operation.
        """
        return AndOperation.create(other, self)

    def __or__(self, other: Var | Any) -> ImmutableVar:
        """Perform a logical OR operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical OR operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical OR operation.
        """
        return OrOperation.create(self, other)

    def __ror__(self, other: Var | Any) -> ImmutableVar:
        """Perform a logical OR operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical OR operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical OR operation.
        """
        return OrOperation.create(other, self)

    def __invert__(self) -> BooleanVar:
        """Perform a logical NOT operation on the current instance.

        Returns:
            A `BooleanVar` object representing the result of the logical NOT operation.
        """
        from .number import BooleanNotOperation

        return BooleanNotOperation.create(self.bool())

    def to_string(self) -> ImmutableVar:
        """Convert the var to a string.

        Returns:
            The string var.
        """
        from .function import JSON_STRINGIFY
        from .sequence import StringVar

        return JSON_STRINGIFY.call(self).to(StringVar)

    def as_ref(self) -> ImmutableVar:
        """Get a reference to the var.

        Returns:
            The reference to the var.
        """
        from .object import ObjectVar

        refs = ImmutableVar(
            _var_name="refs",
            _var_data=ImmutableVarData(
                imports={
                    f"/{constants.Dirs.STATE_PATH}": [imports.ImportVar(tag="refs")]
                }
            ),
        ).to(ObjectVar)
        return refs[self]

    def _type(self) -> StringVar:
        """Returns the type of the object.

        This method uses the `typeof` function from the `FunctionStringVar` class
        to determine the type of the object.

        Returns:
            StringVar: A string variable representing the type of the object.
        """
        from .function import FunctionStringVar
        from .sequence import StringVar

        type_of = FunctionStringVar("typeof")
        return type_of.call(self).to(StringVar)


OUTPUT = TypeVar("OUTPUT", bound=ImmutableVar)


class LiteralVar(ImmutableVar):
    """Base class for immutable literal vars."""

    @classmethod
    def create(
        cls,
        value: Any,
        _var_data: VarData | None = None,
    ) -> Var:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.

        Raises:
            TypeError: If the value is not a supported type for LiteralVar.
        """
        if isinstance(value, Var):
            if _var_data is None:
                return value
            return value._replace(merge_var_data=_var_data)

        if value is None:
            return ImmutableVar.create_safe("null", _var_data=_var_data)

        from reflex.event import EventChain, EventSpec
        from reflex.utils.format import get_event_handler_parts

        from .function import ArgsFunctionOperation, FunctionStringVar
        from .object import LiteralObjectVar

        if isinstance(value, EventSpec):
            event_name = LiteralVar.create(
                ".".join(get_event_handler_parts(value.handler))
            )
            event_args = LiteralVar.create(
                {str(name): value for name, value in value.args}
            )
            event_client_name = LiteralVar.create(value.client_handler_name)
            return FunctionStringVar("Event").call(
                event_name,
                event_args,
                *([event_client_name] if value.client_handler_name else []),
            )

        if isinstance(value, EventChain):
            sig = inspect.signature(value.args_spec)  # type: ignore
            if sig.parameters:
                arg_def = tuple((f"_{p}" for p in sig.parameters))
                arg_def_expr = LiteralVar.create(
                    [ImmutableVar.create_safe(arg) for arg in arg_def]
                )
            else:
                # add a default argument for addEvents if none were specified in value.args_spec
                # used to trigger the preventDefault() on the event.
                arg_def = ("...args",)
                arg_def_expr = ImmutableVar.create_safe("args")

            return ArgsFunctionOperation.create(
                arg_def,
                FunctionStringVar.create("addEvents").call(
                    LiteralVar.create(
                        [LiteralVar.create(event) for event in value.events]
                    ),
                    arg_def_expr,
                    LiteralVar.create(value.event_actions),
                ),
            )

        try:
            from plotly.graph_objects import Figure, layout
            from plotly.io import to_json

            if isinstance(value, Figure):
                return LiteralObjectVar.create(
                    json.loads(str(to_json(value))),
                    _var_type=Figure,
                    _var_data=_var_data,
                )

            if isinstance(value, layout.Template):
                return LiteralObjectVar.create(
                    {
                        "data": json.loads(str(to_json(value.data))),
                        "layout": json.loads(str(to_json(value.layout))),
                    },
                    _var_type=layout.Template,
                    _var_data=_var_data,
                )
        except ImportError:
            pass

        from .sequence import LiteralArrayVar, LiteralStringVar

        try:
            import base64
            import io

            from PIL.Image import MIME
            from PIL.Image import Image as Img

            if isinstance(value, Img):
                with io.BytesIO() as buffer:
                    value.save(buffer, format=getattr(value, "format", None) or "PNG")
                    try:
                        # Newer method to get the mime type, but does not always work.
                        mimetype = value.get_format_mimetype()
                    except AttributeError:
                        try:
                            # Fallback method
                            mimetype = MIME[value.format]
                        except KeyError:
                            # Unknown mime_type: warn and return image/png and hope the browser can sort it out.
                            warnings.warn(  # noqa: B028
                                f"Unknown mime type for {value} {value.format}. Defaulting to image/png"
                            )
                            mimetype = "image/png"
                    return LiteralStringVar.create(
                        f"data:{mimetype};base64,{base64.b64encode(buffer.getvalue()).decode()}",
                        _var_data=_var_data,
                    )
        except ImportError:
            pass

        if isinstance(value, Base):
            return LiteralObjectVar.create(
                {k: (None if callable(v) else v) for k, v in value.dict().items()},
                _var_type=type(value),
                _var_data=_var_data,
            )

        if isinstance(value, dict):
            return LiteralObjectVar.create(value, _var_data=_var_data)

        if isinstance(value, str):
            return LiteralStringVar.create(value, _var_data=_var_data)

        if isinstance(value, Color):
            return LiteralStringVar.create(f"{value}", _var_data=_var_data)

        from .number import LiteralBooleanVar, LiteralNumberVar

        if isinstance(value, bool):
            return LiteralBooleanVar.create(value, _var_data=_var_data)

        if isinstance(value, (int, float)):
            return LiteralNumberVar.create(value, _var_data=_var_data)

        if isinstance(value, (list, tuple, set)):
            return LiteralArrayVar.create(value, _var_data=_var_data)

        raise TypeError(
            f"Unsupported type {type(value)} for LiteralVar. Tried to create a LiteralVar from {value}."
        )

    def __post_init__(self):
        """Post-initialize the var."""

    def json(self) -> str:
        """Serialize the var to a JSON string.

        Raises:
            NotImplementedError: If the method is not implemented.
        """
        raise NotImplementedError(
            "LiteralVar subclasses must implement the json method."
        )


P = ParamSpec("P")
T = TypeVar("T", bound=ImmutableVar)


def var_operation(*, output: Type[T]) -> Callable[[Callable[P, str]], Callable[P, T]]:
    """Decorator for creating a var operation.

    Example:
    ```python
    @var_operation(output=NumberVar)
    def add(a: NumberVar, b: NumberVar):
        return f"({a} + {b})"
    ```

    Args:
        output: The output type of the operation.

    Returns:
        The decorator.
    """

    def decorator(func: Callable[P, str], output=output):
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            args_vars = [
                LiteralVar.create(arg) if not isinstance(arg, Var) else arg
                for arg in args
            ]
            kwargs_vars = {
                key: LiteralVar.create(value) if not isinstance(value, Var) else value
                for key, value in kwargs.items()
            }
            return output(
                _var_name=func(*args_vars, **kwargs_vars),  # type: ignore
                _var_data=VarData.merge(
                    *[arg._get_all_var_data() for arg in args if isinstance(arg, Var)],
                    *[
                        arg._get_all_var_data()
                        for arg in kwargs.values()
                        if isinstance(arg, Var)
                    ],
                ),
            )

        return wrapper

    return decorator


def unionize(*args: Type) -> Type:
    """Unionize the types.

    Args:
        args: The types to unionize.

    Returns:
        The unionized types.
    """
    if not args:
        return Any
    first, *rest = args
    if not rest:
        return first
    return Union[first, unionize(*rest)]


def figure_out_type(value: Any) -> types.GenericType:
    """Figure out the type of the value.

    Args:
        value: The value to figure out the type of.

    Returns:
        The type of the value.
    """
    if isinstance(value, list):
        return List[unionize(*(figure_out_type(v) for v in value))]
    if isinstance(value, set):
        return Set[unionize(*(figure_out_type(v) for v in value))]
    if isinstance(value, tuple):
        return Tuple[unionize(*(figure_out_type(v) for v in value)), ...]
    if isinstance(value, dict):
        return Dict[
            unionize(*(figure_out_type(k) for k in value)),
            unionize(*(figure_out_type(v) for v in value.values())),
        ]
    if isinstance(value, Var):
        return value._var_type
    return type(value)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class AndOperation(ImmutableVar):
    """Class for the logical AND operation."""

    # The first var.
    _var1: Var = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    # The second var.
    _var2: Var = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    def __post_init__(self):
        """Post-initialize the AndOperation."""
        object.__delattr__(self, "_var_name")

    @functools.cached_property
    def _cached_var_name(self) -> str:
        """Get the cached var name.

        Returns:
            The cached var name.
        """
        return f"({str(self._var1)} && {str(self._var2)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute.
        """
        if name == "_var_name":
            return self._cached_var_name
        return getattr(super(type(self), self), name)

    @functools.cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get the cached VarData.

        Returns:
            The cached VarData.
        """
        return ImmutableVarData.merge(
            self._var1._get_all_var_data(),
            self._var2._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __hash__(self) -> int:
        """Calculates the hash value of the object.

        Returns:
            int: The hash value of the object.
        """
        return hash((self.__class__.__name__, self._var1, self._var2))

    @classmethod
    def create(
        cls, var1: Var | Any, var2: Var | Any, _var_data: VarData | None = None
    ) -> AndOperation:
        """Create an AndOperation.

        Args:
            var1: The first var.
            var2: The second var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The AndOperation.
        """
        var1, var2 = map(LiteralVar.create, (var1, var2))
        return AndOperation(
            _var_name="",
            _var_type=unionize(var1._var_type, var2._var_type),
            _var_data=ImmutableVarData.merge(_var_data),
            _var1=var1,
            _var2=var2,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class OrOperation(ImmutableVar):
    """Class for the logical OR operation."""

    # The first var.
    _var1: Var = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    # The second var.
    _var2: Var = dataclasses.field(default_factory=lambda: LiteralVar.create(None))

    def __post_init__(self):
        """Post-initialize the OrOperation."""
        object.__delattr__(self, "_var_name")

    @functools.cached_property
    def _cached_var_name(self) -> str:
        """Get the cached var name.

        Returns:
            The cached var name.
        """
        return f"({str(self._var1)} || {str(self._var2)})"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute.
        """
        if name == "_var_name":
            return self._cached_var_name
        return getattr(super(type(self), self), name)

    @functools.cached_property
    def _cached_get_all_var_data(self) -> ImmutableVarData | None:
        """Get the cached VarData.

        Returns:
            The cached VarData.
        """
        return ImmutableVarData.merge(
            self._var1._get_all_var_data(),
            self._var2._get_all_var_data(),
            self._var_data,
        )

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    def __hash__(self) -> int:
        """Calculates the hash value for the object.

        Returns:
            int: The hash value of the object.
        """
        return hash((self.__class__.__name__, self._var1, self._var2))

    @classmethod
    def create(
        cls, var1: Var | Any, var2: Var | Any, _var_data: VarData | None = None
    ) -> OrOperation:
        """Create an OrOperation.

        Args:
            var1: The first var.
            var2: The second var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The OrOperation.
        """
        var1, var2 = map(LiteralVar.create, (var1, var2))
        return OrOperation(
            _var_name="",
            _var_type=unionize(var1._var_type, var2._var_type),
            _var_data=ImmutableVarData.merge(_var_data),
            _var1=var1,
            _var2=var2,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ImmutableCallableVar(ImmutableVar):
    """Decorate a Var-returning function to act as both a Var and a function.

    This is used as a compatibility shim for replacing Var objects in the
    API with functions that return a family of Var.
    """

    fn: Callable[..., Var] = dataclasses.field(
        default_factory=lambda: lambda: ImmutableVar(_var_name="undefined")
    )
    original_var: Var = dataclasses.field(
        default_factory=lambda: ImmutableVar(_var_name="undefined")
    )

    def __init__(self, fn: Callable[..., Var]):
        """Initialize a CallableVar.

        Args:
            fn: The function to decorate (must return Var)
        """
        original_var = fn()
        super(ImmutableCallableVar, self).__init__(
            _var_name=original_var._var_name,
            _var_type=original_var._var_type,
            _var_data=ImmutableVarData.merge(original_var._var_data),
        )
        object.__setattr__(self, "fn", fn)
        object.__setattr__(self, "original_var", original_var)

    def __call__(self, *args, **kwargs) -> Var:
        """Call the decorated function.

        Args:
            *args: The args to pass to the function.
            **kwargs: The kwargs to pass to the function.

        Returns:
            The Var returned from calling the function.
        """
        return self.fn(*args, **kwargs)

    def __hash__(self) -> int:
        """Calculate the hash of the object.

        Returns:
            The hash of the object.
        """
        return hash((self.__class__.__name__, self.original_var))


RETURN_TYPE = TypeVar("RETURN_TYPE")

DICT_KEY = TypeVar("DICT_KEY")
DICT_VAL = TypeVar("DICT_VAL")

LIST_INSIDE = TypeVar("LIST_INSIDE")


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    **{"slots": True} if sys.version_info >= (3, 10) else {},
)
class ImmutableComputedVar(ImmutableVar[RETURN_TYPE]):
    """A field with computed getters."""

    # Whether to track dependencies and cache computed values
    _cache: bool = dataclasses.field(default=False)

    # Whether the computed var is a backend var
    _backend: bool = dataclasses.field(default=False)

    # The initial value of the computed var
    _initial_value: RETURN_TYPE | types.Unset = dataclasses.field(default=types.Unset())

    # Explicit var dependencies to track
    _static_deps: set[str] = dataclasses.field(default_factory=set)

    # Whether var dependencies should be auto-determined
    _auto_deps: bool = dataclasses.field(default=True)

    # Interval at which the computed var should be updated
    _update_interval: Optional[datetime.timedelta] = dataclasses.field(default=None)

    _fget: Callable[[BaseState], RETURN_TYPE] = dataclasses.field(
        default_factory=lambda: lambda _: None
    )  # type: ignore

    def __init__(
        self,
        fget: Callable[[BASE_STATE], RETURN_TYPE],
        initial_value: RETURN_TYPE | types.Unset = types.Unset(),
        cache: bool = False,
        deps: Optional[List[Union[str, Var]]] = None,
        auto_deps: bool = True,
        interval: Optional[Union[int, datetime.timedelta]] = None,
        backend: bool | None = None,
        **kwargs,
    ):
        """Initialize a ComputedVar.

        Args:
            fget: The getter function.
            initial_value: The initial value of the computed var.
            cache: Whether to cache the computed value.
            deps: Explicit var dependencies to track.
            auto_deps: Whether var dependencies should be auto-determined.
            interval: Interval at which the computed var should be updated.
            backend: Whether the computed var is a backend var.
            **kwargs: additional attributes to set on the instance

        Raises:
            TypeError: If the computed var dependencies are not Var instances or var names.
        """
        hints = get_type_hints(fget)
        hint = hints.get("return", Any)

        kwargs["_var_name"] = kwargs.pop("_var_name", fget.__name__)
        kwargs["_var_type"] = kwargs.pop("_var_type", hint)

        super(ImmutableComputedVar, self).__init__(
            _var_name=kwargs.pop("_var_name"),
            _var_type=kwargs.pop("_var_type"),
            _var_data=ImmutableVarData.merge(kwargs.pop("_var_data", None)),
        )

        if backend is None:
            backend = fget.__name__.startswith("_")

        object.__setattr__(self, "_backend", backend)
        object.__setattr__(self, "_initial_value", initial_value)
        object.__setattr__(self, "_cache", cache)

        if isinstance(interval, int):
            interval = datetime.timedelta(seconds=interval)

        object.__setattr__(self, "_update_interval", interval)

        if deps is None:
            deps = []
        else:
            for dep in deps:
                if isinstance(dep, Var):
                    continue
                if isinstance(dep, str) and dep != "":
                    continue
                raise TypeError(
                    "ComputedVar dependencies must be Var instances or var names (non-empty strings)."
                )
        object.__setattr__(
            self,
            "_static_deps",
            {dep._var_name if isinstance(dep, Var) else dep for dep in deps},
        )
        object.__setattr__(self, "_auto_deps", auto_deps)

        object.__setattr__(self, "_fget", fget)

    @override
    def _replace(self, merge_var_data=None, **kwargs: Any) -> ImmutableComputedVar:
        """Replace the attributes of the ComputedVar.

        Args:
            merge_var_data: VarData to merge into the existing VarData.
            **kwargs: Var fields to update.

        Returns:
            The new ComputedVar instance.

        Raises:
            TypeError: If kwargs contains keys that are not allowed.
        """
        field_values = dict(
            fget=kwargs.pop("fget", self._fget),
            initial_value=kwargs.pop("initial_value", self._initial_value),
            cache=kwargs.pop("cache", self._cache),
            deps=kwargs.pop("deps", self._static_deps),
            auto_deps=kwargs.pop("auto_deps", self._auto_deps),
            interval=kwargs.pop("interval", self._update_interval),
            backend=kwargs.pop("backend", self._backend),
            _var_name=kwargs.pop("_var_name", self._var_name),
            _var_type=kwargs.pop("_var_type", self._var_type),
            _var_is_local=kwargs.pop("_var_is_local", self._var_is_local),
            _var_is_string=kwargs.pop("_var_is_string", self._var_is_string),
            _var_full_name_needs_state_prefix=kwargs.pop(
                "_var_full_name_needs_state_prefix",
                self._var_full_name_needs_state_prefix,
            ),
            _var_data=kwargs.pop(
                "_var_data", VarData.merge(self._var_data, merge_var_data)
            ),
        )

        if kwargs:
            unexpected_kwargs = ", ".join(kwargs.keys())
            raise TypeError(f"Unexpected keyword arguments: {unexpected_kwargs}")

        return ImmutableComputedVar(**field_values)

    @property
    def _cache_attr(self) -> str:
        """Get the attribute used to cache the value on the instance.

        Returns:
            An attribute name.
        """
        return f"__cached_{self._var_name}"

    @property
    def _last_updated_attr(self) -> str:
        """Get the attribute used to store the last updated timestamp.

        Returns:
            An attribute name.
        """
        return f"__last_updated_{self._var_name}"

    def needs_update(self, instance: BaseState) -> bool:
        """Check if the computed var needs to be updated.

        Args:
            instance: The state instance that the computed var is attached to.

        Returns:
            True if the computed var needs to be updated, False otherwise.
        """
        if self._update_interval is None:
            return False
        last_updated = getattr(instance, self._last_updated_attr, None)
        if last_updated is None:
            return True
        return datetime.datetime.now() - last_updated > self._update_interval

    @overload
    def __get__(
        self: ImmutableComputedVar[int] | ImmutableComputedVar[float],
        instance: None,
        owner: Type,
    ) -> NumberVar: ...

    @overload
    def __get__(
        self: ImmutableComputedVar[str],
        instance: None,
        owner: Type,
    ) -> StringVar: ...

    @overload
    def __get__(
        self: ImmutableComputedVar[dict[DICT_KEY, DICT_VAL]],
        instance: None,
        owner: Type,
    ) -> ObjectVar[dict[DICT_KEY, DICT_VAL]]: ...

    @overload
    def __get__(
        self: ImmutableComputedVar[list[LIST_INSIDE]],
        instance: None,
        owner: Type,
    ) -> ArrayVar[list[LIST_INSIDE]]: ...

    @overload
    def __get__(
        self: ImmutableComputedVar[set[LIST_INSIDE]],
        instance: None,
        owner: Type,
    ) -> ArrayVar[set[LIST_INSIDE]]: ...

    @overload
    def __get__(
        self: ImmutableComputedVar[tuple[LIST_INSIDE, ...]],
        instance: None,
        owner: Type,
    ) -> ArrayVar[tuple[LIST_INSIDE, ...]]: ...

    @overload
    def __get__(
        self, instance: None, owner: Type
    ) -> ImmutableComputedVar[RETURN_TYPE]: ...

    @overload
    def __get__(self, instance: BaseState, owner: Type) -> RETURN_TYPE: ...

    def __get__(self, instance: BaseState | None, owner):
        """Get the ComputedVar value.

        If the value is already cached on the instance, return the cached value.

        Args:
            instance: the instance of the class accessing this computed var.
            owner: the class that this descriptor is attached to.

        Returns:
            The value of the var for the given instance.
        """
        if instance is None:
            return self._replace(
                _var_name=format_state_name(owner.get_full_name())
                + "."
                + self._var_name,
                merge_var_data=ImmutableVarData.from_state(owner),
            ).guess_type()

        if not self._cache:
            return self.fget(instance)

        # handle caching
        if not hasattr(instance, self._cache_attr) or self.needs_update(instance):
            # Set cache attr on state instance.
            setattr(instance, self._cache_attr, self.fget(instance))
            # Ensure the computed var gets serialized to redis.
            instance._was_touched = True
            # Set the last updated timestamp on the state instance.
            setattr(instance, self._last_updated_attr, datetime.datetime.now())
        return getattr(instance, self._cache_attr)

    def _deps(
        self,
        objclass: Type,
        obj: FunctionType | CodeType | None = None,
        self_name: Optional[str] = None,
    ) -> set[str]:
        """Determine var dependencies of this ComputedVar.

        Save references to attributes accessed on "self".  Recursively called
        when the function makes a method call on "self" or define comprehensions
        or nested functions that may reference "self".

        Args:
            objclass: the class obj this ComputedVar is attached to.
            obj: the object to disassemble (defaults to the fget function).
            self_name: if specified, look for this name in LOAD_FAST and LOAD_DEREF instructions.

        Returns:
            A set of variable names accessed by the given obj.

        Raises:
            VarValueError: if the function references the get_state, parent_state, or substates attributes
                (cannot track deps in a related state, only implicitly via parent state).
        """
        if not self._auto_deps:
            return self._static_deps
        d = self._static_deps.copy()
        if obj is None:
            fget = self._fget
            if fget is not None:
                obj = cast(FunctionType, fget)
            else:
                return set()
        with contextlib.suppress(AttributeError):
            # unbox functools.partial
            obj = cast(FunctionType, obj.func)  # type: ignore
        with contextlib.suppress(AttributeError):
            # unbox EventHandler
            obj = cast(FunctionType, obj.fn)  # type: ignore

        if self_name is None and isinstance(obj, FunctionType):
            try:
                # the first argument to the function is the name of "self" arg
                self_name = obj.__code__.co_varnames[0]
            except (AttributeError, IndexError):
                self_name = None
        if self_name is None:
            # cannot reference attributes on self if method takes no args
            return set()

        invalid_names = ["get_state", "parent_state", "substates", "get_substate"]
        self_is_top_of_stack = False
        for instruction in dis.get_instructions(obj):
            if (
                instruction.opname in ("LOAD_FAST", "LOAD_DEREF")
                and instruction.argval == self_name
            ):
                # bytecode loaded the class instance to the top of stack, next load instruction
                # is referencing an attribute on self
                self_is_top_of_stack = True
                continue
            if self_is_top_of_stack and instruction.opname in (
                "LOAD_ATTR",
                "LOAD_METHOD",
            ):
                try:
                    ref_obj = getattr(objclass, instruction.argval)
                except Exception:
                    ref_obj = None
                if instruction.argval in invalid_names:
                    raise VarValueError(
                        f"Cached var {self._var_full_name} cannot access arbitrary state via `{instruction.argval}`."
                    )
                if callable(ref_obj):
                    # recurse into callable attributes
                    d.update(
                        self._deps(
                            objclass=objclass,
                            obj=ref_obj,
                        )
                    )
                # recurse into property fget functions
                elif isinstance(ref_obj, property) and not isinstance(
                    ref_obj, ImmutableComputedVar
                ):
                    d.update(
                        self._deps(
                            objclass=objclass,
                            obj=ref_obj.fget,  # type: ignore
                        )
                    )
                elif (
                    instruction.argval in objclass.backend_vars
                    or instruction.argval in objclass.vars
                ):
                    # var access
                    d.add(instruction.argval)
            elif instruction.opname == "LOAD_CONST" and isinstance(
                instruction.argval, CodeType
            ):
                # recurse into nested functions / comprehensions, which can reference
                # instance attributes from the outer scope
                d.update(
                    self._deps(
                        objclass=objclass,
                        obj=instruction.argval,
                        self_name=self_name,
                    )
                )
            self_is_top_of_stack = False
        return d

    def mark_dirty(self, instance) -> None:
        """Mark this ComputedVar as dirty.

        Args:
            instance: the state instance that needs to recompute the value.
        """
        with contextlib.suppress(AttributeError):
            delattr(instance, self._cache_attr)

    def _determine_var_type(self) -> Type:
        """Get the type of the var.

        Returns:
            The type of the var.
        """
        hints = get_type_hints(self._fget)
        if "return" in hints:
            return hints["return"]
        return Any

    @property
    def __class__(self) -> Type:
        """Get the class of the var.

        Returns:
            The class of the var.
        """
        return ComputedVar

    @property
    def fget(self) -> Callable[[BaseState], RETURN_TYPE]:
        """Get the getter function.

        Returns:
            The getter function.
        """
        return self._fget


if TYPE_CHECKING:
    BASE_STATE = TypeVar("BASE_STATE", bound=BaseState)


@overload
def immutable_computed_var(
    fget: None = None,
    initial_value: Any | types.Unset = types.Unset(),
    cache: bool = False,
    deps: Optional[List[Union[str, Var]]] = None,
    auto_deps: bool = True,
    interval: Optional[Union[datetime.timedelta, int]] = None,
    backend: bool | None = None,
    _deprecated_cached_var: bool = False,
    **kwargs,
) -> Callable[
    [Callable[[BASE_STATE], RETURN_TYPE]], ImmutableComputedVar[RETURN_TYPE]
]: ...


@overload
def immutable_computed_var(
    fget: Callable[[BASE_STATE], RETURN_TYPE],
    initial_value: RETURN_TYPE | types.Unset = types.Unset(),
    cache: bool = False,
    deps: Optional[List[Union[str, Var]]] = None,
    auto_deps: bool = True,
    interval: Optional[Union[datetime.timedelta, int]] = None,
    backend: bool | None = None,
    _deprecated_cached_var: bool = False,
    **kwargs,
) -> ImmutableComputedVar[RETURN_TYPE]: ...


def immutable_computed_var(
    fget: Callable[[BASE_STATE], Any] | None = None,
    initial_value: Any | types.Unset = types.Unset(),
    cache: bool = False,
    deps: Optional[List[Union[str, Var]]] = None,
    auto_deps: bool = True,
    interval: Optional[Union[datetime.timedelta, int]] = None,
    backend: bool | None = None,
    _deprecated_cached_var: bool = False,
    **kwargs,
) -> (
    ImmutableComputedVar | Callable[[Callable[[BASE_STATE], Any]], ImmutableComputedVar]
):
    """A ComputedVar decorator with or without kwargs.

    Args:
        fget: The getter function.
        initial_value: The initial value of the computed var.
        cache: Whether to cache the computed value.
        deps: Explicit var dependencies to track.
        auto_deps: Whether var dependencies should be auto-determined.
        interval: Interval at which the computed var should be updated.
        backend: Whether the computed var is a backend var.
        _deprecated_cached_var: Indicate usage of deprecated cached_var partial function.
        **kwargs: additional attributes to set on the instance

    Returns:
        A ComputedVar instance.

    Raises:
        ValueError: If caching is disabled and an update interval is set.
        VarDependencyError: If user supplies dependencies without caching.
    """
    if _deprecated_cached_var:
        console.deprecate(
            feature_name="cached_var",
            reason=("Use @rx.var(cache=True) instead of @rx.cached_var."),
            deprecation_version="0.5.6",
            removal_version="0.6.0",
        )

    if cache is False and interval is not None:
        raise ValueError("Cannot set update interval without caching.")

    if cache is False and (deps is not None or auto_deps is False):
        raise VarDependencyError("Cannot track dependencies without caching.")

    if fget is not None:
        return ImmutableComputedVar(fget, cache=cache)

    def wrapper(fget: Callable[[BASE_STATE], Any]) -> ImmutableComputedVar:
        return ImmutableComputedVar(
            fget,
            initial_value=initial_value,
            cache=cache,
            deps=deps,
            auto_deps=auto_deps,
            interval=interval,
            backend=backend,
            **kwargs,
        )

    return wrapper


# Partial function of computed_var with cache=True
cached_var = functools.partial(
    immutable_computed_var, cache=True, _deprecated_cached_var=True
)
