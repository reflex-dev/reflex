"""Collection of base classes."""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import dis
import functools
import inspect
import json
import random
import re
import string
import uuid
import warnings
from types import CodeType, EllipsisType, FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    FrozenSet,
    Generic,
    Iterable,
    List,
    Literal,
    Mapping,
    NoReturn,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    overload,
)

from typing_extensions import (
    ParamSpec,
    Protocol,
    TypeGuard,
    deprecated,
    get_type_hints,
    override,
)

from reflex import constants
from reflex.base import Base
from reflex.constants.compiler import Hooks
from reflex.utils import console, exceptions, imports, serializers, types
from reflex.utils.exceptions import (
    UntypedComputedVarError,
    VarDependencyError,
    VarTypeError,
    VarValueError,
)
from reflex.utils.format import format_state_name
from reflex.utils.imports import (
    ImmutableParsedImportDict,
    ImportDict,
    ImportVar,
    ParsedImportDict,
    parse_imports,
)
from reflex.utils.types import (
    GenericType,
    Self,
    _isinstance,
    get_origin,
    has_args,
    safe_issubclass,
    typehint_issubclass,
    unionize,
)

if TYPE_CHECKING:
    from reflex.components.component import BaseComponent
    from reflex.state import BaseState

    from .function import ArgsFunctionOperation
    from .number import BooleanVar, NumberVar
    from .object import ObjectVar
    from .sequence import ArrayVar, StringVar


VAR_TYPE = TypeVar("VAR_TYPE", covariant=True)
VALUE = TypeVar("VALUE")
INT_OR_FLOAT = TypeVar("INT_OR_FLOAT", int, float)
FAKE_VAR_TYPE = TypeVar("FAKE_VAR_TYPE")
OTHER_VAR_TYPE = TypeVar("OTHER_VAR_TYPE")
STRING_T = TypeVar("STRING_T", bound=str)
SEQUENCE_TYPE = TypeVar("SEQUENCE_TYPE", bound=Sequence)

warnings.filterwarnings("ignore", message="fields may not start with an underscore")

P = ParamSpec("P")
R = TypeVar("R")


class ReflexCallable(Protocol[P, R]):
    """Protocol for a callable."""

    __call__: Callable[P, R]


ReflexCallableParams = Union[EllipsisType, Tuple[GenericType, ...]]


def unwrap_reflex_callalbe(
    callable_type: GenericType,
) -> Tuple[ReflexCallableParams, GenericType]:
    """Unwrap the ReflexCallable type.

    Args:
        callable_type: The ReflexCallable type to unwrap.

    Returns:
        The unwrapped ReflexCallable type.
    """
    if callable_type is ReflexCallable:
        return Ellipsis, Any

    origin = get_origin(callable_type)

    if origin is not ReflexCallable:
        if origin in types.UnionTypes:
            args = get_args(callable_type)
            params: List[ReflexCallableParams] = []
            return_types: List[GenericType] = []
            for arg in args:
                param, return_type = unwrap_reflex_callalbe(arg)
                if param not in params:
                    params.append(param)
                return_types.append(return_type)
            return (
                Ellipsis if len(params) > 1 else params[0],
                unionize(*return_types),
            )
        return Ellipsis, Any

    args = get_args(callable_type)
    if not args or len(args) != 2:
        return Ellipsis, Any
    return args


@dataclasses.dataclass(
    eq=False,
    frozen=True,
)
class VarSubclassEntry:
    """Entry for a Var subclass."""

    var_subclass: Type[Var]
    to_var_subclass: Type[ToOperation]
    python_types: Tuple[GenericType, ...]
    is_subclass: Callable[[GenericType], bool] | None


_var_subclasses: List[VarSubclassEntry] = []
_var_literal_subclasses: List[Tuple[Type[LiteralVar], VarSubclassEntry]] = []


@dataclasses.dataclass(
    eq=True,
    frozen=True,
)
class VarData:
    """Metadata associated with a x."""

    # The name of the enclosing state.
    state: str = dataclasses.field(default="")

    # The name of the field in the state.
    field_name: str = dataclasses.field(default="")

    # Imports needed to render this var
    imports: ImmutableParsedImportDict = dataclasses.field(default_factory=tuple)

    # Hooks that need to be present in the component to render this var
    hooks: Tuple[str, ...] = dataclasses.field(default_factory=tuple)

    # Components that need to be present in the component to render this var
    components: Tuple[BaseComponent, ...] = dataclasses.field(default_factory=tuple)

    # Dependencies of the var
    deps: Tuple[Var, ...] = dataclasses.field(default_factory=tuple)

    # Position of the hook in the component
    position: Hooks.HookPosition | None = None

    def __init__(
        self,
        state: str = "",
        field_name: str = "",
        imports: ImportDict | ParsedImportDict | None = None,
        hooks: Mapping[str, VarData | None] | Sequence[str] | str | None = None,
        components: Iterable[BaseComponent] | None = None,
        deps: list[Var] | None = None,
        position: Hooks.HookPosition | None = None,
    ):
        """Initialize the var data.

        Args:
            state: The name of the enclosing state.
            field_name: The name of the field in the state.
            imports: Imports needed to render this var.
            hooks: Hooks that need to be present in the component to render this var.
            components: Components that need to be present in the component to render this var.
            deps: Dependencies of the var for useCallback.
            position: Position of the hook in the component.
        """
        if isinstance(hooks, str):
            hooks = [hooks]
        if not isinstance(hooks, dict):
            hooks = {hook: None for hook in (hooks or [])}
        immutable_imports: ImmutableParsedImportDict = tuple(
            (k, tuple(v)) for k, v in parse_imports(imports or {}).items()
        )
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "field_name", field_name)
        object.__setattr__(self, "imports", immutable_imports)
        object.__setattr__(self, "hooks", tuple(hooks or {}))
        object.__setattr__(
            self, "components", tuple(components) if components is not None else ()
        )
        object.__setattr__(self, "deps", tuple(deps or []))
        object.__setattr__(self, "position", position or None)

        if hooks and any(hooks.values()):
            merged_var_data = VarData.merge(self, *hooks.values())
            if merged_var_data is not None:
                object.__setattr__(self, "state", merged_var_data.state)
                object.__setattr__(self, "field_name", merged_var_data.field_name)
                object.__setattr__(self, "imports", merged_var_data.imports)
                object.__setattr__(self, "hooks", merged_var_data.hooks)
                object.__setattr__(self, "deps", merged_var_data.deps)
                object.__setattr__(self, "position", merged_var_data.position)

    def old_school_imports(self) -> ImportDict:
        """Return the imports as a mutable dict.

        Returns:
            The imports as a mutable dict.
        """
        return {k: list(v) for k, v in self.imports}

    def merge(*all: VarData | None) -> VarData | None:
        """Merge multiple var data objects.

        Returns:
            The merged var data object.

        Raises:
            ReflexError: If the positions of the var data objects are different.
        """
        all_var_datas = list(filter(None, all))

        if not all_var_datas:
            return None

        if len(all_var_datas) == 1:
            return all_var_datas[0]

        # Get the first non-empty field name or default to empty string.
        field_name = next(
            (var_data.field_name for var_data in all_var_datas if var_data.field_name),
            "",
        )

        # Get the first non-empty state or default to empty string.
        state = next(
            (var_data.state for var_data in all_var_datas if var_data.state), ""
        )

        hooks: dict[str, VarData | None] = {
            hook: None for var_data in all_var_datas for hook in var_data.hooks
        }

        _imports = imports.merge_imports(
            *(var_data.imports for var_data in all_var_datas)
        )

        deps = [dep for var_data in all_var_datas for dep in var_data.deps]

        positions = list(
            {
                var_data.position
                for var_data in all_var_datas
                if var_data.position is not None
            }
        )

        components = tuple(
            component for var_data in all_var_datas for component in var_data.components
        )

        if positions:
            if len(positions) > 1:
                raise exceptions.ReflexError(
                    f"Cannot merge var data with different positions: {positions}"
                )
            position = positions[0]
        else:
            position = None

        return VarData(
            state=state,
            field_name=field_name,
            imports=_imports,
            hooks=hooks,
            deps=deps,
            position=position,
            components=components,
        )

    def __bool__(self) -> bool:
        """Check if the var data is non-empty.

        Returns:
            True if any field is set to a non-default value.
        """
        return any(getattr(self, field.name) for field in dataclasses.fields(self))

    @classmethod
    def from_state(cls, state: Type[BaseState] | str, field_name: str = "") -> VarData:
        """Set the state of the var.

        Args:
            state: The state to set or the full name of the state.
            field_name: The name of the field in the state. Optional.

        Returns:
            The var with the set state.
        """
        from reflex.utils import format

        state_name = state if isinstance(state, str) else state.get_full_name()
        return VarData(
            state=state_name,
            field_name=field_name,
            hooks={
                "const {0} = useContext(StateContexts.{0})".format(
                    format.format_state_name(state_name)
                ): None
            },
            imports={
                f"$/{constants.Dirs.CONTEXTS_PATH}": [ImportVar(tag="StateContexts")],
                "react": [ImportVar(tag="useContext")],
            },
        )


def _decode_var_immutable(value: str) -> tuple[VarData | None, str]:
    """Decode the state name from a formatted var.

    Args:
        value: The value to extract the state name from.

    Returns:
        The extracted state name and the value without the state name.
    """
    var_datas = []
    if isinstance(value, str):
        # fast path if there is no encoded VarData
        if constants.REFLEX_VAR_OPENING_TAG not in value:
            return None, value

        offset = 0

        # Find all tags.
        while m := _decode_var_pattern.search(value):
            start, end = m.span()
            value = value[:start] + value[end:]

            serialized_data = m.group(1)

            if serialized_data.isnumeric() or (
                serialized_data[0] == "-" and serialized_data[1:].isnumeric()
            ):
                # This is a global immutable var.
                var = _global_vars[int(serialized_data)]
                var_data = var._get_all_var_data()

                if var_data is not None:
                    var_datas.append(var_data)
            offset += end - start

    return VarData.merge(*var_datas) if var_datas else None, value


def can_use_in_object_var(cls: GenericType) -> bool:
    """Check if the class can be used in an ObjectVar.

    Args:
        cls: The class to check.

    Returns:
        Whether the class can be used in an ObjectVar.
    """
    if types.is_union(cls):
        return all(can_use_in_object_var(t) for t in types.get_args(cls))
    return (
        inspect.isclass(cls)
        and not issubclass(cls, Var)
        and serializers.can_serialize(cls, dict)
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
)
class Var(Generic[VAR_TYPE]):
    """Base class for immutable vars."""

    # The name of the var.
    _js_expr: str = dataclasses.field()

    # The type of the var.
    _var_type: types.GenericType = dataclasses.field(default=Any)

    # Extra metadata associated with the Var
    _var_data: Optional[VarData] = dataclasses.field(default=None)

    def __str__(self) -> str:
        """String representation of the var. Guaranteed to be a valid Javascript expression.

        Returns:
            The name of the var.
        """
        return self._js_expr

    @property
    def _var_is_local(self) -> bool:
        """Whether this is a local javascript variable.

        Returns:
            False
        """
        return False

    @property
    @deprecated("Use `_js_expr` instead.")
    def _var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return self._js_expr

    @property
    def _var_field_name(self) -> str:
        """The name of the field.

        Returns:
            The name of the field.
        """
        var_data = self._get_all_var_data()
        field_name = var_data.field_name if var_data else None
        return field_name or self._js_expr

    @property
    @deprecated("Use `_js_expr` instead.")
    def _var_name_unwrapped(self) -> str:
        """The name of the var without extra curly braces.

        Returns:
            The name of the var.
        """
        return self._js_expr

    @property
    def _var_is_string(self) -> bool:
        """Whether the var is a string literal.

        Returns:
            False
        """
        return False

    def __init_subclass__(
        cls,
        python_types: Tuple[GenericType, ...] | GenericType = types.Unset(),
        default_type: GenericType = types.Unset(),
        is_subclass: Callable[[GenericType], bool] | types.Unset = types.Unset(),
        **kwargs,
    ):
        """Initialize the subclass.

        Args:
            python_types: The python types that the var represents.
            default_type: The default type of the var. Defaults to the first python type.
            is_subclass: A function to check if a type is a subclass of the var.
            **kwargs: Additional keyword arguments.
        """
        super().__init_subclass__(**kwargs)

        if python_types or default_type or is_subclass:
            python_types = (
                (python_types if isinstance(python_types, tuple) else (python_types,))
                if python_types
                else ()
            )

            default_type = default_type or (python_types[0] if python_types else Any)

            @dataclasses.dataclass(
                eq=False,
                frozen=True,
                slots=True,
            )
            class ToVarOperation(ToOperation, cls):
                """Base class of converting a var to another var type."""

                _original: Var = dataclasses.field(
                    default=Var(_js_expr="null", _var_type=None),
                )

                _default_var_type: ClassVar[GenericType] = default_type

            new_to_var_operation_name = f"To{cls.__name__.removesuffix('Var')}Operation"
            ToVarOperation.__qualname__ = (
                ToVarOperation.__qualname__.removesuffix(ToVarOperation.__name__)
                + new_to_var_operation_name
            )
            ToVarOperation.__name__ = new_to_var_operation_name

            _var_subclasses.append(
                VarSubclassEntry(
                    cls,
                    ToVarOperation,
                    python_types,
                    is_subclass if not isinstance(is_subclass, types.Unset) else None,
                )
            )

    def __post_init__(self):
        """Post-initialize the var."""
        # Decode any inline Var markup and apply it to the instance
        _var_data, _js_expr = _decode_var_immutable(self._js_expr)

        if _var_data or _js_expr != self._js_expr:
            self.__init__(
                **{
                    **dataclasses.asdict(self),
                    "_js_expr": _js_expr,
                    "_var_data": VarData.merge(self._var_data, _var_data),
                }
            )

    def __hash__(self) -> int:
        """Define a hash function for the var.

        Returns:
            The hash of the var.
        """
        return hash((self._js_expr, self._var_type, self._var_data))

    def _get_all_var_data(self) -> VarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._var_data

    def equals(self, other: Var) -> bool:
        """Check if two vars are equal.

        Args:
            other: The other var to compare.

        Returns:
            Whether the vars are equal.
        """
        return (
            self._js_expr == other._js_expr
            and self._var_type == other._var_type
            and self._get_all_var_data() == other._get_all_var_data()
        )

    @overload
    def _replace(
        self,
        _var_type: Type[OTHER_VAR_TYPE],
        merge_var_data: VarData | None = None,
        **kwargs: Any,
    ) -> Var[OTHER_VAR_TYPE]: ...

    @overload
    def _replace(
        self,
        _var_type: GenericType | None = None,
        merge_var_data: VarData | None = None,
        **kwargs: Any,
    ) -> Self: ...

    def _replace(
        self,
        _var_type: GenericType | None = None,
        merge_var_data: VarData | None = None,
        **kwargs: Any,
    ) -> Self | Var:
        """Make a copy of this Var with updated fields.

        Args:
            _var_type: The new type of the Var.
            merge_var_data: VarData to merge into the existing VarData.
            **kwargs: Var fields to update.

        Returns:
            A new Var with the updated fields overwriting the corresponding fields in this Var.

        Raises:
            TypeError: If _var_is_local, _var_is_string, or _var_full_name_needs_state_prefix is not None.
        """
        if kwargs.get("_var_is_local", False) is not False:
            raise TypeError("The _var_is_local argument is not supported for Var.")

        if kwargs.get("_var_is_string", False) is not False:
            raise TypeError("The _var_is_string argument is not supported for Var.")

        if kwargs.get("_var_full_name_needs_state_prefix", False) is not False:
            raise TypeError(
                "The _var_full_name_needs_state_prefix argument is not supported for Var."
            )
        value_with_replaced = dataclasses.replace(
            self,
            _var_type=_var_type or self._var_type,
            _var_data=VarData.merge(
                kwargs.get("_var_data", self._var_data), merge_var_data
            ),
            **kwargs,
        )

        if (js_expr := kwargs.get("_js_expr")) is not None:
            object.__setattr__(value_with_replaced, "_js_expr", js_expr)

        return value_with_replaced

    @overload
    @classmethod
    def create(  # type: ignore[override]
        cls,
        value: bool,
        _var_data: VarData | None = None,
    ) -> BooleanVar: ...

    @overload
    @classmethod
    def create(  # type: ignore[override]
        cls,
        value: int,
        _var_data: VarData | None = None,
    ) -> NumberVar[int]: ...

    @overload
    @classmethod
    def create(
        cls,
        value: float,
        _var_data: VarData | None = None,
    ) -> NumberVar[float]: ...

    @overload
    @classmethod
    def create(  # pyright: ignore [reportOverlappingOverload]
        cls,
        value: STRING_T,
        _var_data: VarData | None = None,
    ) -> StringVar[STRING_T]: ...

    @overload
    @classmethod
    def create(
        cls,
        value: None,
        _var_data: VarData | None = None,
    ) -> NoneVar: ...

    @overload
    @classmethod
    def create(
        cls,
        value: MAPPING_TYPE,
        _var_data: VarData | None = None,
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    @classmethod
    def create(
        cls,
        value: SEQUENCE_TYPE,
        _var_data: VarData | None = None,
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    @classmethod
    def create(
        cls,
        value: OTHER_VAR_TYPE,
        _var_data: VarData | None = None,
    ) -> Var[OTHER_VAR_TYPE]: ...

    @classmethod
    def create(
        cls,
        value: OTHER_VAR_TYPE,
        _var_data: VarData | None = None,
    ) -> Var[OTHER_VAR_TYPE]:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        # If the value is already a var, do nothing.
        if isinstance(value, Var):
            return value

        return LiteralVar.create(value, _var_data=_var_data)

    @classmethod
    @deprecated("Use `.create()` instead.")
    def create_safe(
        cls,
        *args: Any,
        **kwargs: Any,
    ) -> Var:
        """Create a var from a value.

        Args:
            *args: The arguments to create the var from.
            **kwargs: The keyword arguments to create the var from.

        Returns:
            The var.
        """
        return cls.create(*args, **kwargs)

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
        return f"{constants.REFLEX_VAR_OPENING_TAG}{hashed_var}{constants.REFLEX_VAR_CLOSING_TAG}{self._js_expr}"

    @overload
    def to(self, output: Type[bool]) -> BooleanVar: ...  # pyright: ignore [reportOverlappingOverload]

    @overload
    def to(self, output: Type[int]) -> NumberVar[int]: ...

    @overload
    def to(self, output: type[float]) -> NumberVar[float]: ...

    @overload
    def to(self, output: Type[str]) -> StringVar: ...  # pyright: ignore [reportOverlappingOverload]

    @overload
    def to(
        self,
        output: type[Sequence[VALUE]] | type[set[VALUE]],
    ) -> ArrayVar[Sequence[VALUE]]: ...

    @overload
    def to(
        self,
        output: type[MAPPING_TYPE],
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def to(
        self, output: Type[ObjectVar], var_type: Type[VAR_INSIDE]
    ) -> ObjectVar[VAR_INSIDE]: ...

    @overload
    def to(
        self, output: Type[ObjectVar], var_type: None = None
    ) -> ObjectVar[VAR_TYPE]: ...

    @overload
    def to(self, output: VAR_SUBCLASS, var_type: None = None) -> VAR_SUBCLASS: ...

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

        Returns:
            The converted var.
        """
        from .object import ObjectVar

        fixed_output_type = get_origin(output) or output

        # If the first argument is a python type, we map it to the corresponding Var type.
        for var_subclass in _var_subclasses[::-1]:
            if (
                var_subclass.python_types
                and safe_issubclass(fixed_output_type, var_subclass.python_types)
            ) or (
                var_subclass.is_subclass and var_subclass.is_subclass(fixed_output_type)
            ):
                return self.to(var_subclass.var_subclass, output)

        if fixed_output_type is None:
            return get_to_operation(NoneVar).create(self)  # pyright: ignore [reportReturnType]

        # Handle fixed_output_type being Base or a dataclass.
        if can_use_in_object_var(output):
            return self.to(ObjectVar, output)

        if inspect.isclass(output):
            for var_subclass in _var_subclasses[::-1]:
                if issubclass(output, var_subclass.var_subclass):
                    current_var_type = self._var_type
                    if current_var_type is Any:
                        new_var_type = var_type
                    else:
                        new_var_type = var_type or current_var_type
                    to_operation_return = var_subclass.to_var_subclass.create(
                        value=self, _var_type=new_var_type
                    )
                    return to_operation_return  # pyright: ignore [reportReturnType]

            # If we can't determine the first argument, we just replace the _var_type.
            if not issubclass(output, Var) or var_type is None:
                return dataclasses.replace(
                    self,
                    _var_type=output,
                )

        # We couldn't determine the output type to be any other Var type, so we replace the _var_type.
        if var_type is not None:
            return dataclasses.replace(
                self,
                _var_type=var_type,
            )

        return self

    # We use `NoReturn` here to catch `Var[Any]` and `Var[Unknown]` cases first.
    @overload
    def guess_type(self: Var[NoReturn]) -> Var: ...  # pyright: ignore [reportOverlappingOverload]

    @overload
    def guess_type(self: Var[bool]) -> BooleanVar: ...

    @overload
    def guess_type(self: Var[INT_OR_FLOAT]) -> NumberVar[INT_OR_FLOAT]: ...

    @overload
    def guess_type(self: Var[str]) -> StringVar: ...  # pyright: ignore [reportOverlappingOverload]

    @overload
    def guess_type(self: Var[Sequence[VALUE]]) -> ArrayVar[Sequence[VALUE]]: ...

    @overload
    def guess_type(self: Var[Set[VALUE]]) -> ArrayVar[Set[VALUE]]: ...

    @overload
    def guess_type(
        self: Var[Dict[VALUE, OTHER_VAR_TYPE]],
    ) -> ObjectVar[Dict[VALUE, OTHER_VAR_TYPE]]: ...

    @overload
    def guess_type(self: Var[BASE_TYPE]) -> ObjectVar[BASE_TYPE]: ...

    @overload
    def guess_type(self) -> Self: ...

    def guess_type(self) -> Var:
        """Guesses the type of the variable based on its `_var_type` attribute.

        Returns:
            Var: The guessed type of the variable.

        Raises:
            TypeError: If the type is not supported for guessing.
        """
        from .object import ObjectVar

        var_type = self._var_type

        if var_type is None:
            return self.to(None)

        if types.is_optional(var_type):
            var_type = types.get_args(var_type)[0]

        if var_type is Any:
            return self

        fixed_type = get_origin(var_type) or var_type

        if fixed_type in types.UnionTypes:
            inner_types = get_args(var_type)

            for var_subclass in _var_subclasses:
                if all(
                    (
                        safe_issubclass(t, var_subclass.python_types)
                        or (var_subclass.is_subclass and var_subclass.is_subclass(t))
                    )
                    for t in inner_types
                ):
                    return self.to(var_subclass.var_subclass, self._var_type)

            if can_use_in_object_var(var_type):
                return self.to(ObjectVar, self._var_type)

            return self

        if fixed_type is Literal:
            args = get_args(var_type)
            fixed_type = unionize(*(type(arg) for arg in args))

        if not inspect.isclass(fixed_type):
            raise TypeError(f"Unsupported type {var_type} for guess_type.")

        if fixed_type is None:
            return self.to(None)

        for var_subclass in _var_subclasses[::-1]:
            if safe_issubclass(fixed_type, var_subclass.python_types) or (
                var_subclass.is_subclass and var_subclass.is_subclass(fixed_type)
            ):
                return self.to(var_subclass.var_subclass, self._var_type)

        if can_use_in_object_var(fixed_type):
            return self.to(ObjectVar, self._var_type)

        return self

    def _get_default_value(self) -> Any:
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
        if issubclass(type_, Mapping):
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

    def _get_setter_name(self, include_state: bool = True) -> str:
        """Get the name of the var's generated setter function.

        Args:
            include_state: Whether to include the state name in the setter name.

        Returns:
            The name of the setter function.
        """
        setter = constants.SETTER_PREFIX + self._var_field_name
        var_data = self._get_all_var_data()
        if var_data is None:
            return setter
        if not include_state or var_data.state == "":
            return setter
        return ".".join((var_data.state, setter))

    def _get_setter(self) -> Callable[[BaseState, Any], None]:
        """Get the var's setter function.

        Returns:
            A function that that creates a setter for the var.
        """
        actual_name = self._var_field_name

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
                        f"{type(state).__name__}.{self._js_expr}: Failed conversion of {value} to '{self._var_type.__name__}'. Value not set.",
                    )
            else:
                setattr(state, actual_name, value)

        setter.__qualname__ = self._get_setter_name()

        return setter

    def _var_set_state(self, state: type[BaseState] | str) -> Self:
        """Set the state of the var.

        Args:
            state: The state to set.

        Returns:
            The var with the state set.
        """
        formatted_state_name = (
            state
            if isinstance(state, str)
            else format_state_name(state.get_full_name())
        )

        return StateOperation.create(  # pyright: ignore [reportReturnType]
            formatted_state_name,
            self,
            _var_data=VarData.merge(
                VarData.from_state(state, self._js_expr), self._var_data
            ),
        ).guess_type()

    def __eq__(self, other: Var | Any) -> BooleanVar:
        """Check if the current variable is equal to the given variable.

        Args:
            other (Var | Any): The variable to compare with.

        Returns:
            BooleanVar: A BooleanVar object representing the result of the equality check.
        """
        from .number import equal_operation

        return equal_operation(self, other).guess_type()

    def __ne__(self, other: Var | Any) -> BooleanVar:
        """Check if the current object is not equal to the given object.

        Parameters:
            other (Var | Any): The object to compare with.

        Returns:
            BooleanVar: A BooleanVar object representing the result of the comparison.
        """
        from .number import equal_operation

        return (~equal_operation(self, other)).guess_type()

    def bool(self) -> BooleanVar:
        """Convert the var to a boolean.

        Returns:
            The boolean var.
        """
        from .number import boolify

        return boolify(self)  # pyright: ignore [reportReturnType]

    def __and__(self, other: Var | Any) -> Var:
        """Perform a logical AND operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical AND operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical AND operation.
        """
        return and_operation(self, other)

    def __rand__(self, other: Var | Any) -> Var:
        """Perform a logical AND operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical AND operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical AND operation.
        """
        return and_operation(other, self)

    def __or__(self, other: Var | Any) -> Var:
        """Perform a logical OR operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical OR operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical OR operation.
        """
        return or_operation(self, other)

    def __ror__(self, other: Var | Any) -> Var:
        """Perform a logical OR operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical OR operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical OR operation.
        """
        return or_operation(other, self)

    def __invert__(self) -> BooleanVar:
        """Perform a logical NOT operation on the current instance.

        Returns:
            A `BooleanVar` object representing the result of the logical NOT operation.
        """
        return (~self.bool()).guess_type()

    def to_string(self, use_json: bool = True) -> StringVar:
        """Convert the var to a string.

        Args:
            use_json: Whether to use JSON stringify. If False, uses Object.prototype.toString.

        Returns:
            The string var.
        """
        from .function import JSON_STRINGIFY, PROTOTYPE_TO_STRING
        from .sequence import StringVar

        return (
            JSON_STRINGIFY.call(self).to(StringVar)
            if use_json
            else PROTOTYPE_TO_STRING.call(self).to(StringVar)
        )

    def _as_ref(self) -> Var:
        """Get a reference to the var.

        Returns:
            The reference to the var.
        """
        from .object import ObjectVar

        refs = Var(
            _js_expr="refs",
            _var_data=VarData(
                imports={
                    f"$/{constants.Dirs.STATE_PATH}": [imports.ImportVar(tag="refs")]
                }
            ),
        ).to(ObjectVar, Mapping[str, str])
        return refs[LiteralVar.create(str(self))]

    @deprecated("Use `.js_type()` instead.")
    def _type(self) -> StringVar:
        """Returns the type of the object.

        This method uses the `typeof` function from the `FunctionStringVar` class
        to determine the type of the object.

        Returns:
            StringVar: A string variable representing the type of the object.
        """
        return self.js_type()

    def js_type(self) -> StringVar:
        """Returns the javascript type of the object.

        This method uses the `typeof` function from the `FunctionStringVar` class
        to determine the type of the object.

        Returns:
            StringVar: A string variable representing the type of the object.
        """
        from .function import FunctionStringVar
        from .sequence import StringVar

        type_of = FunctionStringVar("typeof")
        return type_of.call(self).to(StringVar)

    def _without_data(self):
        """Create a copy of the var without the data.

        Returns:
            The var without the data.
        """
        return dataclasses.replace(self, _var_data=None)

    def __get__(self, instance: Any, owner: Any):
        """Get the var.

        Args:
            instance: The instance to get the var from.
            owner: The owner of the var.

        Returns:
            The var.
        """
        return self

    def _decode(self) -> Any:
        """Decode Var as a python value.

        Note that Var with state set cannot be decoded python-side and will be
        returned as full_name.

        Returns:
            The decoded value or the Var name.
        """
        if isinstance(self, LiteralVar):
            return self._var_value
        try:
            return json.loads(str(self))
        except ValueError:
            return str(self)

    @property
    def _var_state(self) -> str:
        """Compat method for getting the state.

        Returns:
            The state name associated with the var.
        """
        var_data = self._get_all_var_data()
        return var_data.state if var_data else ""

    @overload
    @classmethod
    def range(cls, stop: int | NumberVar, /) -> ArrayVar[Sequence[int]]: ...

    @overload
    @classmethod
    def range(
        cls,
        start: int | NumberVar,
        end: int | NumberVar,
        step: int | NumberVar = 1,
        /,
    ) -> ArrayVar[Sequence[int]]: ...

    @classmethod
    def range(
        cls,
        first_endpoint: int | Var[int],
        second_endpoint: int | Var[int] | None = None,
        step: int | Var[int] | None = None,
        /,
    ) -> ArrayVar[Sequence[int]]:
        """Create a range of numbers.

        Args:
            first_endpoint: The end of the range if second_endpoint is not provided, otherwise the start of the range.
            second_endpoint: The end of the range.
            step: The step of the range.

        Returns:
            The range of numbers.
        """
        from .sequence import ArrayVar

        if step is None:
            return ArrayVar.range(first_endpoint, second_endpoint)

        return ArrayVar.range(first_endpoint, second_endpoint, step)

    if not TYPE_CHECKING:

        def __bool__(self) -> bool:
            """Raise exception if using Var in a boolean context.

            Raises:
                VarTypeError: when attempting to bool-ify the Var.

            # noqa: DAR101 self
            """
            raise VarTypeError(
                f"Cannot convert Var {str(self)!r} to bool for use with `if`, `and`, `or`, and `not`. "
                "Instead use `rx.cond` and bitwise operators `&` (and), `|` (or), `~` (invert)."
            )

        def __iter__(self) -> Any:
            """Raise exception if using Var in an iterable context.

            Raises:
                VarTypeError: when attempting to iterate over the Var.

            # noqa: DAR101 self
            """
            raise VarTypeError(
                f"Cannot iterate over Var {str(self)!r}. Instead use `rx.foreach`."
            )

        def __contains__(self, _: Any) -> Var:
            """Override the 'in' operator to alert the user that it is not supported.

            Raises:
                VarTypeError: the operation is not supported

            # noqa: DAR101 self
            """
            raise VarTypeError(
                "'in' operator not supported for Var types, use Var.contains() instead."
            )


OUTPUT = TypeVar("OUTPUT", bound=Var)

VAR_SUBCLASS = TypeVar("VAR_SUBCLASS", bound=Var)
VAR_INSIDE = TypeVar("VAR_INSIDE")


class VarWithDefault(Var[VAR_TYPE]):
    """Annotate an optional argument."""

    def __init__(self, default_value: VAR_TYPE):
        """Initialize the default value.

        Args:
            default_value: The default value.
        """
        super().__init__("")
        self._default = default_value

    @property
    def default(self) -> Var[VAR_TYPE]:
        """Get the default value.

        Returns:
            The default value.
        """
        return Var.create(self._default)


class ToOperation:
    """A var operation that converts a var to another type."""

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute of the var.
        """
        from .object import ObjectVar

        if isinstance(self, ObjectVar) and name != "_js_expr":
            return ObjectVar.__getattr__(self, name)
        return getattr(self._original, name)

    def __post_init__(self):
        """Post initialization."""
        object.__delattr__(self, "_js_expr")

    def __hash__(self) -> int:
        """Calculate the hash value of the object.

        Returns:
            int: The hash value of the object.
        """
        return hash(self._original)

    def _get_all_var_data(self) -> VarData | None:
        """Get all the var data.

        Returns:
            The var data.
        """
        return VarData.merge(
            self._original._get_all_var_data(),
            self._var_data,
        )

    @classmethod
    def create(
        cls,
        value: Var,
        _var_type: GenericType | None = None,
        _var_data: VarData | None = None,
    ):
        """Create a ToOperation.

        Args:
            value: The value of the var.
            _var_type: The type of the Var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The ToOperation.
        """
        return cls(
            _js_expr="",  # pyright: ignore [reportCallIssue]
            _var_data=_var_data,  # pyright: ignore [reportCallIssue]
            _var_type=_var_type or cls._default_var_type,  # pyright: ignore [reportCallIssue, reportAttributeAccessIssue]
            _original=value,  # pyright: ignore [reportCallIssue]
        )


class LiteralVar(Var):
    """Base class for immutable literal vars."""

    def __init_subclass__(cls, **kwargs):
        """Initialize the subclass.

        Args:
            **kwargs: Additional keyword arguments.

        Raises:
            TypeError: If the LiteralVar subclass does not have a corresponding Var subclass.
        """
        super().__init_subclass__(**kwargs)

        bases = cls.__bases__

        bases_normalized = [
            base if inspect.isclass(base) else get_origin(base) for base in bases
        ]

        possible_bases = [
            base
            for base in bases_normalized
            if issubclass(base, Var) and base != LiteralVar
        ]

        if not possible_bases:
            raise TypeError(
                f"LiteralVar subclass {cls} must have a base class that is a subclass of Var and not LiteralVar."
            )

        var_subclasses = [
            var_subclass
            for var_subclass in _var_subclasses
            if var_subclass.var_subclass in possible_bases
        ]

        if not var_subclasses:
            raise TypeError(
                f"LiteralVar {cls} must have a base class annotated with `python_types`."
            )

        if len(var_subclasses) != 1:
            raise TypeError(
                f"LiteralVar {cls} must have exactly one base class annotated with `python_types`."
            )

        var_subclass = var_subclasses[0]

        # Remove the old subclass, happens because __init_subclass__ is called twice
        # for each subclass. This is because of __slots__ in dataclasses.
        for var_literal_subclass in list(_var_literal_subclasses):
            if var_literal_subclass[1] is var_subclass:
                _var_literal_subclasses.remove(var_literal_subclass)

        _var_literal_subclasses.append((cls, var_subclass))

    @classmethod
    def create(  # pyright: ignore [reportArgumentType]
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

        for literal_subclass, var_subclass in _var_literal_subclasses[::-1]:
            if isinstance(value, var_subclass.python_types):
                return literal_subclass.create(value, _var_data=_var_data)

        from reflex.event import EventHandler
        from reflex.utils.format import get_event_handler_parts

        from .object import LiteralObjectVar
        from .sequence import LiteralStringVar

        if isinstance(value, EventHandler):
            return Var(_js_expr=".".join(filter(None, get_event_handler_parts(value))))

        serialized_value = serializers.serialize(value)
        if serialized_value is not None:
            if isinstance(serialized_value, Mapping):
                return LiteralObjectVar.create(
                    serialized_value,
                    _var_type=type(value),
                    _var_data=_var_data,
                )
            if isinstance(serialized_value, str):
                return LiteralStringVar.create(
                    serialized_value, _var_type=type(value), _var_data=_var_data
                )
            return LiteralVar.create(serialized_value, _var_data=_var_data)

        if isinstance(value, Base):
            # get the fields of the pydantic class
            fields = value.__fields__.keys()
            one_level_dict = {field: getattr(value, field) for field in fields}

            return LiteralObjectVar.create(
                {
                    field: value
                    for field, value in one_level_dict.items()
                    if not callable(value)
                },
                _var_type=type(value),
                _var_data=_var_data,
            )

        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return LiteralObjectVar.create(
                {
                    k: (None if callable(v) else v)
                    for k, v in dataclasses.asdict(value).items()
                },
                _var_type=type(value),
                _var_data=_var_data,
            )

        if isinstance(value, range):
            return ArrayVar.range(value.start, value.stop, value.step)

        raise TypeError(
            f"Unsupported type {type(value)} for LiteralVar. Tried to create a LiteralVar from {value}."
        )

    def __post_init__(self):
        """Post-initialize the var."""

    @property
    def _var_value(self) -> Any:
        raise NotImplementedError(
            "LiteralVar subclasses must implement the _var_value property."
        )

    def json(self) -> str:
        """Serialize the var to a JSON string.

        Raises:
            NotImplementedError: If the method is not implemented.
        """
        raise NotImplementedError(
            "LiteralVar subclasses must implement the json method."
        )


@serializers.serializer
def serialize_literal(value: LiteralVar):
    """Serialize a Literal type.

    Args:
        value: The Literal to serialize.

    Returns:
        The serialized Literal.
    """
    return value._var_value


def get_python_literal(value: Union[LiteralVar, Any]) -> Any | None:
    """Get the Python literal value.

    Args:
        value: The value to get the Python literal value of.

    Returns:
        The Python literal value.
    """
    if isinstance(value, LiteralVar):
        return value._var_value
    if isinstance(value, Var):
        return None
    return value


def validate_arg(type_hint: GenericType) -> Callable[[Any], str | None]:
    """Create a validator for an argument.

    Args:
        type_hint: The type hint of the argument.

    Returns:
        The validator.
    """

    def validate(value: Any):
        if isinstance(value, LiteralVar):
            if not _isinstance(value._var_value, type_hint):
                return f"Expected {type_hint} but got {value._var_value} of type {type(value._var_value)}."
        elif isinstance(value, Var):
            if not typehint_issubclass(value._var_type, type_hint):
                return f"Expected {type_hint} but got {value._var_type}."
        else:
            if not _isinstance(value, type_hint):
                return f"Expected {type_hint} but got {value} of type {type(value)}."

    return validate


P = ParamSpec("P")
T = TypeVar("T")
V1 = TypeVar("V1")
V2 = TypeVar("V2")
V3 = TypeVar("V3")
V4 = TypeVar("V4")
V5 = TypeVar("V5")


class TypeComputer(Protocol):
    """A protocol for type computers."""

    def __call__(self, *args: Var) -> Tuple[GenericType, Union[TypeComputer, None]]:
        """Compute the type of the operation.

        Args:
            *args: The arguments to compute the type of.
        """
        ...


@overload
def var_operation(
    func: Callable[[Var[V1], Var[V2], Var[V3]], CustomVarOperationReturn[T]],
) -> ArgsFunctionOperation[ReflexCallable[[V1, V2, V3], T]]: ...


@overload
def var_operation(
    func: Callable[[Var[V1], Var[V2], VarWithDefault[V3]], CustomVarOperationReturn[T]],
) -> ArgsFunctionOperation[ReflexCallable[[V1, V2, VarWithDefault[V3]], T]]: ...


@overload
def var_operation(
    func: Callable[
        [
            Var[V1],
            VarWithDefault[V2],
            VarWithDefault[V3],
        ],
        CustomVarOperationReturn[T],
    ],
) -> ArgsFunctionOperation[
    ReflexCallable[
        [
            V1,
            VarWithDefault[V2],
            VarWithDefault[V3],
        ],
        T,
    ]
]: ...


@overload
def var_operation(
    func: Callable[
        [
            VarWithDefault[V1],
            VarWithDefault[V2],
            VarWithDefault[V3],
        ],
        CustomVarOperationReturn[T],
    ],
) -> ArgsFunctionOperation[
    ReflexCallable[
        [
            VarWithDefault[V1],
            VarWithDefault[V1],
            VarWithDefault[V1],
        ],
        T,
    ]
]: ...


@overload
def var_operation(
    func: Callable[[Var[V1], Var[V2]], CustomVarOperationReturn[T]],
) -> ArgsFunctionOperation[ReflexCallable[[V1, V2], T]]: ...


@overload
def var_operation(
    func: Callable[
        [
            Var[V1],
            VarWithDefault[V2],
        ],
        CustomVarOperationReturn[T],
    ],
) -> ArgsFunctionOperation[
    ReflexCallable[
        [
            V1,
            VarWithDefault[V2],
        ],
        T,
    ]
]: ...


@overload
def var_operation(
    func: Callable[
        [
            VarWithDefault[V1],
            VarWithDefault[V2],
        ],
        CustomVarOperationReturn[T],
    ],
) -> ArgsFunctionOperation[
    ReflexCallable[
        [
            VarWithDefault[V1],
            VarWithDefault[V2],
        ],
        T,
    ]
]: ...


@overload
def var_operation(
    func: Callable[[Var[V1]], CustomVarOperationReturn[T]],
) -> ArgsFunctionOperation[ReflexCallable[[V1], T]]: ...


@overload
def var_operation(
    func: Callable[
        [VarWithDefault[V1]],
        CustomVarOperationReturn[T],
    ],
) -> ArgsFunctionOperation[
    ReflexCallable[
        [VarWithDefault[V1]],
        T,
    ]
]: ...


@overload
def var_operation(
    func: Callable[[], CustomVarOperationReturn[T]],
) -> ArgsFunctionOperation[ReflexCallable[[], T]]: ...


def var_operation(
    func: Callable[..., CustomVarOperationReturn[T]],
) -> ArgsFunctionOperation[ReflexCallable[..., T]]:
    """Decorator for creating a var operation.

    Example:
    ```python
    @var_operation
    def add(a: Var[int], b: Var[int]):
        return var_operation_return(f"{a} + {b}")
    ```

    Args:
        func: The function to decorate.

    Returns:
        The decorated function.

    Raises:
        TypeError: If the function has keyword-only arguments or arguments without Var type hints.
    """
    from .function import ArgsFunctionOperation, ReflexCallable

    func_name = func.__name__

    func_arg_spec = inspect.getfullargspec(func)
    func_signature = inspect.signature(func)

    if func_arg_spec.kwonlyargs:
        raise TypeError(f"Function {func_name} cannot have keyword-only arguments.")
    if func_arg_spec.varargs:
        raise TypeError(f"Function {func_name} cannot have variable arguments.")

    arg_names = func_arg_spec.args

    arg_default_values: Sequence[inspect.Parameter.empty | VarWithDefault] = tuple(
        (
            default_value
            if isinstance(
                (default_value := func_signature.parameters[arg_name].default),
                VarWithDefault,
            )
            else inspect.Parameter.empty()
        )
        for arg_name in arg_names
    )

    type_hints = get_type_hints(func)

    if not all(
        (get_origin((type_hint := type_hints.get(arg_name, Any))) or type_hint)
        in (Var, VarWithDefault)
        and len(get_args(type_hint)) <= 1
        for arg_name in arg_names
    ):
        raise TypeError(
            f"Function {func_name} must have type hints of the form `Var[Type]`."
        )

    args_with_type_hints = tuple(
        (arg_name, (args[0] if (args := get_args(type_hints[arg_name])) else Any))
        for arg_name in arg_names
    )

    arg_vars = tuple(
        (
            Var("_" + arg_name, _var_type=arg_python_type)
            if not isinstance(arg_python_type, TypeVar)
            else Var("_" + arg_name)
        )
        for arg_name, arg_python_type in args_with_type_hints
    )

    custom_operation_return = func(*arg_vars)

    def simplified_operation(*args):
        return func(*args)._js_expr

    args_operation = ArgsFunctionOperation.create(
        tuple(map(str, arg_vars)),
        custom_operation_return,
        default_values=arg_default_values,
        validators=tuple(
            validate_arg(arg_type)
            if not isinstance(arg_type, TypeVar)
            else validate_arg(arg_type.__bound__ or Any)
            for _, arg_type in args_with_type_hints
        ),
        function_name=func_name,
        type_computer=custom_operation_return._type_computer,
        _raw_js_function=custom_operation_return._raw_js_function,
        _original_var_operation=simplified_operation,
        _var_type=ReflexCallable[
            tuple(  # pyright: ignore [reportInvalidTypeArguments]
                arg_python_type
                if isinstance(arg_default_values[i], inspect.Parameter)
                else VarWithDefault[arg_python_type]
                for i, (_, arg_python_type) in enumerate(args_with_type_hints)
            ),
            custom_operation_return._var_type,
        ],
    )

    return args_operation


def figure_out_type(value: Any) -> types.GenericType:
    """Figure out the type of the value.

    Args:
        value: The value to figure out the type of.

    Returns:
        The type of the value.
    """
    if isinstance(value, Var):
        return value._var_type
    type_ = type(value)
    if has_args(type_):
        return type_
    if isinstance(value, list):
        return List[unionize(*(figure_out_type(v) for v in value))]
    if isinstance(value, set):
        return Set[unionize(*(figure_out_type(v) for v in value))]
    if isinstance(value, tuple):
        return Tuple[unionize(*(figure_out_type(v) for v in value)), ...]
    if isinstance(value, Mapping):
        return Mapping[
            unionize(*(figure_out_type(k) for k in value)),
            unionize(*(figure_out_type(v) for v in value.values())),
        ]
    return type(value)


GLOBAL_CACHE = {}


class cached_property:  # noqa: N801
    """A cached property that caches the result of the function."""

    def __init__(self, func: Callable):
        """Initialize the cached_property.

        Args:
            func: The function to cache.
        """
        self._func = func
        self._attrname = None

    def __set_name__(self, owner: Any, name: str):
        """Set the name of the cached property.

        Args:
            owner: The owner of the cached property.
            name: The name of the cached property.

        Raises:
            TypeError: If the cached property is assigned to two different names.
        """
        if self._attrname is None:
            self._attrname = name

            original_del = getattr(owner, "__del__", None)

            def delete_property(this: Any):
                """Delete the cached property.

                Args:
                    this: The object to delete the cached property from.
                """
                cached_field_name = "_reflex_cache_" + name
                try:
                    unique_id = object.__getattribute__(this, cached_field_name)
                except AttributeError:
                    if original_del is not None:
                        original_del(this)
                    return
                if unique_id in GLOBAL_CACHE:
                    del GLOBAL_CACHE[unique_id]

                if original_del is not None:
                    original_del(this)

            owner.__del__ = delete_property

        elif name != self._attrname:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                f"({self._attrname!r} and {name!r})."
            )

    def __get__(self, instance: Any, owner: Type | None = None):
        """Get the cached property.

        Args:
            instance: The instance to get the cached property from.
            owner: The owner of the cached property.

        Returns:
            The cached property.

        Raises:
            TypeError: If the class does not have __set_name__.
        """
        if self._attrname is None:
            raise TypeError(
                "Cannot use cached_property on a class without __set_name__."
            )
        cached_field_name = "_reflex_cache_" + self._attrname
        try:
            unique_id = object.__getattribute__(instance, cached_field_name)
        except AttributeError:
            unique_id = uuid.uuid4().int
            object.__setattr__(instance, cached_field_name, unique_id)
        if unique_id not in GLOBAL_CACHE:
            GLOBAL_CACHE[unique_id] = self._func(instance)
        return GLOBAL_CACHE[unique_id]


cached_property_no_lock = cached_property


class CachedVarOperation:
    """Base class for cached var operations to lower boilerplate code."""

    def __post_init__(self):
        """Post-initialize the CachedVarOperation."""
        object.__delattr__(self, "_js_expr")

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute.
        """
        if name == "_js_expr":
            return self._cached_var_name

        parent_classes = inspect.getmro(type(self))

        next_class = parent_classes[parent_classes.index(CachedVarOperation) + 1]

        return next_class.__getattr__(self, name)

    def _get_all_var_data(self) -> VarData | None:
        """Get all VarData associated with the Var.

        Returns:
            The VarData of the components and all of its children.
        """
        return self._cached_get_all_var_data

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get the cached VarData.

        Returns:
            The cached VarData.
        """
        return VarData.merge(
            *(
                value._get_all_var_data() if isinstance(value, Var) else None
                for value in (
                    getattr(self, field.name)
                    for field in dataclasses.fields(self)  # pyright: ignore [reportArgumentType]
                )
            ),
            self._var_data,
        )

    def __hash__(self) -> int:
        """Calculate the hash of the object.

        Returns:
            The hash of the object.
        """
        return hash(
            (
                type(self).__name__,
                *[
                    getattr(self, field.name)
                    for field in dataclasses.fields(self)  # pyright: ignore [reportArgumentType]
                    if field.name not in ["_js_expr", "_var_data", "_var_type"]
                ],
            )
        )


RETURN_TYPE = TypeVar("RETURN_TYPE")


class FakeComputedVarBaseClass(property):
    """A fake base class for ComputedVar to avoid inheriting from property."""

    __pydantic_run_validation__ = False


def is_computed_var(obj: Any) -> TypeGuard[ComputedVar]:
    """Check if the object is a ComputedVar.

    Args:
        obj: The object to check.

    Returns:
        Whether the object is a ComputedVar.
    """
    return isinstance(obj, FakeComputedVarBaseClass)


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class ComputedVar(Var[RETURN_TYPE]):
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
    )  # pyright: ignore [reportAssignmentType]

    def __init__(
        self,
        fget: Callable[[BASE_STATE], RETURN_TYPE],
        initial_value: RETURN_TYPE | types.Unset = types.Unset(),
        cache: bool = True,
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
            UntypedComputedVarError: If the computed var is untyped.
        """
        hint = kwargs.pop("return_type", None) or get_type_hints(fget).get(
            "return", Any
        )

        if hint is Any:
            raise UntypedComputedVarError(var_name=fget.__name__)
        kwargs.setdefault("_js_expr", fget.__name__)
        kwargs.setdefault("_var_type", hint)

        Var.__init__(
            self,
            _js_expr=kwargs.pop("_js_expr"),
            _var_type=kwargs.pop("_var_type"),
            _var_data=kwargs.pop("_var_data", None),
        )

        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {tuple(kwargs)}")

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
            {dep._js_expr if isinstance(dep, Var) else dep for dep in deps},
        )
        object.__setattr__(self, "_auto_deps", auto_deps)

        object.__setattr__(self, "_fget", fget)

    @override
    def _replace(
        self,
        _var_type: Any = None,
        merge_var_data: VarData | None = None,
        **kwargs: Any,
    ) -> Self:
        """Replace the attributes of the ComputedVar.

        Args:
            _var_type: ignored in ComputedVar.
            merge_var_data: VarData to merge into the existing VarData.
            **kwargs: Var fields to update.

        Returns:
            The new ComputedVar instance.

        Raises:
            TypeError: If kwargs contains keys that are not allowed.
        """
        field_values = {
            "fget": kwargs.pop("fget", self._fget),
            "initial_value": kwargs.pop("initial_value", self._initial_value),
            "cache": kwargs.pop("cache", self._cache),
            "deps": kwargs.pop("deps", self._static_deps),
            "auto_deps": kwargs.pop("auto_deps", self._auto_deps),
            "interval": kwargs.pop("interval", self._update_interval),
            "backend": kwargs.pop("backend", self._backend),
            "_js_expr": kwargs.pop("_js_expr", self._js_expr),
            "_var_type": kwargs.pop("_var_type", self._var_type),
            "_var_data": kwargs.pop(
                "_var_data", VarData.merge(self._var_data, merge_var_data)
            ),
            "return_type": kwargs.pop("return_type", self._var_type),
        }

        if kwargs:
            unexpected_kwargs = ", ".join(kwargs.keys())
            raise TypeError(f"Unexpected keyword arguments: {unexpected_kwargs}")

        return type(self)(**field_values)

    @property
    def _cache_attr(self) -> str:
        """Get the attribute used to cache the value on the instance.

        Returns:
            An attribute name.
        """
        return f"__cached_{self._js_expr}"

    @property
    def _last_updated_attr(self) -> str:
        """Get the attribute used to store the last updated timestamp.

        Returns:
            An attribute name.
        """
        return f"__last_updated_{self._js_expr}"

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
        self: ComputedVar[int] | ComputedVar[float],
        instance: None,
        owner: Type,
    ) -> NumberVar: ...

    @overload
    def __get__(
        self: ComputedVar[str],
        instance: None,
        owner: Type,
    ) -> StringVar: ...

    @overload
    def __get__(
        self: ComputedVar[MAPPING_TYPE],
        instance: None,
        owner: Type,
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def __get__(
        self: ComputedVar[SEQUENCE_TYPE],
        instance: None,
        owner: Type,
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def __get__(self, instance: None, owner: Type) -> ComputedVar[RETURN_TYPE]: ...

    @overload
    def __get__(self, instance: BaseState, owner: Type) -> RETURN_TYPE: ...

    def __get__(self, instance: BaseState | None, owner: Type):
        """Get the ComputedVar value.

        If the value is already cached on the instance, return the cached value.

        Args:
            instance: the instance of the class accessing this computed var.
            owner: the class that this descriptor is attached to.

        Returns:
            The value of the var for the given instance.
        """
        if instance is None:
            state_where_defined = owner
            while self._js_expr in state_where_defined.inherited_vars:
                state_where_defined = state_where_defined.get_parent_state()

            field_name = (
                format_state_name(state_where_defined.get_full_name())
                + "."
                + self._js_expr
            )

            return dispatch(
                field_name,
                var_data=VarData.from_state(state_where_defined, self._js_expr),
                result_var_type=self._var_type,
                existing_var=self,
            )

        if not self._cache:
            value = self.fget(instance)
        else:
            # handle caching
            if not hasattr(instance, self._cache_attr) or self.needs_update(instance):
                # Set cache attr on state instance.
                setattr(instance, self._cache_attr, self.fget(instance))
                # Ensure the computed var gets serialized to redis.
                instance._was_touched = True
                # Set the last updated timestamp on the state instance.
                setattr(instance, self._last_updated_attr, datetime.datetime.now())
            value = getattr(instance, self._cache_attr)

        if not _isinstance(value, self._var_type):
            console.error(
                f"Computed var '{type(instance).__name__}.{self._js_expr}' must return"
                f" type '{self._var_type}', got '{type(value)}'."
            )

        return value

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
            obj = cast(FunctionType, obj.func)  # pyright: ignore [reportAttributeAccessIssue]
        with contextlib.suppress(AttributeError):
            # unbox EventHandler
            obj = cast(FunctionType, obj.fn)  # pyright: ignore [reportAttributeAccessIssue]

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
                        f"Cached var {self!s} cannot access arbitrary state via `{instruction.argval}`."
                    )
                if callable(ref_obj):
                    # recurse into callable attributes
                    d.update(
                        self._deps(
                            objclass=objclass,
                            obj=ref_obj,  # pyright: ignore [reportArgumentType]
                        )
                    )
                # recurse into property fget functions
                elif isinstance(ref_obj, property) and not isinstance(
                    ref_obj, ComputedVar
                ):
                    d.update(
                        self._deps(
                            objclass=objclass,
                            obj=ref_obj.fget,  # pyright: ignore [reportArgumentType]
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

    def mark_dirty(self, instance: BaseState) -> None:
        """Mark this ComputedVar as dirty.

        Args:
            instance: the state instance that needs to recompute the value.
        """
        with contextlib.suppress(AttributeError):
            delattr(instance, self._cache_attr)

    def _determine_var_type(self) -> GenericType:
        """Get the type of the var.

        Returns:
            The type of the var.
        """
        hints = get_type_hints(self._fget)
        if "return" in hints:
            return hints["return"]
        return Any  # pyright: ignore [reportReturnType]

    @property
    def __class__(self) -> Type:
        """Get the class of the var.

        Returns:
            The class of the var.
        """
        return FakeComputedVarBaseClass

    @property
    def fget(self) -> Callable[[BaseState], RETURN_TYPE]:
        """Get the getter function.

        Returns:
            The getter function.
        """
        return self._fget


class DynamicRouteVar(ComputedVar[Union[str, List[str]]]):
    """A ComputedVar that represents a dynamic route."""

    pass


if TYPE_CHECKING:
    BASE_STATE = TypeVar("BASE_STATE", bound=BaseState)


@overload
def computed_var(
    fget: None = None,
    initial_value: Any | types.Unset = types.Unset(),
    cache: bool = True,
    deps: Optional[List[Union[str, Var]]] = None,
    auto_deps: bool = True,
    interval: Optional[Union[datetime.timedelta, int]] = None,
    backend: bool | None = None,
    **kwargs,
) -> Callable[[Callable[[BASE_STATE], RETURN_TYPE]], ComputedVar[RETURN_TYPE]]: ...  # pyright: ignore [reportInvalidTypeVarUse]


@overload
def computed_var(
    fget: Callable[[BASE_STATE], RETURN_TYPE],
    initial_value: RETURN_TYPE | types.Unset = types.Unset(),
    cache: bool = True,
    deps: Optional[List[Union[str, Var]]] = None,
    auto_deps: bool = True,
    interval: Optional[Union[datetime.timedelta, int]] = None,
    backend: bool | None = None,
    **kwargs,
) -> ComputedVar[RETURN_TYPE]: ...


def computed_var(
    fget: Callable[[BASE_STATE], Any] | None = None,
    initial_value: Any | types.Unset = types.Unset(),
    cache: bool = True,
    deps: Optional[List[Union[str, Var]]] = None,
    auto_deps: bool = True,
    interval: Optional[Union[datetime.timedelta, int]] = None,
    backend: bool | None = None,
    **kwargs,
) -> ComputedVar | Callable[[Callable[[BASE_STATE], Any]], ComputedVar]:
    """A ComputedVar decorator with or without kwargs.

    Args:
        fget: The getter function.
        initial_value: The initial value of the computed var.
        cache: Whether to cache the computed value.
        deps: Explicit var dependencies to track.
        auto_deps: Whether var dependencies should be auto-determined.
        interval: Interval at which the computed var should be updated.
        backend: Whether the computed var is a backend var.
        **kwargs: additional attributes to set on the instance

    Returns:
        A ComputedVar instance.

    Raises:
        ValueError: If caching is disabled and an update interval is set.
        VarDependencyError: If user supplies dependencies without caching.
    """
    if cache is False and interval is not None:
        raise ValueError("Cannot set update interval without caching.")

    if cache is False and (deps is not None or auto_deps is False):
        raise VarDependencyError("Cannot track dependencies without caching.")

    if fget is not None:
        return ComputedVar(fget, cache=cache)

    def wrapper(fget: Callable[[BASE_STATE], Any]) -> ComputedVar:
        return ComputedVar(
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


RETURN = TypeVar("RETURN")


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class CustomVarOperationReturn(Var[RETURN]):
    """Base class for custom var operations."""

    _type_computer: TypeComputer | None = dataclasses.field(default=None)
    _raw_js_function: str | None = dataclasses.field(default=None)

    @classmethod
    def create(
        cls,
        js_expression: str,
        _var_type: Type[RETURN] | None = None,
        _type_computer: TypeComputer | None = None,
        _var_data: VarData | None = None,
        _raw_js_function: str | None = None,
    ) -> CustomVarOperationReturn[RETURN]:
        """Create a CustomVarOperation.

        Args:
            js_expression: The JavaScript expression to evaluate.
            _var_type: The type of the var.
            _type_computer: A function to compute the type of the var given the arguments.
            _var_data: Additional hooks and imports associated with the Var.
            _raw_js_function: If provided, it will be used when the operation is being called with all of its arguments at once.

        Returns:
            The CustomVarOperation.
        """
        return CustomVarOperationReturn(
            _js_expr=js_expression,
            _var_type=_var_type or Any,
            _type_computer=_type_computer,
            _var_data=_var_data,
            _raw_js_function=_raw_js_function,
        )


def var_operation_return(
    js_expression: str,
    var_type: Type[RETURN] | None = None,
    type_computer: Optional[TypeComputer] = None,
    var_data: VarData | None = None,
    _raw_js_function: str | None = None,
) -> CustomVarOperationReturn[RETURN]:
    """Shortcut for creating a CustomVarOperationReturn.

    Args:
        js_expression: The JavaScript expression to evaluate.
        var_type: The type of the var.
        type_computer: A function to compute the type of the var given the arguments.
        var_data: Additional hooks and imports associated with the Var.
        _raw_js_function: If provided, it will be used when the operation is being called with all of its arguments at once.

    Returns:
        The CustomVarOperationReturn.
    """
    return CustomVarOperationReturn.create(
        js_expression=js_expression,
        _var_type=var_type,
        _type_computer=type_computer,
        _var_data=var_data,
        _raw_js_function=_raw_js_function,
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class CustomVarOperation(CachedVarOperation, Var[T]):
    """Base class for custom var operations."""

    _name: str = dataclasses.field(default="")

    _args: Tuple[Tuple[str, Var], ...] = dataclasses.field(default_factory=tuple)

    _return: CustomVarOperationReturn[T] = dataclasses.field(
        default_factory=lambda: CustomVarOperationReturn.create("")
    )

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """Get the cached var name.

        Returns:
            The cached var name.
        """
        return str(self._return)

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get the cached VarData.

        Returns:
            The cached VarData.
        """
        return VarData.merge(
            *(arg[1]._get_all_var_data() for arg in self._args),
            self._return._get_all_var_data(),
            self._var_data,
        )

    @classmethod
    def create(
        cls,
        name: str,
        args: Tuple[Tuple[str, Var], ...],
        return_var: CustomVarOperationReturn[T],
        _var_data: VarData | None = None,
    ) -> CustomVarOperation[T]:
        """Create a CustomVarOperation.

        Args:
            name: The name of the operation.
            args: The arguments to the operation.
            return_var: The return var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The CustomVarOperation.
        """
        return CustomVarOperation(
            _js_expr="",
            _var_type=return_var._var_type,
            _var_data=_var_data,
            _name=name,
            _args=args,
            _return=return_var,
        )


class NoneVar(Var[None], python_types=type(None)):
    """A var representing None."""


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralNoneVar(LiteralVar, NoneVar):
    """A var representing None."""

    _var_value: None = None

    def json(self) -> str:
        """Serialize the var to a JSON string.

        Returns:
            The JSON string.
        """
        return "null"

    @classmethod
    def create(
        cls,
        value: None = None,
        _var_data: VarData | None = None,
    ) -> LiteralNoneVar:
        """Create a var from a value.

        Args:
            value: The value of the var. Must be None. Existed for compatibility with LiteralVar.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        return LiteralNoneVar(
            _js_expr="null",
            _var_type=None,
            _var_data=_var_data,
        )


def get_to_operation(var_subclass: Type[Var]) -> Type[ToOperation]:
    """Get the ToOperation class for a given Var subclass.

    Args:
        var_subclass: The Var subclass.

    Returns:
        The ToOperation class.

    Raises:
        ValueError: If the ToOperation class cannot be found.
    """
    possible_classes = [
        saved_var_subclass.to_var_subclass
        for saved_var_subclass in _var_subclasses
        if saved_var_subclass.var_subclass is var_subclass
    ]
    if not possible_classes:
        raise ValueError(f"Could not find ToOperation for {var_subclass}.")
    return possible_classes[0]


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class StateOperation(CachedVarOperation, Var):
    """A var operation that accesses a field on an object."""

    _state_name: str = dataclasses.field(default="")
    _field: Var = dataclasses.field(default_factory=lambda: LiteralNoneVar.create())

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """Get the cached var name.

        Returns:
            The cached var name.
        """
        return f"{self._state_name!s}.{self._field!s}"

    def __getattr__(self, name: str) -> Any:
        """Get an attribute of the var.

        Args:
            name: The name of the attribute.

        Returns:
            The attribute.
        """
        if name == "_js_expr":
            return self._cached_var_name

        return getattr(self._field, name)

    @classmethod
    def create(
        cls,
        state_name: str,
        field: Var,
        _var_data: VarData | None = None,
    ) -> StateOperation:
        """Create a DotOperation.

        Args:
            state_name: The name of the state.
            field: The field of the state.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The DotOperation.
        """
        return StateOperation(
            _js_expr="",
            _var_type=field._var_type,
            _var_data=_var_data,
            _state_name=state_name,
            _field=field,
        )


def get_uuid_string_var() -> Var:
    """Return a Var that generates a single memoized UUID via .web/utils/state.js.

    useMemo with an empty dependency array ensures that the generated UUID is
    consistent across re-renders of the component.

    Returns:
        A Var that generates a UUID at runtime.
    """
    from reflex.utils.imports import ImportVar
    from reflex.vars import Var

    unique_uuid_var = get_unique_variable_name()
    unique_uuid_var_data = VarData(
        imports={
            f"$/{constants.Dirs.STATE_PATH}": {ImportVar(tag="generateUUID")},  # pyright: ignore [reportArgumentType]
            "react": "useMemo",
        },
        hooks={f"const {unique_uuid_var} = useMemo(generateUUID, [])": None},
    )

    return Var(
        _js_expr=unique_uuid_var,
        _var_type=str,
        _var_data=unique_uuid_var_data,
    )


# Set of unique variable names.
USED_VARIABLES = set()


def get_unique_variable_name() -> str:
    """Get a unique variable name.

    Returns:
        The unique variable name.
    """
    name = "".join([random.choice(string.ascii_lowercase) for _ in range(8)])
    if name not in USED_VARIABLES:
        USED_VARIABLES.add(name)
        return name
    return get_unique_variable_name()


# Compile regex for finding reflex var tags.
_decode_var_pattern_re = (
    rf"{constants.REFLEX_VAR_OPENING_TAG}(.*?){constants.REFLEX_VAR_CLOSING_TAG}"
)
_decode_var_pattern = re.compile(_decode_var_pattern_re, flags=re.DOTALL)

# Defined global immutable vars.
_global_vars: Dict[int, Var] = {}


def _extract_var_data(value: Iterable) -> list[VarData | None]:
    """Extract the var imports and hooks from an iterable containing a Var.

    Args:
        value: The iterable to extract the VarData from

    Returns:
        The extracted VarDatas.
    """
    from reflex.style import Style
    from reflex.vars import Var

    var_datas = []
    with contextlib.suppress(TypeError):
        for sub in value:
            if isinstance(sub, Var):
                var_datas.append(sub._var_data)
            elif not isinstance(sub, str):
                # Recurse into dict values.
                if (
                    (values_fn := getattr(sub, "values", None)) is not None
                    and callable(values_fn)
                    and isinstance((values := values_fn()), Iterable)
                ):
                    var_datas.extend(_extract_var_data(values))
                # Recurse into iterable values (or dict keys).
                var_datas.extend(_extract_var_data(sub))

    # Style objects should already have _var_data.
    if isinstance(value, Style):
        var_datas.append(value._var_data)
    else:
        # Recurse when value is a dict itself.
        values_fn = getattr(value, "values", None)
        if callable(values_fn) and isinstance((values := values_fn()), Iterable):
            var_datas.extend(_extract_var_data(values))
    return var_datas


dispatchers: Dict[GenericType, Callable[[Var], Var]] = {}


def transform(fn: Callable[[Var], Var]) -> Callable[[Var], Var]:
    """Register a function to transform a Var.

    Args:
        fn: The function to register.

    Returns:
        The decorator.

    Raises:
        TypeError: If the return type of the function is not a Var.
        TypeError: If the Var return type does not have a generic type.
        ValueError: If a function for the generic type is already registered.
    """
    return_type = fn.__annotations__["return"]

    origin = get_origin(return_type)

    if origin is not Var:
        raise TypeError(
            f"Expected return type of {fn.__name__} to be a Var, got {origin}."
        )

    generic_args = get_args(return_type)

    if not generic_args:
        raise TypeError(
            f"Expected Var return type of {fn.__name__} to have a generic type."
        )

    generic_type = get_origin(generic_args[0]) or generic_args[0]

    if generic_type in dispatchers:
        raise ValueError(f"Function for {generic_type} already registered.")

    dispatchers[generic_type] = fn

    return fn


def generic_type_to_actual_type_map(
    generic_type: GenericType, actual_type: GenericType
) -> Dict[TypeVar, GenericType]:
    """Map the generic type to the actual type.

    Args:
        generic_type: The generic type.
        actual_type: The actual type.

    Returns:
        The mapping of type variables to actual types.

    Raises:
        TypeError: If the generic type and actual type do not match.
        TypeError: If the number of generic arguments and actual arguments do not match.
    """
    generic_origin = get_origin(generic_type) or generic_type
    actual_origin = get_origin(actual_type) or actual_type

    if generic_origin is not actual_origin:
        if isinstance(generic_origin, TypeVar):
            return {generic_origin: actual_origin}
        raise TypeError(
            f"Type mismatch: expected {generic_origin}, got {actual_origin}."
        )

    generic_args = get_args(generic_type)
    actual_args = get_args(actual_type)

    if len(generic_args) != len(actual_args):
        raise TypeError(
            f"Number of generic arguments mismatch: expected {len(generic_args)}, got {len(actual_args)}."
        )

    # call recursively for nested generic types and merge the results
    return {
        k: v
        for generic_arg, actual_arg in zip(generic_args, actual_args, strict=True)
        for k, v in generic_type_to_actual_type_map(generic_arg, actual_arg).items()
    }


def resolve_generic_type_with_mapping(
    generic_type: GenericType, type_mapping: Dict[TypeVar, GenericType]
):
    """Resolve a generic type with a type mapping.

    Args:
        generic_type: The generic type.
        type_mapping: The type mapping.

    Returns:
        The resolved generic type.
    """
    if isinstance(generic_type, TypeVar):
        return type_mapping.get(generic_type, generic_type)

    generic_origin = get_origin(generic_type) or generic_type

    generic_args = get_args(generic_type)

    if not generic_args:
        return generic_type

    mapping_for_older_python = {
        list: List,
        set: Set,
        dict: Dict,
        tuple: Tuple,
        frozenset: FrozenSet,
    }

    return mapping_for_older_python.get(generic_origin, generic_origin)[
        tuple(
            resolve_generic_type_with_mapping(arg, type_mapping) for arg in generic_args
        )
    ]


def resolve_arg_type_from_return_type(
    arg_type: GenericType, return_type: GenericType, actual_return_type: GenericType
) -> GenericType:
    """Resolve the argument type from the return type.

    Args:
        arg_type: The argument type.
        return_type: The return type.
        actual_return_type: The requested return type.

    Returns:
        The argument type without the generics that are resolved.
    """
    return resolve_generic_type_with_mapping(
        arg_type, generic_type_to_actual_type_map(return_type, actual_return_type)
    )


def dispatch(
    field_name: str,
    var_data: VarData,
    result_var_type: GenericType,
    existing_var: Var | None = None,
) -> Var:
    """Dispatch a Var to the appropriate transformation function.

    Args:
        field_name: The name of the field.
        var_data: The VarData associated with the Var.
        result_var_type: The type of the Var.
        existing_var: The existing Var to transform. Optional.

    Returns:
        The transformed Var.

    Raises:
        TypeError: If the return type of the function is not a Var.
        TypeError: If the Var return type does not have a generic type.
        TypeError: If the first argument of the function is not a Var.
        TypeError: If the first argument of the function does not have a generic type
    """
    result_origin_var_type = get_origin(result_var_type) or result_var_type

    if result_origin_var_type in dispatchers:
        fn = dispatchers[result_origin_var_type]
        fn_first_arg_type = next(
            iter(inspect.signature(fn).parameters.values())
        ).annotation

        fn_return = inspect.signature(fn).return_annotation

        fn_return_origin = get_origin(fn_return) or fn_return

        if fn_return_origin is not Var:
            raise TypeError(
                f"Expected return type of {fn.__name__} to be a Var, got {fn_return}."
            )

        fn_return_generic_args = get_args(fn_return)

        if not fn_return_generic_args:
            raise TypeError(f"Expected generic type of {fn_return} to be a type.")

        arg_origin = get_origin(fn_first_arg_type) or fn_first_arg_type

        if arg_origin is not Var:
            raise TypeError(
                f"Expected first argument of {fn.__name__} to be a Var, got {fn_first_arg_type}."
            )

        arg_generic_args = get_args(fn_first_arg_type)

        if not arg_generic_args:
            raise TypeError(
                f"Expected generic type of {fn_first_arg_type} to be a type."
            )

        arg_type = arg_generic_args[0]
        fn_return_type = fn_return_generic_args[0]

        var = (
            Var(
                field_name,
                _var_data=var_data,
                _var_type=resolve_arg_type_from_return_type(
                    arg_type, fn_return_type, result_var_type
                ),
            ).guess_type()
            if existing_var is None
            else existing_var._replace(
                _var_type=resolve_arg_type_from_return_type(
                    arg_type, fn_return_type, result_var_type
                ),
                _var_data=var_data,
                _js_expr=field_name,
            ).guess_type()
        )

        return fn(var)

    if existing_var is not None:
        return existing_var._replace(
            _js_expr=field_name,
            _var_data=var_data,
            _var_type=result_var_type,
        ).guess_type()
    return Var(
        field_name,
        _var_data=var_data,
        _var_type=result_var_type,
    ).guess_type()


V = TypeVar("V")

BASE_TYPE = TypeVar("BASE_TYPE", bound=Base)

FIELD_TYPE = TypeVar("FIELD_TYPE")
MAPPING_TYPE = TypeVar("MAPPING_TYPE", bound=Mapping)


class Field(Generic[FIELD_TYPE]):
    """Shadow class for Var to allow for type hinting in the IDE."""

    def __set__(self, instance: Any, value: FIELD_TYPE):
        """Set the Var.

        Args:
            instance: The instance of the class setting the Var.
            value: The value to set the Var to.
        """

    @overload
    def __get__(self: Field[bool], instance: None, owner: Any) -> BooleanVar: ...

    @overload
    def __get__(self: Field[int], instance: None, owner: Any) -> NumberVar[int]: ...

    @overload
    def __get__(self: Field[float], instance: None, owner: Any) -> NumberVar[float]: ...

    @overload
    def __get__(self: Field[str], instance: None, owner: Any) -> StringVar[str]: ...

    @overload
    def __get__(self: Field[None], instance: None, owner: Any) -> NoneVar: ...

    @overload
    def __get__(
        self: Field[Sequence[V]] | Field[Set[V]] | Field[List[V]],
        instance: None,
        owner: Any,
    ) -> ArrayVar[Sequence[V]]: ...

    @overload
    def __get__(
        self: Field[MAPPING_TYPE], instance: None, owner: Any
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def __get__(
        self: Field[BASE_TYPE], instance: None, owner: Any
    ) -> ObjectVar[BASE_TYPE]: ...

    @overload
    def __get__(self, instance: None, owner: Any) -> Var[FIELD_TYPE]: ...

    @overload
    def __get__(self, instance: Any, owner: Any) -> FIELD_TYPE: ...

    def __get__(self, instance: Any, owner: Any):  # pyright: ignore [reportInconsistentOverload]
        """Get the Var.

        Args:
            instance: The instance of the class accessing the Var.
            owner: The class that the Var is attached to.
        """


def field(value: FIELD_TYPE) -> Field[FIELD_TYPE]:
    """Create a Field with a value.

    Args:
        value: The value of the Field.

    Returns:
        The Field.
    """
    return value  # pyright: ignore [reportReturnType]


def and_operation(a: Var | Any, b: Var | Any) -> Var:
    """Perform a logical AND operation on two variables.

    Args:
        a: The first variable.
        b: The second variable.

    Returns:
        The result of the logical AND operation.
    """
    return _and_operation(a, b)


def or_operation(a: Var | Any, b: Var | Any) -> Var:
    """Perform a logical OR operation on two variables.

    Args:
        a: The first variable.
        b: The second variable.

    Returns:
        The result of the logical OR operation.
    """
    return _or_operation(a, b)


def passthrough_unary_type_computer(no_args: GenericType) -> TypeComputer:
    """Create a type computer for unary operations.

    Args:
        no_args: The type to return when no arguments are provided.

    Returns:
        The type computer.
    """

    def type_computer(*args: Var):
        if not args:
            return (no_args, type_computer)
        return (ReflexCallable[[], args[0]._var_type], None)

    return type_computer


def unary_type_computer(
    no_args: GenericType, computer: Callable[[Var], GenericType]
) -> TypeComputer:
    """Create a type computer for unary operations.

    Args:
        no_args: The type to return when no arguments are provided.
        computer: The function to compute the type.

    Returns:
        The type computer.
    """

    def type_computer(*args: Var):
        if not args:
            return (no_args, type_computer)
        return (ReflexCallable[[], computer(args[0])], None)

    return type_computer


def nary_type_computer(
    *types: GenericType, computer: Callable[..., GenericType]
) -> TypeComputer:
    """Create a type computer for n-ary operations.

    Args:
        types: The types to return when no arguments are provided.
        computer: The function to compute the type.

    Returns:
        The type computer.
    """

    def type_computer(*args: Var):
        if len(args) != len(types):
            return (
                types[len(args)],
                functools.partial(type_computer, *args),
            )
        return (
            ReflexCallable[[], computer(args)],
            None,
        )

    return type_computer


T_LOGICAL = TypeVar("T_LOGICAL")
U_LOGICAL = TypeVar("U_LOGICAL")


@var_operation
def _and_operation(
    a: Var[T_LOGICAL], b: Var[U_LOGICAL]
) -> CustomVarOperationReturn[Union[T_LOGICAL, U_LOGICAL]]:
    """Perform a logical AND operation on two variables.

    Args:
        a: The first variable.
        b: The second variable.

    Returns:
        The result of the logical AND operation.
    """
    return var_operation_return(
        js_expression=f"({a} && {b})",
        type_computer=nary_type_computer(
            ReflexCallable[[Any, Any], Any],
            ReflexCallable[[Any], Any],
            computer=lambda args: unionize(
                args[0]._var_type,
                args[1]._var_type,
            ),
        ),
    )


@var_operation
def _or_operation(
    a: Var[T_LOGICAL], b: Var[U_LOGICAL]
) -> CustomVarOperationReturn[Union[T_LOGICAL, U_LOGICAL]]:
    """Perform a logical OR operation on two variables.

    Args:
        a: The first variable.
        b: The second variable.

    Returns:
        The result ocomputerf the logical OR operation.
    """
    return var_operation_return(
        js_expression=f"({a} || {b})",
        type_computer=nary_type_computer(
            ReflexCallable[[Any, Any], Any],
            ReflexCallable[[Any], Any],
            computer=lambda args: unionize(
                args[0]._var_type,
                args[1]._var_type,
            ),
        ),
    )
