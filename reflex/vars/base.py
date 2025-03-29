"""Collection of base classes."""

from __future__ import annotations

import contextlib
import copy
import dataclasses
import datetime
import functools
import inspect
import json
import random
import re
import string
import uuid
import warnings
from types import CodeType, FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Coroutine,
    Dict,
    FrozenSet,
    Generic,
    Iterable,
    List,
    Literal,
    Mapping,
    NoReturn,
    ParamSpec,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeGuard,
    TypeVar,
    Union,
    cast,
    get_args,
    get_type_hints,
    overload,
)

from sqlalchemy.orm import DeclarativeBase
from typing_extensions import deprecated, override

from reflex import constants
from reflex.base import Base
from reflex.constants.compiler import Hooks
from reflex.utils import console, exceptions, imports, serializers, types
from reflex.utils.exceptions import (
    ComputedVarSignatureError,
    UntypedComputedVarError,
    VarAttributeError,
    VarDependencyError,
    VarTypeError,
)
from reflex.utils.format import format_state_name
from reflex.utils.imports import (
    ImmutableImportDict,
    ImmutableParsedImportDict,
    ImportDict,
    ImportVar,
    ParsedImportTuple,
    parse_imports,
)
from reflex.utils.types import (
    GenericType,
    Self,
    _isinstance,
    get_origin,
    has_args,
    safe_issubclass,
    unionize,
)

if TYPE_CHECKING:
    from reflex.components.component import BaseComponent
    from reflex.state import BaseState

    from .number import BooleanVar, LiteralBooleanVar, LiteralNumberVar, NumberVar
    from .object import LiteralObjectVar, ObjectVar
    from .sequence import ArrayVar, LiteralArrayVar, LiteralStringVar, StringVar


VAR_TYPE = TypeVar("VAR_TYPE", covariant=True)
OTHER_VAR_TYPE = TypeVar("OTHER_VAR_TYPE")
STRING_T = TypeVar("STRING_T", bound=str)
SEQUENCE_TYPE = TypeVar("SEQUENCE_TYPE", bound=Sequence)

warnings.filterwarnings("ignore", message="fields may not start with an underscore")


@dataclasses.dataclass(
    eq=False,
    frozen=True,
)
class VarSubclassEntry:
    """Entry for a Var subclass."""

    var_subclass: Type[Var]
    to_var_subclass: Type[ToOperation]
    python_types: tuple[GenericType, ...]


_var_subclasses: list[VarSubclassEntry] = []
_var_literal_subclasses: list[tuple[Type[LiteralVar], VarSubclassEntry]] = []


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
    imports: ParsedImportTuple = dataclasses.field(default_factory=tuple)

    # Hooks that need to be present in the component to render this var
    hooks: tuple[str, ...] = dataclasses.field(default_factory=tuple)

    # Dependencies of the var
    deps: tuple[Var, ...] = dataclasses.field(default_factory=tuple)

    # Position of the hook in the component
    position: Hooks.HookPosition | None = None

    # Components that are part of this var
    components: Tuple[BaseComponent, ...] = dataclasses.field(default_factory=tuple)

    def __init__(
        self,
        state: str = "",
        field_name: str = "",
        imports: ImmutableImportDict | ImmutableParsedImportDict | None = None,
        hooks: Mapping[str, VarData | None] | Sequence[str] | str | None = None,
        deps: list[Var] | None = None,
        position: Hooks.HookPosition | None = None,
        components: Iterable[BaseComponent] | None = None,
    ):
        """Initialize the var data.

        Args:
            state: The name of the enclosing state.
            field_name: The name of the field in the state.
            imports: Imports needed to render this var.
            hooks: Hooks that need to be present in the component to render this var.
            deps: Dependencies of the var for useCallback.
            position: Position of the hook in the component.
            components: Components that are part of this var.
        """
        if isinstance(hooks, str):
            hooks = [hooks]
        if not isinstance(hooks, dict):
            hooks = dict.fromkeys(hooks or [])
        immutable_imports: ParsedImportTuple = tuple(
            (k, tuple(v)) for k, v in parse_imports(imports or {}).items()
        )
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "field_name", field_name)
        object.__setattr__(self, "imports", immutable_imports)
        object.__setattr__(self, "hooks", tuple(hooks or {}))
        object.__setattr__(self, "deps", tuple(deps or []))
        object.__setattr__(self, "position", position or None)
        object.__setattr__(self, "components", tuple(components or []))

        if hooks and any(hooks.values()):
            merged_var_data = VarData.merge(self, *hooks.values())
            if merged_var_data is not None:
                object.__setattr__(self, "state", merged_var_data.state)
                object.__setattr__(self, "field_name", merged_var_data.field_name)
                object.__setattr__(self, "imports", merged_var_data.imports)
                object.__setattr__(self, "hooks", merged_var_data.hooks)
                object.__setattr__(self, "deps", merged_var_data.deps)
                object.__setattr__(self, "position", merged_var_data.position)
                object.__setattr__(self, "components", merged_var_data.components)

    def old_school_imports(self) -> ImportDict:
        """Return the imports as a mutable dict.

        Returns:
            The imports as a mutable dict.
        """
        return {k: list(v) for k, v in self.imports}

    def merge(*all: VarData | None) -> VarData | None:
        """Merge multiple var data objects.

        Args:
            *all: The var data objects to merge.

        Raises:
            ReflexError: If trying to merge VarData with different positions.

        Returns:
            The merged var data object.

        # noqa: DAR102 *all
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
        if positions:
            if len(positions) > 1:
                raise exceptions.ReflexError(
                    f"Cannot merge var data with different positions: {positions}"
                )
            position = positions[0]
        else:
            position = None

        components = tuple(
            component for var_data in all_var_datas for component in var_data.components
        )

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
        return bool(
            self.state
            or self.imports
            or self.hooks
            or self.field_name
            or self.deps
            or self.position
            or self.components
        )

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
        and not safe_issubclass(cls, Var)
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
    _var_data: VarData | None = dataclasses.field(default=None)

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
        python_types: tuple[GenericType, ...] | GenericType = types.Unset(),
        default_type: GenericType = types.Unset(),
        **kwargs,
    ):
        """Initialize the subclass.

        Args:
            python_types: The python types that the var represents.
            default_type: The default type of the var. Defaults to the first python type.
            **kwargs: Additional keyword arguments.
        """
        super().__init_subclass__(**kwargs)

        if python_types or default_type:
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

            new_to_var_operation_name = f"{cls.__name__.removesuffix('Var')}CastedVar"
            ToVarOperation.__qualname__ = (
                ToVarOperation.__qualname__.removesuffix(ToVarOperation.__name__)
                + new_to_var_operation_name
            )
            ToVarOperation.__name__ = new_to_var_operation_name

            _var_subclasses.append(VarSubclassEntry(cls, ToVarOperation, python_types))

    def __post_init__(self):
        """Post-initialize the var."""
        # Decode any inline Var markup and apply it to the instance
        _var_data, _js_expr = _decode_var_immutable(self._js_expr)

        if _var_data or _js_expr != self._js_expr:
            self.__init__(
                _js_expr=_js_expr,
                _var_type=self._var_type,
                _var_data=VarData.merge(self._var_data, _var_data),
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
    def create(  # pyright: ignore[reportOverlappingOverload]
        cls,
        value: NoReturn,
        _var_data: VarData | None = None,
    ) -> Var[Any]: ...

    @overload
    @classmethod
    def create(  # pyright: ignore[reportOverlappingOverload]
        cls,
        value: bool,
        _var_data: VarData | None = None,
    ) -> LiteralBooleanVar: ...

    @overload
    @classmethod
    def create(
        cls,
        value: int,
        _var_data: VarData | None = None,
    ) -> LiteralNumberVar[int]: ...

    @overload
    @classmethod
    def create(
        cls,
        value: float,
        _var_data: VarData | None = None,
    ) -> LiteralNumberVar[float]: ...

    @overload
    @classmethod
    def create(  # pyright: ignore [reportOverlappingOverload]
        cls,
        value: str,
        _var_data: VarData | None = None,
    ) -> LiteralStringVar: ...

    @overload
    @classmethod
    def create(  # pyright: ignore [reportOverlappingOverload]
        cls,
        value: STRING_T,
        _var_data: VarData | None = None,
    ) -> StringVar[STRING_T]: ...

    @overload
    @classmethod
    def create(  # pyright: ignore[reportOverlappingOverload]
        cls,
        value: None,
        _var_data: VarData | None = None,
    ) -> LiteralNoneVar: ...

    @overload
    @classmethod
    def create(
        cls,
        value: MAPPING_TYPE,
        _var_data: VarData | None = None,
    ) -> LiteralObjectVar[MAPPING_TYPE]: ...

    @overload
    @classmethod
    def create(
        cls,
        value: SEQUENCE_TYPE,
        _var_data: VarData | None = None,
    ) -> LiteralArrayVar[SEQUENCE_TYPE]: ...

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
    def to(self, output: Type[str]) -> StringVar: ...

    @overload
    def to(self, output: Type[bool]) -> BooleanVar: ...

    @overload
    def to(self, output: type[int] | type[float]) -> NumberVar: ...

    @overload
    def to(
        self,
        output: type[list] | type[tuple] | type[set],
    ) -> ArrayVar: ...

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
            if fixed_output_type in var_subclass.python_types or safe_issubclass(
                fixed_output_type, var_subclass.python_types
            ):
                return self.to(var_subclass.var_subclass, output)

        if fixed_output_type is None:
            return get_to_operation(NoneVar).create(self)  # pyright: ignore [reportReturnType]

        # Handle fixed_output_type being Base or a dataclass.
        if can_use_in_object_var(output):
            return self.to(ObjectVar, output)

        if inspect.isclass(output):
            for var_subclass in _var_subclasses[::-1]:
                if safe_issubclass(output, var_subclass.var_subclass):
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
            if not safe_issubclass(output, Var) or var_type is None:
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

    @overload
    def guess_type(self: Var[NoReturn]) -> Var[Any]: ...  # pyright: ignore [reportOverlappingOverload]

    @overload
    def guess_type(self: Var[str]) -> StringVar: ...

    @overload
    def guess_type(self: Var[bool]) -> BooleanVar: ...

    @overload
    def guess_type(self: Var[int] | Var[float] | Var[int | float]) -> NumberVar: ...

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
        if var_type is NoReturn:
            return self.to(Any)

        var_type = types.value_inside_optional(var_type)

        if var_type is Any:
            return self

        fixed_type = get_origin(var_type) or var_type

        if fixed_type in types.UnionTypes:
            inner_types = get_args(var_type)
            non_optional_inner_types = [
                types.value_inside_optional(inner_type) for inner_type in inner_types
            ]
            fixed_inner_types = [
                get_origin(inner_type) or inner_type
                for inner_type in non_optional_inner_types
            ]

            for var_subclass in _var_subclasses[::-1]:
                if all(
                    safe_issubclass(t, var_subclass.python_types)
                    for t in fixed_inner_types
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
            if safe_issubclass(fixed_type, var_subclass.python_types):
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
        if safe_issubclass(type_, str):
            return ""
        if safe_issubclass(type_, types.get_args(int | float)):
            return 0
        if safe_issubclass(type_, bool):
            return False
        if safe_issubclass(type_, list):
            return []
        if safe_issubclass(type_, Mapping):
            return {}
        if safe_issubclass(type_, tuple):
            return ()
        if types.is_dataframe(type_):
            try:
                import pandas as pd

                return pd.DataFrame()
            except ImportError as e:
                raise ImportError(
                    "Please install pandas to use dataframes in your app."
                ) from e
        return set() if safe_issubclass(type_, set) else None

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

        def setter(state: Any, value: Any):
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
                        f"{type(state).__name__}.{self._js_expr}: Failed conversion of {value!s} to '{self._var_type.__name__}'. Value not set.",
                    )
            else:
                setattr(state, actual_name, value)

        setter.__annotations__["value"] = self._var_type

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

        return equal_operation(self, other)

    def __ne__(self, other: Var | Any) -> BooleanVar:
        """Check if the current object is not equal to the given object.

        Parameters:
            other (Var | Any): The object to compare with.

        Returns:
            BooleanVar: A BooleanVar object representing the result of the comparison.
        """
        from .number import equal_operation

        return ~equal_operation(self, other)

    def bool(self) -> BooleanVar:
        """Convert the var to a boolean.

        Returns:
            The boolean var.
        """
        from .number import boolify

        return boolify(self)

    def __and__(
        self, other: Var[OTHER_VAR_TYPE] | Any
    ) -> Var[VAR_TYPE | OTHER_VAR_TYPE]:
        """Perform a logical AND operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical AND operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical AND operation.
        """
        return and_operation(self, other)

    def __rand__(
        self, other: Var[OTHER_VAR_TYPE] | Any
    ) -> Var[VAR_TYPE | OTHER_VAR_TYPE]:
        """Perform a logical AND operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical AND operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical AND operation.
        """
        return and_operation(other, self)

    def __or__(
        self, other: Var[OTHER_VAR_TYPE] | Any
    ) -> Var[VAR_TYPE | OTHER_VAR_TYPE]:
        """Perform a logical OR operation on the current instance and another variable.

        Args:
            other: The variable to perform the logical OR operation with.

        Returns:
            A `BooleanVar` object representing the result of the logical OR operation.
        """
        return or_operation(self, other)

    def __ror__(
        self, other: Var[OTHER_VAR_TYPE] | Any
    ) -> Var[VAR_TYPE | OTHER_VAR_TYPE]:
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
        return ~self.bool()

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
        first_endpoint: int | NumberVar,
        second_endpoint: int | NumberVar | None = None,
        step: int | NumberVar | None = None,
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

        return ArrayVar.range(first_endpoint, second_endpoint, step)

    if not TYPE_CHECKING:

        def __getitem__(self, key: Any) -> Var:
            """Get the item from the var.

            Args:
                key: The key to get.

            Raises:
                UntypedVarError: If the var type is Any.
                TypeError: If the var type is Any.

            # noqa: DAR101 self
            """
            if self._var_type is Any:
                raise exceptions.UntypedVarError(
                    self,
                    f"access the item '{key}'",
                )
            raise TypeError(
                f"Var of type {self._var_type} does not support item access."
            )

        def __getattr__(self, name: str):
            """Get an attribute of the var.

            Args:
                name: The name of the attribute.

            Raises:
                VarAttributeError: If the attribute does not exist.
                UntypedVarError: If the var type is Any.
                TypeError: If the var type is Any.

            # noqa: DAR101 self
            """
            if name.startswith("_"):
                raise VarAttributeError(f"Attribute {name} not found.")

            if name == "contains":
                raise TypeError(
                    f"Var of type {self._var_type} does not support contains check."
                )
            if name == "reverse":
                raise TypeError("Cannot reverse non-list var.")

            if self._var_type is Any:
                raise exceptions.UntypedVarError(
                    self,
                    f"access the attribute '{name}'",
                )

            raise VarAttributeError(
                f"The State var has no attribute '{name}' or may have been annotated wrongly.",
            )

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
            if safe_issubclass(base, Var) and base != LiteralVar
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
    def _create_literal_var(
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
        from .object import LiteralObjectVar
        from .sequence import ArrayVar, LiteralStringVar

        if isinstance(value, Var):
            if _var_data is None:
                return value
            return value._replace(merge_var_data=_var_data)

        for literal_subclass, var_subclass in _var_literal_subclasses[::-1]:
            if isinstance(value, var_subclass.python_types):
                return literal_subclass.create(value, _var_data=_var_data)

        from reflex.event import EventHandler
        from reflex.utils.format import get_event_handler_parts

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

    if not TYPE_CHECKING:
        create = _create_literal_var

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


def get_python_literal(value: LiteralVar | Any) -> Any | None:
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


P = ParamSpec("P")
T = TypeVar("T")


# NoReturn is used to match CustomVarOperationReturn with no type hint.
@overload
def var_operation(  # pyright: ignore [reportOverlappingOverload]
    func: Callable[P, CustomVarOperationReturn[NoReturn]],
) -> Callable[P, Var]: ...


@overload
def var_operation(
    func: Callable[P, CustomVarOperationReturn[None]],
) -> Callable[P, NoneVar]: ...


@overload
def var_operation(  # pyright: ignore [reportOverlappingOverload]
    func: Callable[P, CustomVarOperationReturn[bool]]
    | Callable[P, CustomVarOperationReturn[bool | None]],
) -> Callable[P, BooleanVar]: ...


NUMBER_T = TypeVar("NUMBER_T", int, float, int | float)


@overload
def var_operation(
    func: Callable[P, CustomVarOperationReturn[NUMBER_T]]
    | Callable[P, CustomVarOperationReturn[NUMBER_T | None]],
) -> Callable[P, NumberVar[NUMBER_T]]: ...


@overload
def var_operation(
    func: Callable[P, CustomVarOperationReturn[str]]
    | Callable[P, CustomVarOperationReturn[str | None]],
) -> Callable[P, StringVar]: ...


LIST_T = TypeVar("LIST_T", bound=Sequence)


@overload
def var_operation(
    func: Callable[P, CustomVarOperationReturn[LIST_T]]
    | Callable[P, CustomVarOperationReturn[LIST_T | None]],
) -> Callable[P, ArrayVar[LIST_T]]: ...


OBJECT_TYPE = TypeVar("OBJECT_TYPE", bound=Mapping)


@overload
def var_operation(
    func: Callable[P, CustomVarOperationReturn[OBJECT_TYPE]]
    | Callable[P, CustomVarOperationReturn[OBJECT_TYPE | None]],
) -> Callable[P, ObjectVar[OBJECT_TYPE]]: ...


@overload
def var_operation(
    func: Callable[P, CustomVarOperationReturn[T]]
    | Callable[P, CustomVarOperationReturn[T | None]],
) -> Callable[P, Var[T]]: ...


def var_operation(  # pyright: ignore [reportInconsistentOverload]
    func: Callable[P, CustomVarOperationReturn[T]],
) -> Callable[P, Var[T]]:
    """Decorator for creating a var operation.

    Example:
    ```python
    @var_operation
    def add(a: NumberVar, b: NumberVar):
        return custom_var_operation(f"{a} + {b}")
    ```

    Args:
        func: The function to decorate.

    Returns:
        The decorated function.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Var[T]:
        func_args = list(inspect.signature(func).parameters)
        args_vars = {
            func_args[i]: (LiteralVar.create(arg) if not isinstance(arg, Var) else arg)
            for i, arg in enumerate(args)
        }
        kwargs_vars = {
            key: LiteralVar.create(value) if not isinstance(value, Var) else value
            for key, value in kwargs.items()
        }

        return CustomVarOperation.create(
            name=func.__name__,
            args=tuple(list(args_vars.items()) + list(kwargs_vars.items())),
            return_var=func(*args_vars.values(), **kwargs_vars),  # pyright: ignore [reportCallIssue, reportReturnType]
        ).guess_type()

    return wrapper


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
        if not value:
            return Sequence[NoReturn]
        return Sequence[unionize(*(figure_out_type(v) for v in value))]
    if isinstance(value, set):
        return set[unionize(*(figure_out_type(v) for v in value))]
    if isinstance(value, tuple):
        return tuple[unionize(*(figure_out_type(v) for v in value)), ...]
    if isinstance(value, Mapping):
        if not value:
            return Mapping[NoReturn, NoReturn]
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
                GLOBAL_CACHE.pop(unique_id, None)

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


class VarProtocol(Protocol):
    """A protocol for Var."""

    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field[Any]]]

    @property
    def _js_expr(self) -> str: ...

    @property
    def _var_type(self) -> types.GenericType: ...

    @property
    def _var_data(self) -> VarData: ...


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
    def _cached_get_all_var_data(self: VarProtocol) -> VarData | None:
        """Get the cached VarData.

        Returns:
            The cached VarData.
        """
        return VarData.merge(
            *(
                value._get_all_var_data() if isinstance(value, Var) else None
                for value in (
                    getattr(self, field.name) for field in dataclasses.fields(self)
                )
            ),
            self._var_data,
        )

    def __hash__(self: DataclassInstance) -> int:
        """Calculate the hash of the object.

        Returns:
            The hash of the object.
        """
        return hash(
            (
                type(self).__name__,
                *[
                    getattr(self, field.name)
                    for field in dataclasses.fields(self)
                    if field.name not in ["_js_expr", "_var_data", "_var_type"]
                ],
            )
        )


def and_operation(
    a: Var[VAR_TYPE] | Any, b: Var[OTHER_VAR_TYPE] | Any
) -> Var[VAR_TYPE | OTHER_VAR_TYPE]:
    """Perform a logical AND operation on two variables.

    Args:
        a: The first variable.
        b: The second variable.

    Returns:
        The result of the logical AND operation.
    """
    return _and_operation(a, b)


@var_operation
def _and_operation(a: Var, b: Var):
    """Perform a logical AND operation on two variables.

    Args:
        a: The first variable.
        b: The second variable.

    Returns:
        The result of the logical AND operation.
    """
    return var_operation_return(
        js_expression=f"({a} && {b})",
        var_type=unionize(a._var_type, b._var_type),
    )


def or_operation(
    a: Var[VAR_TYPE] | Any, b: Var[OTHER_VAR_TYPE] | Any
) -> Var[VAR_TYPE | OTHER_VAR_TYPE]:
    """Perform a logical OR operation on two variables.

    Args:
        a: The first variable.
        b: The second variable.

    Returns:
        The result of the logical OR operation.
    """
    return _or_operation(a, b)


@var_operation
def _or_operation(a: Var, b: Var):
    """Perform a logical OR operation on two variables.

    Args:
        a: The first variable.
        b: The second variable.

    Returns:
        The result of the logical OR operation.
    """
    return var_operation_return(
        js_expression=f"({a} || {b})",
        var_type=unionize(a._var_type, b._var_type),
    )


RETURN_TYPE = TypeVar("RETURN_TYPE")

DICT_KEY = TypeVar("DICT_KEY")
DICT_VAL = TypeVar("DICT_VAL")

LIST_INSIDE = TypeVar("LIST_INSIDE")


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
    _static_deps: dict[str | None, set[str]] = dataclasses.field(default_factory=dict)

    # Whether var dependencies should be auto-determined
    _auto_deps: bool = dataclasses.field(default=True)

    # Interval at which the computed var should be updated
    _update_interval: datetime.timedelta | None = dataclasses.field(default=None)

    _fget: Callable[[BaseState], RETURN_TYPE] = dataclasses.field(
        default_factory=lambda: lambda _: None
    )  # pyright: ignore [reportAssignmentType]

    def __init__(
        self,
        fget: Callable[[BASE_STATE], RETURN_TYPE],
        initial_value: RETURN_TYPE | types.Unset = types.Unset(),
        cache: bool = True,
        deps: list[str | Var] | None = None,
        auto_deps: bool = True,
        interval: int | datetime.timedelta | None = None,
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

        object.__setattr__(
            self,
            "_static_deps",
            self._calculate_static_deps(deps),
        )
        object.__setattr__(self, "_auto_deps", auto_deps)

        object.__setattr__(self, "_fget", fget)

    def _calculate_static_deps(
        self,
        deps: Union[list[str | Var], dict[str | None, set[str]]] | None = None,
    ) -> dict[str | None, set[str]]:
        """Calculate the static dependencies of the computed var from user input or existing dependencies.

        Args:
            deps: The user input dependencies or existing dependencies.

        Returns:
            The static dependencies.
        """
        if isinstance(deps, dict):
            # Assume a dict is coming from _replace, so no special processing.
            return deps
        _static_deps = {}
        if deps is not None:
            for dep in deps:
                _static_deps = self._add_static_dep(dep, _static_deps)
        return _static_deps

    def _add_static_dep(
        self, dep: str | Var, deps: dict[str | None, set[str]] | None = None
    ) -> dict[str | None, set[str]]:
        """Add a static dependency to the computed var or existing dependency set.

        Args:
            dep: The dependency to add.
            deps: The existing dependency set.

        Returns:
            The updated dependency set.

        Raises:
            TypeError: If the computed var dependencies are not Var instances or var names.
        """
        if deps is None:
            deps = self._static_deps
        if isinstance(dep, Var):
            state_name = (
                all_var_data.state
                if (all_var_data := dep._get_all_var_data()) and all_var_data.state
                else None
            )
            if all_var_data is not None:
                var_name = all_var_data.field_name
            else:
                var_name = dep._js_expr
            deps.setdefault(state_name, set()).add(var_name)
        elif isinstance(dep, str) and dep != "":
            deps.setdefault(None, set()).add(dep)
        else:
            raise TypeError(
                "ComputedVar dependencies must be Var instances or var names (non-empty strings)."
            )
        return deps

    @override
    def _replace(
        self,
        merge_var_data: VarData | None = None,
        **kwargs: Any,
    ) -> Self:
        """Replace the attributes of the ComputedVar.

        Args:
            merge_var_data: VarData to merge into the existing VarData.
            **kwargs: Var fields to update.

        Returns:
            The new ComputedVar instance.

        Raises:
            TypeError: If kwargs contains keys that are not allowed.
        """
        if "deps" in kwargs:
            kwargs["deps"] = self._calculate_static_deps(kwargs["deps"])
        field_values = {
            "fget": kwargs.pop("fget", self._fget),
            "initial_value": kwargs.pop("initial_value", self._initial_value),
            "cache": kwargs.pop("cache", self._cache),
            "deps": kwargs.pop("deps", copy.copy(self._static_deps)),
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
        self: ComputedVar[bool],
        instance: None,
        owner: Type,
    ) -> BooleanVar: ...

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
        self: ComputedVar[list[LIST_INSIDE]],
        instance: None,
        owner: Type,
    ) -> ArrayVar[list[LIST_INSIDE]]: ...

    @overload
    def __get__(
        self: ComputedVar[tuple[LIST_INSIDE, ...]],
        instance: None,
        owner: Type,
    ) -> ArrayVar[tuple[LIST_INSIDE, ...]]: ...

    @overload
    def __get__(
        self: ComputedVar[BASE_TYPE],
        instance: None,
        owner: Type,
    ) -> ObjectVar[BASE_TYPE]: ...

    @overload
    def __get__(
        self: ComputedVar[SQLA_TYPE],
        instance: None,
        owner: Type,
    ) -> ObjectVar[SQLA_TYPE]: ...

    if TYPE_CHECKING:

        @overload
        def __get__(
            self: ComputedVar[DATACLASS_TYPE], instance: None, owner: Any
        ) -> ObjectVar[DATACLASS_TYPE]: ...

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

        self._check_deprecated_return_type(instance, value)

        return value

    def _check_deprecated_return_type(self, instance: BaseState, value: Any) -> None:
        if not _isinstance(value, self._var_type, nested=1, treat_var_as_type=False):
            console.error(
                f"Computed var '{type(instance).__name__}.{self._js_expr}' must return"
                f" a value of type '{self._var_type}', got '{value!s}' of type {type(value)}."
            )

    def _deps(
        self,
        objclass: Type[BaseState],
        obj: FunctionType | CodeType | None = None,
    ) -> dict[str, set[str]]:
        """Determine var dependencies of this ComputedVar.

        Save references to attributes accessed on "self" or other fetched states.

        Recursively called when the function makes a method call on "self" or
        define comprehensions or nested functions that may reference "self".

        Args:
            objclass: the class obj this ComputedVar is attached to.
            obj: the object to disassemble (defaults to the fget function).

        Returns:
            A dictionary mapping state names to the set of variable names
            accessed by the given obj.
        """
        from .dep_tracking import DependencyTracker

        d = {}
        if self._static_deps:
            d.update(self._static_deps)
            # None is a placeholder for the current state class.
            if None in d:
                d[objclass.get_full_name()] = d.pop(None)

        if not self._auto_deps:
            return d

        if obj is None:
            fget = self._fget
            if fget is not None:
                obj = cast(FunctionType, fget)
            else:
                return d

        try:
            return DependencyTracker(
                func=obj, state_cls=objclass, dependencies=d
            ).dependencies
        except Exception as e:
            console.warn(
                "Failed to automatically determine dependencies for computed var "
                f"{objclass.__name__}.{self._js_expr}: {e}. "
                "Provide static_deps and set auto_deps=False to suppress this warning."
            )
            return d

    def mark_dirty(self, instance: BaseState) -> None:
        """Mark this ComputedVar as dirty.

        Args:
            instance: the state instance that needs to recompute the value.
        """
        with contextlib.suppress(AttributeError):
            delattr(instance, self._cache_attr)

    def add_dependency(self, objclass: Type[BaseState], dep: Var):
        """Explicitly add a dependency to the ComputedVar.

        After adding the dependency, when the `dep` changes, this computed var
        will be marked dirty.

        Args:
            objclass: The class obj this ComputedVar is attached to.
            dep: The dependency to add.

        Raises:
            VarDependencyError: If the dependency is not a Var instance with a
                state and field name
        """
        if all_var_data := dep._get_all_var_data():
            state_name = all_var_data.state
            if state_name:
                var_name = all_var_data.field_name
                if var_name:
                    self._static_deps.setdefault(state_name, set()).add(var_name)
                    objclass.get_root_state().get_class_substate(
                        state_name
                    )._var_dependencies.setdefault(var_name, set()).add(
                        (objclass.get_full_name(), self._js_expr)
                    )
                    return
        raise VarDependencyError(
            "ComputedVar dependencies must be Var instances with a state and "
            f"field name, got {dep!r}."
        )

    def _determine_var_type(self) -> Type:
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


class DynamicRouteVar(ComputedVar[str | list[str]]):
    """A ComputedVar that represents a dynamic route."""

    pass


async def _default_async_computed_var(_self: BaseState) -> Any:
    return None


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    init=False,
    slots=True,
)
class AsyncComputedVar(ComputedVar[RETURN_TYPE]):
    """A computed var that wraps a coroutinefunction."""

    _fget: Callable[[BaseState], Coroutine[None, None, RETURN_TYPE]] = (
        dataclasses.field(default=_default_async_computed_var)
    )

    @overload
    def __get__(
        self: AsyncComputedVar[bool],
        instance: None,
        owner: Type,
    ) -> BooleanVar: ...

    @overload
    def __get__(
        self: AsyncComputedVar[int] | ComputedVar[float],
        instance: None,
        owner: Type,
    ) -> NumberVar: ...

    @overload
    def __get__(
        self: AsyncComputedVar[str],
        instance: None,
        owner: Type,
    ) -> StringVar: ...

    @overload
    def __get__(
        self: AsyncComputedVar[MAPPING_TYPE],
        instance: None,
        owner: Type,
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def __get__(
        self: AsyncComputedVar[list[LIST_INSIDE]],
        instance: None,
        owner: Type,
    ) -> ArrayVar[list[LIST_INSIDE]]: ...

    @overload
    def __get__(
        self: AsyncComputedVar[tuple[LIST_INSIDE, ...]],
        instance: None,
        owner: Type,
    ) -> ArrayVar[tuple[LIST_INSIDE, ...]]: ...

    @overload
    def __get__(
        self: AsyncComputedVar[BASE_TYPE],
        instance: None,
        owner: Type,
    ) -> ObjectVar[BASE_TYPE]: ...

    @overload
    def __get__(
        self: AsyncComputedVar[SQLA_TYPE],
        instance: None,
        owner: Type,
    ) -> ObjectVar[SQLA_TYPE]: ...

    if TYPE_CHECKING:

        @overload
        def __get__(
            self: AsyncComputedVar[DATACLASS_TYPE], instance: None, owner: Any
        ) -> ObjectVar[DATACLASS_TYPE]: ...

    @overload
    def __get__(self, instance: None, owner: Type) -> AsyncComputedVar[RETURN_TYPE]: ...

    @overload
    def __get__(
        self, instance: BaseState, owner: Type
    ) -> Coroutine[None, None, RETURN_TYPE]: ...

    def __get__(
        self, instance: BaseState | None, owner
    ) -> Var | Coroutine[None, None, RETURN_TYPE]:
        """Get the ComputedVar value.

        If the value is already cached on the instance, return the cached value.

        Args:
            instance: the instance of the class accessing this computed var.
            owner: the class that this descriptor is attached to.

        Returns:
            The value of the var for the given instance.
        """
        if instance is None:
            return super(AsyncComputedVar, self).__get__(instance, owner)

        if not self._cache:

            async def _awaitable_result(instance: BaseState = instance) -> RETURN_TYPE:
                value = await self.fget(instance)
                self._check_deprecated_return_type(instance, value)
                return value

            return _awaitable_result()
        else:
            # handle caching
            async def _awaitable_result(instance: BaseState = instance) -> RETURN_TYPE:
                if not hasattr(instance, self._cache_attr) or self.needs_update(
                    instance
                ):
                    # Set cache attr on state instance.
                    setattr(instance, self._cache_attr, await self.fget(instance))
                    # Ensure the computed var gets serialized to redis.
                    instance._was_touched = True
                    # Set the last updated timestamp on the state instance.
                    setattr(instance, self._last_updated_attr, datetime.datetime.now())
                value = getattr(instance, self._cache_attr)
                self._check_deprecated_return_type(instance, value)
                return value

            return _awaitable_result()

    @property
    def fget(self) -> Callable[[BaseState], Coroutine[None, None, RETURN_TYPE]]:
        """Get the getter function.

        Returns:
            The getter function.
        """
        return self._fget


if TYPE_CHECKING:
    BASE_STATE = TypeVar("BASE_STATE", bound=BaseState)


@overload
def computed_var(
    fget: None = None,
    initial_value: Any | types.Unset = types.Unset(),
    cache: bool = True,
    deps: list[str | Var] | None = None,
    auto_deps: bool = True,
    interval: datetime.timedelta | int | None = None,
    backend: bool | None = None,
    **kwargs,
) -> Callable[[Callable[[BASE_STATE], RETURN_TYPE]], ComputedVar[RETURN_TYPE]]: ...  # pyright: ignore [reportInvalidTypeVarUse]


@overload
def computed_var(
    fget: Callable[[BASE_STATE], RETURN_TYPE],
    initial_value: RETURN_TYPE | types.Unset = types.Unset(),
    cache: bool = True,
    deps: list[str | Var] | None = None,
    auto_deps: bool = True,
    interval: datetime.timedelta | int | None = None,
    backend: bool | None = None,
    **kwargs,
) -> ComputedVar[RETURN_TYPE]: ...


def computed_var(
    fget: Callable[[BASE_STATE], Any] | None = None,
    initial_value: Any | types.Unset = types.Unset(),
    cache: bool = True,
    deps: list[str | Var] | None = None,
    auto_deps: bool = True,
    interval: datetime.timedelta | int | None = None,
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
        ComputedVarSignatureError: If the getter function has more than one argument.
    """
    if cache is False and interval is not None:
        raise ValueError("Cannot set update interval without caching.")

    if cache is False and (deps is not None or auto_deps is False):
        raise VarDependencyError("Cannot track dependencies without caching.")

    if fget is not None:
        sign = inspect.signature(fget)
        if len(sign.parameters) != 1:
            raise ComputedVarSignatureError(fget.__name__, signature=str(sign))

        if inspect.iscoroutinefunction(fget):
            computed_var_cls = AsyncComputedVar
        else:
            computed_var_cls = ComputedVar
        return computed_var_cls(
            fget,
            initial_value=initial_value,
            cache=cache,
            deps=deps,
            auto_deps=auto_deps,
            interval=interval,
            backend=backend,
            **kwargs,
        )

    def wrapper(fget: Callable[[BASE_STATE], Any]) -> ComputedVar:
        if inspect.iscoroutinefunction(fget):
            computed_var_cls = AsyncComputedVar
        else:
            computed_var_cls = ComputedVar
        return computed_var_cls(
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


class CustomVarOperationReturn(Var[RETURN]):
    """Base class for custom var operations."""

    @classmethod
    def create(
        cls,
        js_expression: str,
        _var_type: Type[RETURN] | None = None,
        _var_data: VarData | None = None,
    ) -> CustomVarOperationReturn[RETURN]:
        """Create a CustomVarOperation.

        Args:
            js_expression: The JavaScript expression to evaluate.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The CustomVarOperation.
        """
        return CustomVarOperationReturn(
            _js_expr=js_expression,
            _var_type=_var_type or Any,
            _var_data=_var_data,
        )


def var_operation_return(
    js_expression: str,
    var_type: Type[RETURN] | GenericType | None = None,
    var_data: VarData | None = None,
) -> CustomVarOperationReturn[RETURN]:
    """Shortcut for creating a CustomVarOperationReturn.

    Args:
        js_expression: The JavaScript expression to evaluate.
        var_type: The type of the var.
        var_data: Additional hooks and imports associated with the Var.

    Returns:
        The CustomVarOperationReturn.
    """
    return CustomVarOperationReturn.create(
        js_expression,
        var_type,
        var_data,
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class CustomVarOperation(CachedVarOperation, Var[T]):
    """Base class for custom var operations."""

    _name: str = dataclasses.field(default="")

    _args: tuple[tuple[str, Var], ...] = dataclasses.field(default_factory=tuple)

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
        args: tuple[tuple[str, Var], ...],
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
            f"$/{constants.Dirs.STATE_PATH}": ImportVar(tag="generateUUID"),
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
_global_vars: dict[int, Var] = {}


dispatchers: dict[GenericType, Callable[[Var], Var]] = {}


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
) -> dict[TypeVar, GenericType]:
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
    generic_type: GenericType, type_mapping: dict[TypeVar, GenericType]
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

BASE_TYPE = TypeVar("BASE_TYPE", bound=Base | None)
SQLA_TYPE = TypeVar("SQLA_TYPE", bound=DeclarativeBase | None)

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

    DATACLASS_TYPE = TypeVar("DATACLASS_TYPE", bound=DataclassInstance | None)

FIELD_TYPE = TypeVar("FIELD_TYPE")
MAPPING_TYPE = TypeVar("MAPPING_TYPE", bound=Mapping | None)


class Field(Generic[FIELD_TYPE]):
    """Shadow class for Var to allow for type hinting in the IDE."""

    def __set__(self, instance: Any, value: FIELD_TYPE):
        """Set the Var.

        Args:
            instance: The instance of the class setting the Var.
            value: The value to set the Var to.
        """

    @overload
    def __get__(self: Field[None], instance: None, owner: Any) -> NoneVar: ...

    @overload
    def __get__(
        self: Field[bool] | Field[bool | None], instance: None, owner: Any
    ) -> BooleanVar: ...

    @overload
    def __get__(
        self: Field[int] | Field[int | None],
        instance: None,
        owner: Any,
    ) -> NumberVar[int]: ...

    @overload
    def __get__(
        self: Field[float]
        | Field[int | float]
        | Field[float | None]
        | Field[int | float | None],
        instance: None,
        owner: Any,
    ) -> NumberVar: ...

    @overload
    def __get__(
        self: Field[str] | Field[str | None], instance: None, owner: Any
    ) -> StringVar: ...

    @overload
    def __get__(
        self: Field[list[V]]
        | Field[set[V]]
        | Field[list[V] | None]
        | Field[set[V] | None],
        instance: None,
        owner: Any,
    ) -> ArrayVar[Sequence[V]]: ...

    @overload
    def __get__(
        self: Field[SEQUENCE_TYPE] | Field[SEQUENCE_TYPE | None],
        instance: None,
        owner: Any,
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def __get__(
        self: Field[MAPPING_TYPE] | Field[MAPPING_TYPE | None],
        instance: None,
        owner: Any,
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def __get__(
        self: Field[BASE_TYPE] | Field[BASE_TYPE | None], instance: None, owner: Any
    ) -> ObjectVar[BASE_TYPE]: ...

    @overload
    def __get__(
        self: Field[SQLA_TYPE] | Field[SQLA_TYPE | None], instance: None, owner: Any
    ) -> ObjectVar[SQLA_TYPE]: ...

    if TYPE_CHECKING:

        @overload
        def __get__(
            self: Field[DATACLASS_TYPE] | Field[DATACLASS_TYPE | None],
            instance: None,
            owner: Any,
        ) -> ObjectVar[DATACLASS_TYPE]: ...

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
