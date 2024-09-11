"""Define a state var."""

from __future__ import annotations

import contextlib
import dataclasses
import random
import re
import string
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Optional,
    Tuple,
    Type,
    _GenericAlias,  # type: ignore
)

from reflex import constants
from reflex.utils import imports
from reflex.utils.exceptions import (
    VarTypeError,
)

# This module used to export ImportVar itself, so we still import it for export here
from reflex.utils.imports import (
    ImmutableParsedImportDict,
    ImportDict,
    ImportVar,
    ParsedImportDict,
    parse_imports,
)

if TYPE_CHECKING:
    from reflex.ivars import ImmutableVar
    from reflex.state import BaseState


# Set of unique variable names.
USED_VARIABLES = set()


# These names were changed in reflex 0.3.0
REPLACED_NAMES = {
    "full_name": "_var_full_name",
    "name": "_var_name",
    "state": "_var_data.state",
    "type_": "_var_type",
    "is_local": "_var_is_local",
    "is_string": "_var_is_string",
    "set_state": "_var_set_state",
    "deps": "_deps",
}


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


@dataclasses.dataclass(
    eq=True,
    frozen=True,
)
class VarData:
    """Metadata associated with a Var."""

    # The name of the enclosing state.
    state: str = dataclasses.field(default="")

    # Imports needed to render this var
    imports: ImmutableParsedImportDict = dataclasses.field(default_factory=tuple)

    # Hooks that need to be present in the component to render this var
    hooks: Tuple[str, ...] = dataclasses.field(default_factory=tuple)

    def __init__(
        self,
        state: str = "",
        imports: ImportDict | ParsedImportDict | None = None,
        hooks: dict[str, None] | None = None,
    ):
        """Initialize the var data.

        Args:
            state: The name of the enclosing state.
            imports: Imports needed to render this var.
            hooks: Hooks that need to be present in the component to render this var.
        """
        immutable_imports: ImmutableParsedImportDict = tuple(
            sorted(
                ((k, tuple(sorted(v))) for k, v in parse_imports(imports or {}).items())
            )
        )
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "imports", immutable_imports)
        object.__setattr__(self, "hooks", tuple(hooks or {}))

    def old_school_imports(self) -> ImportDict:
        """Return the imports as a mutable dict.

        Returns:
            The imports as a mutable dict.
        """
        return dict((k, list(v)) for k, v in self.imports)

    @classmethod
    def merge(cls, *others: VarData | None) -> VarData | None:
        """Merge multiple var data objects.

        Args:
            *others: The var data objects to merge.

        Returns:
            The merged var data object.
        """
        state = ""
        _imports = {}
        hooks = {}
        for var_data in others:
            if var_data is None:
                continue
            state = state or var_data.state
            _imports = imports.merge_imports(_imports, var_data.imports)
            hooks.update(
                var_data.hooks
                if isinstance(var_data.hooks, dict)
                else {k: None for k in var_data.hooks}
            )

        if state or _imports or hooks:
            return VarData(
                state=state,
                imports=_imports,
                hooks=hooks,
            )
        return None

    def __bool__(self) -> bool:
        """Check if the var data is non-empty.

        Returns:
            True if any field is set to a non-default value.
        """
        return bool(self.state or self.imports or self.hooks)

    def __eq__(self, other: Any) -> bool:
        """Check if two var data objects are equal.

        Args:
            other: The other var data object to compare.

        Returns:
            True if all fields are equal and collapsed imports are equal.
        """
        if not isinstance(other, VarData):
            return False

        # Don't compare interpolations - that's added in by the decoder, and
        # not part of the vardata itself.
        return (
            self.state == other.state
            and self.hooks
            == (
                other.hooks if isinstance(other, VarData) else tuple(other.hooks.keys())
            )
            and imports.collapse_imports(self.imports)
            == imports.collapse_imports(other.imports)
        )

    @classmethod
    def from_state(cls, state: Type[BaseState] | str) -> VarData:
        """Set the state of the var.

        Args:
            state: The state to set or the full name of the state.

        Returns:
            The var with the set state.
        """
        from reflex.utils import format

        state_name = state if isinstance(state, str) else state.get_full_name()
        new_var_data = VarData(
            state=state_name,
            hooks={
                "const {0} = useContext(StateContexts.{0})".format(
                    format.format_state_name(state_name)
                ): None
            },
            imports={
                f"/{constants.Dirs.CONTEXTS_PATH}": [ImportVar(tag="StateContexts")],
                "react": [ImportVar(tag="useContext")],
            },
        )
        return new_var_data


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


# Compile regex for finding reflex var tags.
_decode_var_pattern_re = (
    rf"{constants.REFLEX_VAR_OPENING_TAG}(.*?){constants.REFLEX_VAR_CLOSING_TAG}"
)
_decode_var_pattern = re.compile(_decode_var_pattern_re, flags=re.DOTALL)

# Defined global immutable vars.
_global_vars: Dict[int, ImmutableVar] = {}


def _extract_var_data(value: Iterable) -> list[VarData | None]:
    """Extract the var imports and hooks from an iterable containing a Var.

    Args:
        value: The iterable to extract the VarData from

    Returns:
        The extracted VarDatas.
    """
    from reflex.ivars import ImmutableVar
    from reflex.style import Style

    var_datas = []
    with contextlib.suppress(TypeError):
        for sub in value:
            if isinstance(sub, ImmutableVar):
                var_datas.append(sub._var_data)
            elif not isinstance(sub, str):
                # Recurse into dict values.
                if hasattr(sub, "values") and callable(sub.values):
                    var_datas.extend(_extract_var_data(sub.values()))
                # Recurse into iterable values (or dict keys).
                var_datas.extend(_extract_var_data(sub))

    # Style objects should already have _var_data.
    if isinstance(value, Style):
        var_datas.append(value._var_data)
    else:
        # Recurse when value is a dict itself.
        values = getattr(value, "values", None)
        if callable(values):
            var_datas.extend(_extract_var_data(values()))
    return var_datas


class Var:
    """An abstract var."""

    @classmethod
    def create(
        cls,
        value: Any,
        _var_is_local: bool = True,
        _var_is_string: bool | None = None,
        _var_data: Optional[VarData] = None,
    ) -> ImmutableVar | None:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            _var_is_local: Whether the var is local.
            _var_is_string: Whether the var is a string literal.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        from reflex.ivars import ImmutableVar, LiteralVar

        # Check for none values.
        if value is None:
            return None

        # If the value is already a var, do nothing.
        if isinstance(value, ImmutableVar):
            return value

        # If the value is not a string, create a LiteralVar.
        if not isinstance(value, str):
            return LiteralVar.create(
                value,
                _var_data=_var_data,
            )

        # if _var_is_string is provided, use that
        if _var_is_string is False:
            return ImmutableVar.create(
                value,
                _var_data=_var_data,
            )
        if _var_is_string is True:
            return LiteralVar.create(
                value,
                _var_data=_var_data,
            )

        # Otherwise, rely on _var_is_local
        if _var_is_local is True:
            return LiteralVar.create(
                value,
                _var_data=_var_data,
            )

        return ImmutableVar.create(
            value,
            _var_data=_var_data,
        )

    @classmethod
    def create_safe(
        cls,
        value: Any,
        _var_is_local: bool = True,
        _var_is_string: bool | None = None,
        _var_data: Optional[VarData] = None,
    ) -> ImmutableVar:
        """Create a var from a value, asserting that it is not None.

        Args:
            value: The value to create the var from.
            _var_is_local: Whether the var is local.
            _var_is_string: Whether the var is a string literal.
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

    @classmethod
    def __class_getitem__(cls, type_: str) -> _GenericAlias:
        """Get a typed var.

        Args:
            type_: The type of the var.

        Returns:
            The var class item.
        """
        return _GenericAlias(cls, type_)

    def __bool__(self) -> bool:
        """Raise exception if using Var in a boolean context.

        Raises:
            VarTypeError: when attempting to bool-ify the Var.
        """
        raise VarTypeError(
            f"Cannot convert Var {str(self)!r} to bool for use with `if`, `and`, `or`, and `not`. "
            "Instead use `rx.cond` and bitwise operators `&` (and), `|` (or), `~` (invert)."
        )

    def __iter__(self) -> Any:
        """Raise exception if using Var in an iterable context.

        Raises:
            VarTypeError: when attempting to iterate over the Var.
        """
        raise VarTypeError(
            f"Cannot iterate over Var {str(self)!r}. Instead use `rx.foreach`."
        )

    def __contains__(self, _: Any) -> ImmutableVar:
        """Override the 'in' operator to alert the user that it is not supported.

        Raises:
            VarTypeError: the operation is not supported
        """
        raise VarTypeError(
            "'in' operator not supported for Var types, use Var.contains() instead."
        )

    def __get__(self, instance: Any, owner: Any) -> ImmutableVar:
        """Return the value of the Var.

        Args:
            instance: The instance of the Var.
            owner: The owner of the Var.

        Returns:
            The value of the Var.
        """
        return self  # type: ignore

    @classmethod
    def range(
        cls,
        v1: ImmutableVar | int = 0,
        v2: ImmutableVar | int | None = None,
        step: ImmutableVar | int | None = None,
    ) -> ImmutableVar:
        """Return an iterator over indices from v1 to v2 (or 0 to v1).

        Args:
            v1: The start of the range or end of range if v2 is not given.
            v2: The end of the range.
            step: The number of numbers between each item.

        Returns:
            A var representing range operation.
        """
        from reflex.ivars import ArrayVar

        return ArrayVar.range(v1, v2, step)  # type: ignore

    def upcast(self) -> ImmutableVar:
        """Upcast a Var to an ImmutableVar.

        Returns:
            The upcasted Var.
        """
        return self  # type: ignore

    def json(self) -> str:
        """Serialize the var to a JSON string.

        Raises:
            NotImplementedError: If the method is not implemented.
        """
        raise NotImplementedError("Var subclasses must implement the json method.")


def get_uuid_string_var() -> ImmutableVar:
    """Return a Var that generates a single memoized UUID via .web/utils/state.js.

    useMemo with an empty dependency array ensures that the generated UUID is
    consistent across re-renders of the component.

    Returns:
        A Var that generates a UUID at runtime.
    """
    from reflex.ivars import ImmutableVar
    from reflex.utils.imports import ImportVar

    unique_uuid_var = get_unique_variable_name()
    unique_uuid_var_data = VarData(
        imports={
            f"/{constants.Dirs.STATE_PATH}": {ImportVar(tag="generateUUID")},  # type: ignore
            "react": "useMemo",
        },
        hooks={f"const {unique_uuid_var} = useMemo(generateUUID, [])": None},
    )

    return ImmutableVar(
        _var_name=unique_uuid_var,
        _var_type=str,
        _var_data=unique_uuid_var_data,
    )
