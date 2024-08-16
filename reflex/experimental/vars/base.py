"""Collection of base classes."""

from __future__ import annotations

import dataclasses
import functools
import inspect
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from typing_extensions import ParamSpec, get_origin

from reflex import constants
from reflex.base import Base
from reflex.utils import serializers, types
from reflex.utils.exceptions import VarTypeError
from reflex.vars import (
    ImmutableVarData,
    Var,
    VarData,
    _decode_var_immutable,
    _extract_var_data,
    _global_vars,
)

if TYPE_CHECKING:
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
        return type(self)(**field_values)

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
        self, output: Type[OUTPUT], var_type: types.GenericType | None = None
    ) -> OUTPUT: ...

    def to(
        self, output: Type[OUTPUT], var_type: types.GenericType | None = None
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
        from .number import (
            BooleanVar,
            NumberVar,
            ToBooleanVarOperation,
            ToNumberVarOperation,
        )

        fixed_type = (
            var_type
            if var_type is None or inspect.isclass(var_type)
            else get_origin(var_type)
        )

        if issubclass(output, NumberVar):
            if fixed_type is not None and not issubclass(fixed_type, (int, float)):
                raise TypeError(
                    f"Unsupported type {var_type} for NumberVar. Must be int or float."
                )
            return ToNumberVarOperation(self, var_type or float)
        if issubclass(output, BooleanVar):
            return ToBooleanVarOperation(self)

        from .sequence import ArrayVar, StringVar, ToArrayOperation, ToStringOperation

        if issubclass(output, ArrayVar):
            if fixed_type is not None and not issubclass(
                fixed_type, (list, tuple, set)
            ):
                raise TypeError(
                    f"Unsupported type {var_type} for ArrayVar. Must be list, tuple, or set."
                )
            return ToArrayOperation(self, var_type or list)
        if issubclass(output, StringVar):
            return ToStringOperation(self)

        from .object import ObjectVar, ToObjectOperation

        if issubclass(output, ObjectVar):
            return ToObjectOperation(self, var_type or dict)

        from .function import FunctionVar, ToFunctionOperation

        if issubclass(output, FunctionVar):
            if fixed_type is not None and not issubclass(fixed_type, Callable):
                raise TypeError(
                    f"Unsupported type {var_type} for FunctionVar. Must be Callable."
                )
            return ToFunctionOperation(self, var_type or Callable)

        return output(
            _var_name=self._var_name,
            _var_type=self._var_type if var_type is None else var_type,
            _var_data=self._var_data,
        )

    def guess_type(self) -> ImmutableVar:
        """Guess the type of the var.

        Returns:
            The guessed type.
        """
        from .number import NumberVar
        from .object import ObjectVar
        from .sequence import ArrayVar, StringVar

        if self._var_type is Any:
            return self

        var_type = self._var_type

        fixed_type = var_type if inspect.isclass(var_type) else get_origin(var_type)

        if issubclass(fixed_type, (int, float)):
            return self.to(NumberVar, var_type)
        if issubclass(fixed_type, dict):
            return self.to(ObjectVar, var_type)
        if issubclass(fixed_type, (list, tuple, set)):
            return self.to(ArrayVar, var_type)
        if issubclass(fixed_type, str):
            return self.to(StringVar)
        if issubclass(fixed_type, Base):
            return self.to(ObjectVar, var_type)
        return self


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

        from .object import LiteralObjectVar

        if isinstance(value, Base):
            return LiteralObjectVar(
                value.dict(), _var_type=type(value), _var_data=_var_data
            )

        from .number import LiteralBooleanVar, LiteralNumberVar
        from .sequence import LiteralArrayVar, LiteralStringVar

        if isinstance(value, str):
            return LiteralStringVar.create(value, _var_data=_var_data)

        type_mapping = {
            int: LiteralNumberVar,
            float: LiteralNumberVar,
            bool: LiteralBooleanVar,
            dict: LiteralObjectVar,
            list: LiteralArrayVar,
            tuple: LiteralArrayVar,
            set: LiteralArrayVar,
        }

        constructor = type_mapping.get(type(value))

        if constructor is None:
            raise TypeError(f"Unsupported type {type(value)} for LiteralVar.")

        return constructor(value, _var_data=_var_data)

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


def figure_out_type(value: Any) -> Type:
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
    return type(value)
