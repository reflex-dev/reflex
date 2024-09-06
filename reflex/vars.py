"""Define a state var."""

from __future__ import annotations

import contextlib
import dataclasses
import json
import random
import re
import string
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    _GenericAlias,  # type: ignore
)

from reflex import constants
from reflex.base import Base
from reflex.utils import imports, serializers
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

# Supported operators for all types.
ALL_OPS = ["==", "!=", "!==", "===", "&&", "||"]
# Delimiters used between function args or operands.
DELIMITERS = [","]
# Mapping of valid operations for different type combinations.
OPERATION_MAPPING = {
    (int, int): {
        "+",
        "-",
        "/",
        "//",
        "*",
        "%",
        "**",
        ">",
        "<",
        "<=",
        ">=",
        "|",
        "&",
    },
    (int, str): {"*"},
    (int, list): {"*"},
    (str, str): {"+", ">", "<", "<=", ">="},
    (float, float): {"+", "-", "/", "//", "*", "%", "**", ">", "<", "<=", ">="},
    (float, int): {"+", "-", "/", "//", "*", "%", "**", ">", "<", "<=", ">="},
    (list, list): {"+", ">", "<", "<=", ">="},
}

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

PYTHON_JS_TYPE_MAP = {
    (int, float): "number",
    (str,): "string",
    (bool,): "boolean",
    (list, tuple): "Array",
    (dict,): "Object",
    (None,): "null",
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


class VarData(Base):
    """Metadata associated with a Var."""

    # The name of the enclosing state.
    state: str = ""

    # Imports needed to render this var
    imports: ParsedImportDict = {}

    # Hooks that need to be present in the component to render this var
    hooks: Dict[str, None] = {}

    # Positions of interpolated strings. This is used by the decoder to figure
    # out where the interpolations are and only escape the non-interpolated
    # segments.
    interpolations: List[Tuple[int, int]] = []

    def __init__(
        self, imports: Union[ImportDict, ParsedImportDict] | None = None, **kwargs: Any
    ):
        """Initialize the var data.

        Args:
            imports: The imports needed to render this var.
            **kwargs: The var data fields.
        """
        if imports:
            kwargs["imports"] = parse_imports(imports)
        super().__init__(**kwargs)

    @classmethod
    def merge(cls, *others: ImmutableVarData | VarData | None) -> VarData | None:
        """Merge multiple var data objects.

        Args:
            *others: The var data objects to merge.

        Returns:
            The merged var data object.
        """
        state = ""
        _imports = {}
        hooks = {}
        interpolations = []
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
            interpolations += (
                var_data.interpolations if isinstance(var_data, VarData) else []
            )

        if state or _imports or hooks or interpolations:
            return cls(
                state=state,
                imports=_imports,
                hooks=hooks,
                interpolations=interpolations,
            )
        return None

    def __bool__(self) -> bool:
        """Check if the var data is non-empty.

        Returns:
            True if any field is set to a non-default value.
        """
        return bool(self.state or self.imports or self.hooks or self.interpolations)

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
            and self.hooks.keys() == other.hooks.keys()
            and imports.collapse_imports(self.imports)
            == imports.collapse_imports(other.imports)
        )

    def dict(self) -> dict:
        """Convert the var data to a dictionary.

        Returns:
            The var data dictionary.
        """
        return {
            "state": self.state,
            "interpolations": list(self.interpolations),
            "imports": {
                lib: [import_var.dict() for import_var in import_vars]
                for lib, import_vars in self.imports.items()
            },
            "hooks": self.hooks,
        }


@dataclasses.dataclass(
    eq=True,
    frozen=True,
)
class ImmutableVarData:
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

    @classmethod
    def merge(
        cls, *others: ImmutableVarData | VarData | None
    ) -> ImmutableVarData | None:
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
            return ImmutableVarData(
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
        if not isinstance(other, (ImmutableVarData, VarData)):
            return False

        # Don't compare interpolations - that's added in by the decoder, and
        # not part of the vardata itself.
        return (
            self.state == other.state
            and self.hooks
            == (
                other.hooks
                if isinstance(other, ImmutableVarData)
                else tuple(other.hooks.keys())
            )
            and imports.collapse_imports(self.imports)
            == imports.collapse_imports(other.imports)
        )

    @classmethod
    def from_state(cls, state: Type[BaseState] | str) -> ImmutableVarData:
        """Set the state of the var.

        Args:
            state: The state to set or the full name of the state.

        Returns:
            The var with the set state.
        """
        from reflex.utils import format

        state_name = state if isinstance(state, str) else state.get_full_name()
        new_var_data = ImmutableVarData(
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


def _decode_var_immutable(value: str) -> tuple[ImmutableVarData | None, str]:
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

        # Initialize some methods for reading json.
        var_data_config = VarData().__config__

        def json_loads(s):
            try:
                return var_data_config.json_loads(s)
            except json.decoder.JSONDecodeError:
                return var_data_config.json_loads(var_data_config.json_loads(f'"{s}"'))

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
                    realstart = start + offset

                    var_datas.append(var_data)
            else:
                # Read the JSON, pull out the string length, parse the rest as VarData.
                data = json_loads(serialized_data)
                string_length = data.pop("string_length", None)
                var_data = VarData.parse_obj(data)

                # Use string length to compute positions of interpolations.
                if string_length is not None:
                    realstart = start + offset
                    var_data.interpolations = [(realstart, realstart + string_length)]

                var_datas.append(var_data)
            offset += end - start

    return ImmutableVarData.merge(*var_datas) if var_datas else None, value


def _encode_var(value: Var) -> str:
    """Encode the state name into a formatted var.

    Args:
        value: The value to encode the state name into.

    Returns:
        The encoded var.
    """
    if value._var_data:
        from reflex.utils.serializers import serialize

        final_value = str(value)
        data = value._var_data.dict()
        data["string_length"] = len(final_value)
        data_json = value._var_data.__config__.json_dumps(data, default=serialize)

        return (
            f"{constants.REFLEX_VAR_OPENING_TAG}{data_json}{constants.REFLEX_VAR_CLOSING_TAG}"
            + final_value
        )

    return str(value)


# Compile regex for finding reflex var tags.
_decode_var_pattern_re = (
    rf"{constants.REFLEX_VAR_OPENING_TAG}(.*?){constants.REFLEX_VAR_CLOSING_TAG}"
)
_decode_var_pattern = re.compile(_decode_var_pattern_re, flags=re.DOTALL)

# Defined global immutable vars.
_global_vars: Dict[int, Var] = {}


def _decode_var(value: str) -> tuple[VarData | None, str]:
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

        # Initialize some methods for reading json.
        var_data_config = VarData().__config__

        def json_loads(s):
            try:
                return var_data_config.json_loads(s)
            except json.decoder.JSONDecodeError:
                return var_data_config.json_loads(var_data_config.json_loads(f'"{s}"'))

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
                var_data = var._var_data

                if var_data is not None:
                    realstart = start + offset

                    var_datas.append(var_data)
            else:
                # Read the JSON, pull out the string length, parse the rest as VarData.
                data = json_loads(serialized_data)
                string_length = data.pop("string_length", None)
                var_data = VarData.parse_obj(data)

                # Use string length to compute positions of interpolations.
                if string_length is not None:
                    realstart = start + offset
                    var_data.interpolations = [(realstart, realstart + string_length)]

                var_datas.append(var_data)
            offset += end - start

    return VarData.merge(*var_datas) if var_datas else None, value


def _extract_var_data(value: Iterable) -> list[VarData | None]:
    """Extract the var imports and hooks from an iterable containing a Var.

    Args:
        value: The iterable to extract the VarData from

    Returns:
        The extracted VarDatas.
    """
    from reflex.style import Style

    var_datas = []
    with contextlib.suppress(TypeError):
        for sub in value:
            if isinstance(sub, Var):
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

    # The name of the var.
    _var_name: str

    # The type of the var.
    _var_type: Type

    # Whether this is a local javascript variable.
    _var_is_local: bool

    # Whether the var is a string literal.
    _var_is_string: bool

    # _var_full_name should be prefixed with _var_state
    _var_full_name_needs_state_prefix: bool

    # Extra metadata associated with the Var
    _var_data: Optional[VarData]

    @classmethod
    def create(
        cls,
        value: Any,
        _var_is_local: bool = True,
        _var_is_string: bool | None = None,
        _var_data: Optional[VarData] = None,
    ) -> Var | None:
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
        if isinstance(value, Var):
            return value

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

        # If the value is a string, create a LiteralVar.
        if not isinstance(value, str) or _var_is_local is True:
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
    ) -> Var:
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

    def _decode(self) -> Any:
        """Decode Var as a python value.

        Note that Var with state set cannot be decoded python-side and will be
        returned as full_name.

        Returns:
            The decoded value or the Var name.
        """
        if self._var_is_string:
            return self._var_name
        try:
            return json.loads(self._var_name)
        except ValueError:
            try:
                return json.loads(self.json())
            except (ValueError, NotImplementedError):
                return self._var_name

    def equals(self, other: Var) -> bool:
        """Check if two vars are equal.

        Args:
            other: The other var to compare.

        Returns:
            Whether the vars are equal.
        """
        return (
            self._var_name == other._var_name
            and self._var_type == other._var_type
            and ImmutableVarData.merge(self._get_all_var_data())
            == ImmutableVarData.merge(other._get_all_var_data())
        )

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

    def __contains__(self, _: Any) -> Var:
        """Override the 'in' operator to alert the user that it is not supported.

        Raises:
            VarTypeError: the operation is not supported
        """
        raise VarTypeError(
            "'in' operator not supported for Var types, use Var.contains() instead."
        )

    @classmethod
    def range(
        cls,
        v1: Var | int = 0,
        v2: Var | int | None = None,
        step: Var | int | None = None,
    ) -> Var:
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

    @property
    def _var_state(self) -> str:
        """Compat method for getting the state.

        Returns:
            The state name associated with the var.
        """
        var_data = self._get_all_var_data()
        return var_data.state if var_data else ""

    def _get_all_var_data(self) -> ImmutableVarData | None:
        """Get all the var data.

        Raises:
            NotImplementedError: If the method is not implemented.
        """
        raise NotImplementedError(
            "Var subclasses must implement the _get_all_var_data method."
        )

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


# Allow automatic serialization of Var within JSON structures
serializers.serializer(_encode_var)


def get_uuid_string_var() -> Var:
    """Return a Var that generates a single memoized UUID via .web/utils/state.js.

    useMemo with an empty dependency array ensures that the generated UUID is
    consistent across re-renders of the component.

    Returns:
        A Var that generates a UUID at runtime.
    """
    from reflex.ivars import ImmutableVar
    from reflex.utils.imports import ImportVar

    unique_uuid_var = get_unique_variable_name()
    unique_uuid_var_data = ImmutableVarData(
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
