"""Define a state var."""
from __future__ import annotations

import contextlib
import dis
import json
import random
import string
from abc import ABC
from types import CodeType, FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    _GenericAlias,  # type: ignore
    cast,
    get_type_hints,
)

from pydantic.fields import ModelField

from reflex import constants
from reflex.base import Base
from reflex.utils import console, format, serializers, types

if TYPE_CHECKING:
    from reflex.state import State

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


class Var(ABC):
    """An abstract var."""

    # The name of the var.
    name: str

    # The type of the var.
    type_: Type

    # The name of the enclosing state.
    state: str = ""

    # Whether this is a local javascript variable.
    is_local: bool = False

    # Whether the var is a string literal.
    is_string: bool = False

    @classmethod
    def create(
        cls, value: Any, is_local: bool = True, is_string: bool = False
    ) -> Var | None:
        """Create a var from a value.

        Args:
            value: The value to create the var from.
            is_local: Whether the var is local.
            is_string: Whether the var is a string literal.

        Returns:
            The var.

        Raises:
            TypeError: If the value is JSON-unserializable.
        """
        # Check for none values.
        if value is None:
            return None

        # If the value is already a var, do nothing.
        if isinstance(value, Var):
            return value

        # Try to serialize the value.
        type_ = type(value)
        name = serializers.serialize(value)
        if name is None:
            raise TypeError(
                f"No JSON serializer found for var {value} of type {type_}."
            )
        name = name if isinstance(name, str) else format.json_dumps(name)

        return BaseVar(name=name, type_=type_, is_local=is_local, is_string=is_string)

    @classmethod
    def create_safe(
        cls, value: Any, is_local: bool = True, is_string: bool = False
    ) -> Var:
        """Create a var from a value, guaranteeing that it is not None.

        Args:
            value: The value to create the var from.
            is_local: Whether the var is local.
            is_string: Whether the var is a string literal.

        Returns:
            The var.
        """
        var = cls.create(value, is_local=is_local, is_string=is_string)
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
        if self.state:
            return self.full_name
        if self.is_string:
            return self.name
        try:
            return json.loads(self.name)
        except ValueError:
            return self.name

    def equals(self, other: Var) -> bool:
        """Check if two vars are equal.

        Args:
            other: The other var to compare.

        Returns:
            Whether the vars are equal.
        """
        return (
            self.name == other.name
            and self.type_ == other.type_
            and self.state == other.state
            and self.is_local == other.is_local
        )

    def to_string(self, json: bool = True) -> Var:
        """Convert a var to a string.

        Args:
            json: Whether to convert to a JSON string.

        Returns:
            The stringified var.
        """
        fn = "JSON.stringify" if json else "String"
        return self.operation(fn=fn, type_=str)

    def __hash__(self) -> int:
        """Define a hash function for a var.

        Returns:
            The hash of the var.
        """
        return hash((self.name, str(self.type_)))

    def __str__(self) -> str:
        """Wrap the var so it can be used in templates.

        Returns:
            The wrapped var, i.e. {state.var}.
        """
        out = self.full_name if self.is_local else format.wrap(self.full_name, "{")
        if self.is_string:
            out = format.format_string(out)
        return out

    def __bool__(self) -> bool:
        """Raise exception if using Var in a boolean context.

        Raises:
            TypeError: when attempting to bool-ify the Var.
        """
        raise TypeError(
            f"Cannot convert Var {self.full_name!r} to bool for use with `if`, `and`, `or`, and `not`. "
            "Instead use `rx.cond` and bitwise operators `&` (and), `|` (or), `~` (invert)."
        )

    def __iter__(self) -> Any:
        """Raise exception if using Var in an iterable context.

        Raises:
            TypeError: when attempting to iterate over the Var.
        """
        raise TypeError(
            f"Cannot iterate over Var {self.full_name!r}. Instead use `rx.foreach`."
        )

    def __format__(self, format_spec: str) -> str:
        """Format the var into a Javascript equivalent to an f-string.

        Args:
            format_spec: The format specifier (Ignored for now).

        Returns:
            The formatted var.
        """
        if self.is_local:
            return str(self)
        return f"${str(self)}"

    def __getitem__(self, i: Any) -> Var:
        """Index into a var.

        Args:
            i: The index to index into.

        Returns:
            The indexed var.

        Raises:
            TypeError: If the var is not indexable.
        """
        # Indexing is only supported for strings, lists, tuples, dicts, and dataframes.
        if not (
            types._issubclass(self.type_, Union[List, Dict, Tuple, str])
            or types.is_dataframe(self.type_)
        ):
            if self.type_ == Any:
                raise TypeError(
                    "Could not index into var of type Any. (If you are trying to index into a state var, "
                    "add the correct type annotation to the var.)"
                )
            raise TypeError(
                f"Var {self.name} of type {self.type_} does not support indexing."
            )

        # The type of the indexed var.
        type_ = Any

        # Convert any vars to local vars.
        if isinstance(i, Var):
            i = BaseVar(name=i.name, type_=i.type_, state=i.state, is_local=True)

        # Handle list/tuple/str indexing.
        if types._issubclass(self.type_, Union[List, Tuple, str]):
            # List/Tuple/String indices must be ints, slices, or vars.
            if (
                not isinstance(i, types.get_args(Union[int, slice, Var]))
                or isinstance(i, Var)
                and not i.type_ == int
            ):
                raise TypeError("Index must be an integer or an integer var.")

            # Handle slices first.
            if isinstance(i, slice):
                # Get the start and stop indices.
                start = i.start or 0
                stop = i.stop or "undefined"

                # Use the slice function.
                return BaseVar(
                    name=f"{self.name}.slice({start}, {stop})",
                    type_=self.type_,
                    state=self.state,
                    is_local=self.is_local,
                )

            # Get the type of the indexed var.
            type_ = (
                types.get_args(self.type_)[0]
                if types.is_generic_alias(self.type_)
                else Any
            )

            # Use `at` to support negative indices.
            return BaseVar(
                name=f"{self.name}.at({i})",
                type_=type_,
                state=self.state,
                is_local=self.is_local,
            )

        # Dictionary / dataframe indexing.
        # Tuples are currently not supported as indexes.
        if (
            (types._issubclass(self.type_, Dict) or types.is_dataframe(self.type_))
            and not isinstance(i, types.get_args(Union[int, str, float, Var]))
        ) or (
            isinstance(i, Var)
            and not types._issubclass(i.type_, types.get_args(Union[int, str, float]))
        ):
            raise TypeError(
                "Index must be one of the following types: int, str, int or str Var"
            )
        # Get the type of the indexed var.
        if isinstance(i, str):
            i = format.wrap(i, '"')
        type_ = (
            types.get_args(self.type_)[1] if types.is_generic_alias(self.type_) else Any
        )

        # Use normal indexing here.
        return BaseVar(
            name=f"{self.name}[{i}]",
            type_=type_,
            state=self.state,
            is_local=self.is_local,
        )

    def __getattribute__(self, name: str) -> Var:
        """Get a var attribute.

        Args:
            name: The name of the attribute.

        Returns:
            The var attribute.

        Raises:
            AttributeError: If the var is wrongly annotated or can't find attribute.
            TypeError: If an annotation to the var isn't provided.
        """
        try:
            return super().__getattribute__(name)
        except Exception as e:
            # Check if the attribute is one of the class fields.
            if not name.startswith("_"):
                if self.type_ == Any:
                    raise TypeError(
                        f"You must provide an annotation for the state var `{self.full_name}`. Annotation cannot be `{self.type_}`"
                    ) from None
                if hasattr(self.type_, "__fields__") and name in self.type_.__fields__:
                    type_ = self.type_.__fields__[name].outer_type_
                    if isinstance(type_, ModelField):
                        type_ = type_.type_
                    return BaseVar(
                        name=f"{self.name}.{name}",
                        type_=type_,
                        state=self.state,
                        is_local=self.is_local,
                    )
            raise AttributeError(
                f"The State var `{self.full_name}` has no attribute '{name}' or may have been annotated "
                f"wrongly.\n"
                f"original message: {e.args[0]}"
            ) from e

    def operation(
        self,
        op: str = "",
        other: Var | None = None,
        type_: Type | None = None,
        flip: bool = False,
        fn: str | None = None,
        invoke_fn: bool = False,
    ) -> Var:
        """Perform an operation on a var.

        Args:
            op: The operation to perform.
            other: The other var to perform the operation on.
            type_: The type of the operation result.
            flip: Whether to flip the order of the operation.
            fn: A function to apply to the operation.
            invoke_fn: Whether to invoke the function.

        Returns:
            The operation result.

        Raises:
            TypeError: If the operation between two operands is invalid.
            ValueError: If flip is set to true and value of operand is not provided
        """
        if isinstance(other, str):
            other = Var.create(json.dumps(other))
        else:
            other = Var.create(other)

        type_ = type_ or self.type_

        if other is None and flip:
            raise ValueError(
                "flip_operands cannot be set to True if the value of 'other' operand is not provided"
            )

        left_operand, right_operand = (other, self) if flip else (self, other)

        if other is not None:
            # check if the operation between operands is valid.
            if op and not self.is_valid_operation(
                types.get_base_class(left_operand.type_),  # type: ignore
                types.get_base_class(right_operand.type_),  # type: ignore
                op,
            ):
                raise TypeError(
                    f"Unsupported Operand type(s) for {op}: `{left_operand.full_name}` of type {left_operand.type_.__name__} and `{right_operand.full_name}` of type {right_operand.type_.__name__}"  # type: ignore
                )

            # apply function to operands
            if fn is not None:
                if invoke_fn:
                    # invoke the function on left operand.
                    operation_name = f"{left_operand.full_name}.{fn}({right_operand.full_name})"  # type: ignore
                else:
                    # pass the operands as arguments to the function.
                    operation_name = f"{left_operand.full_name} {op} {right_operand.full_name}"  # type: ignore
                    operation_name = f"{fn}({operation_name})"
            else:
                # apply operator to operands (left operand <operator> right_operand)
                operation_name = f"{left_operand.full_name} {op} {right_operand.full_name}"  # type: ignore
                operation_name = format.wrap(operation_name, "(")
        else:
            # apply operator to left operand (<operator> left_operand)
            operation_name = f"{op}{self.full_name}"
            # apply function to operands
            if fn is not None:
                operation_name = (
                    f"{fn}({operation_name})"
                    if not invoke_fn
                    else f"{self.full_name}.{fn}()"
                )

        return BaseVar(
            name=operation_name,
            type_=type_,
            is_local=self.is_local,
        )

    @staticmethod
    def is_valid_operation(
        operand1_type: Type, operand2_type: Type, operator: str
    ) -> bool:
        """Check if an operation between two operands is valid.

        Args:
            operand1_type: Type of the operand
            operand2_type: Type of the second operand
            operator: The operator.

        Returns:
            Whether operation is valid or not

        """
        if operator in ALL_OPS or operator in DELIMITERS:
            return True

        # bools are subclasses of ints
        pair = tuple(
            sorted(
                [
                    int if operand1_type == bool else operand1_type,
                    int if operand2_type == bool else operand2_type,
                ],
                key=lambda x: x.__name__,
            )
        )
        return pair in OPERATION_MAPPING and operator in OPERATION_MAPPING[pair]

    def compare(self, op: str, other: Var) -> Var:
        """Compare two vars with inequalities.

        Args:
            op: The comparison operator.
            other: The other var to compare with.

        Returns:
            The comparison result.
        """
        return self.operation(op, other, bool)

    def __invert__(self) -> Var:
        """Invert a var.

        Returns:
            The inverted var.
        """
        return self.operation("!", type_=bool)

    def __neg__(self) -> Var:
        """Negate a var.

        Returns:
            The negated var.
        """
        return self.operation(fn="-")

    def __abs__(self) -> Var:
        """Get the absolute value of a var.

        Returns:
            A var with the absolute value.
        """
        return self.operation(fn="Math.abs")

    def length(self) -> Var:
        """Get the length of a list var.

        Returns:
            A var with the absolute value.

        Raises:
            TypeError: If the var is not a list.
        """
        if not types._issubclass(self.type_, List):
            raise TypeError(f"Cannot get length of non-list var {self}.")
        return BaseVar(
            name=f"{self.full_name}.length",
            type_=int,
            is_local=self.is_local,
        )

    def __eq__(self, other: Var) -> Var:
        """Perform an equality comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the equality comparison.
        """
        return self.compare("===", other)

    def __ne__(self, other: Var) -> Var:
        """Perform an inequality comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the inequality comparison.
        """
        return self.compare("!==", other)

    def __gt__(self, other: Var) -> Var:
        """Perform a greater than comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the greater than comparison.
        """
        return self.compare(">", other)

    def __ge__(self, other: Var) -> Var:
        """Perform a greater than or equal to comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the greater than or equal to comparison.
        """
        return self.compare(">=", other)

    def __lt__(self, other: Var) -> Var:
        """Perform a less than comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the less than comparison.
        """
        return self.compare("<", other)

    def __le__(self, other: Var) -> Var:
        """Perform a less than or equal to comparison.

        Args:
            other: The other var to compare with.

        Returns:
            A var representing the less than or equal to comparison.
        """
        return self.compare("<=", other)

    def __add__(self, other: Var, flip=False) -> Var:
        """Add two vars.

        Args:
            other: The other var to add.
            flip: Whether to flip operands.

        Returns:
            A var representing the sum.
        """
        other_type = other.type_ if isinstance(other, Var) else type(other)
        # For list-list addition, javascript concatenates the content of the lists instead of
        # merging the list, and for that reason we use the spread operator available through spreadArraysOrObjects
        # utility function
        if (
            types.get_base_class(self.type_) == list
            and types.get_base_class(other_type) == list
        ):
            return self.operation(",", other, fn="spreadArraysOrObjects", flip=flip)
        return self.operation("+", other, flip=flip)

    def __radd__(self, other: Var) -> Var:
        """Add two vars.

        Args:
            other: The other var to add.

        Returns:
            A var representing the sum.
        """
        return self.__add__(other=other, flip=True)

    def __sub__(self, other: Var) -> Var:
        """Subtract two vars.

        Args:
            other: The other var to subtract.

        Returns:
            A var representing the difference.
        """
        return self.operation("-", other)

    def __rsub__(self, other: Var) -> Var:
        """Subtract two vars.

        Args:
            other: The other var to subtract.

        Returns:
            A var representing the difference.
        """
        return self.operation("-", other, flip=True)

    def __mul__(self, other: Var, flip=True) -> Var:
        """Multiply two vars.

        Args:
            other: The other var to multiply.
            flip: Whether to flip operands

        Returns:
            A var representing the product.
        """
        other_type = other.type_ if isinstance(other, Var) else type(other)
        # For str-int multiplication, we use the repeat function.
        # i.e "hello" * 2 is equivalent to "hello".repeat(2) in js.
        if (types.get_base_class(self.type_), types.get_base_class(other_type)) in [
            (int, str),
            (str, int),
        ]:
            return self.operation(other=other, fn="repeat", invoke_fn=True)

        # For list-int multiplication, we use the Array function.
        # i.e ["hello"] * 2 is equivalent to Array(2).fill().map(() => ["hello"]).flat() in js.
        if (types.get_base_class(self.type_), types.get_base_class(other_type)) in [
            (int, list),
            (list, int),
        ]:
            other_name = other.full_name if isinstance(other, Var) else other
            name = f"Array({other_name}).fill().map(() => {self.full_name}).flat()"
            return BaseVar(
                name=name,
                type_=str,
                is_local=self.is_local,
            )

        return self.operation("*", other)

    def __rmul__(self, other: Var) -> Var:
        """Multiply two vars.

        Args:
            other: The other var to multiply.

        Returns:
            A var representing the product.
        """
        return self.__mul__(other=other, flip=True)

    def __pow__(self, other: Var) -> Var:
        """Raise a var to a power.

        Args:
            other: The power to raise to.

        Returns:
            A var representing the power.
        """
        return self.operation(",", other, fn="Math.pow")

    def __rpow__(self, other: Var) -> Var:
        """Raise a var to a power.

        Args:
            other: The power to raise to.

        Returns:
            A var representing the power.
        """
        return self.operation(",", other, flip=True, fn="Math.pow")

    def __truediv__(self, other: Var) -> Var:
        """Divide two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the quotient.
        """
        return self.operation("/", other)

    def __rtruediv__(self, other: Var) -> Var:
        """Divide two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the quotient.
        """
        return self.operation("/", other, flip=True)

    def __floordiv__(self, other: Var) -> Var:
        """Divide two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the quotient.
        """
        return self.operation("/", other, fn="Math.floor")

    def __mod__(self, other: Var) -> Var:
        """Get the remainder of two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the remainder.
        """
        return self.operation("%", other)

    def __rmod__(self, other: Var) -> Var:
        """Get the remainder of two vars.

        Args:
            other: The other var to divide.

        Returns:
            A var representing the remainder.
        """
        return self.operation("%", other, flip=True)

    def __and__(self, other: Var) -> Var:
        """Perform a logical and.

        Args:
            other: The other var to perform the logical AND with.

        Returns:
            A var representing the logical AND.

        Note:
            This method provides behavior specific to JavaScript, where it returns the JavaScript
            equivalent code (using the '&&' operator) of a logical AND operation.
            In JavaScript, the
            logical OR operator '&&' is used for Boolean logic, and this method emulates that behavior
            by returning the equivalent code as a Var instance.

            In Python, logical AND 'and' operates differently, evaluating expressions immediately, making
            it challenging to override the behavior entirely.
            Therefore, this method leverages the
            bitwise AND '__and__' operator for custom JavaScript-like behavior.

        Example:
        >>> var1 = Var.create(True)
        >>> var2 = Var.create(False)
        >>> js_code = var1 & var2
        >>> print(js_code.full_name)
        '(true && false)'
        """
        return self.operation("&&", other, type_=bool)

    def __rand__(self, other: Var) -> Var:
        """Perform a logical and.

        Args:
            other: The other var to perform the logical AND with.

        Returns:
            A var representing the logical AND.

        Note:
            This method provides behavior specific to JavaScript, where it returns the JavaScript
            equivalent code (using the '&&' operator) of a logical AND operation.
            In JavaScript, the
            logical OR operator '&&' is used for Boolean logic, and this method emulates that behavior
            by returning the equivalent code as a Var instance.

            In Python, logical AND 'and' operates differently, evaluating expressions immediately, making
            it challenging to override the behavior entirely.
            Therefore, this method leverages the
            bitwise AND '__rand__' operator for custom JavaScript-like behavior.

        Example:
        >>> var1 = Var.create(True)
        >>> var2 = Var.create(False)
        >>> js_code = var1 & var2
        >>> print(js_code.full_name)
        '(false && true)'
        """
        return self.operation("&&", other, type_=bool, flip=True)

    def __or__(self, other: Var) -> Var:
        """Perform a logical or.

        Args:
            other: The other var to perform the logical or with.

        Returns:
            A var representing the logical or.

        Note:
            This method provides behavior specific to JavaScript, where it returns the JavaScript
            equivalent code (using the '||' operator) of a logical OR operation. In JavaScript, the
            logical OR operator '||' is used for Boolean logic, and this method emulates that behavior
            by returning the equivalent code as a Var instance.

            In Python, logical OR 'or' operates differently, evaluating expressions immediately, making
            it challenging to override the behavior entirely. Therefore, this method leverages the
            bitwise OR '__or__' operator for custom JavaScript-like behavior.

        Example:
        >>> var1 = Var.create(True)
        >>> var2 = Var.create(False)
        >>> js_code = var1 | var2
        >>> print(js_code.full_name)
        '(true || false)'
        """
        return self.operation("||", other, type_=bool)

    def __ror__(self, other: Var) -> Var:
        """Perform a logical or.

        Args:
            other: The other var to perform the logical or with.

        Returns:
            A var representing the logical or.

        Note:
            This method provides behavior specific to JavaScript, where it returns the JavaScript
            equivalent code (using the '||' operator) of a logical OR operation. In JavaScript, the
            logical OR operator '||' is used for Boolean logic, and this method emulates that behavior
            by returning the equivalent code as a Var instance.

            In Python, logical OR 'or' operates differently, evaluating expressions immediately, making
            it challenging to override the behavior entirely. Therefore, this method leverages the
            bitwise OR '__or__' operator for custom JavaScript-like behavior.

        Example:
        >>> var1 = Var.create(True)
        >>> var2 = Var.create(False)
        >>> js_code = var1 | var2
        >>> print(js_code)
        'false || true'
        """
        return self.operation("||", other, type_=bool, flip=True)

    def __contains__(self, _: Any) -> Var:
        """Override the 'in' operator to alert the user that it is not supported.

        Raises:
            TypeError: the operation is not supported
        """
        raise TypeError(
            "'in' operator not supported for Var types, use Var.contains() instead."
        )

    def contains(self, other: Any) -> Var:
        """Check if a var contains the object `other`.

        Args:
            other: The object to check.

        Raises:
            TypeError: If the var is not a valid type: dict, list, tuple or str.

        Returns:
            A var representing the contain check.
        """
        if not (types._issubclass(self.type_, Union[dict, list, tuple, str])):
            raise TypeError(
                f"Var {self.full_name} of type {self.type_} does not support contains check."
            )
        method = (
            "hasOwnProperty" if types.get_base_class(self.type_) == dict else "includes"
        )
        if isinstance(other, str):
            other = Var.create(json.dumps(other), is_string=True)
        elif not isinstance(other, Var):
            other = Var.create(other)
        if types._issubclass(self.type_, Dict):
            return BaseVar(
                name=f"{self.full_name}.{method}({other.full_name})",
                type_=bool,
                is_local=self.is_local,
            )
        else:  # str, list, tuple
            # For strings, the left operand must be a string.
            if types._issubclass(self.type_, str) and not types._issubclass(
                other.type_, str
            ):
                raise TypeError(
                    f"'in <string>' requires string as left operand, not {other.type_}"
                )
            return BaseVar(
                name=f"{self.full_name}.includes({other.full_name})",
                type_=bool,
                is_local=self.is_local,
            )

    def reverse(self) -> Var:
        """Reverse a list var.

        Raises:
            TypeError: If the var is not a list.

        Returns:
            A var with the reversed list.
        """
        if not types._issubclass(self.type_, list):
            raise TypeError(f"Cannot reverse non-list var {self.full_name}.")

        return BaseVar(
            name=f"[...{self.full_name}].reverse()",
            type_=self.type_,
            is_local=self.is_local,
        )

    def lower(self) -> Var:
        """Convert a string var to lowercase.

        Returns:
            A var with the lowercase string.

        Raises:
            TypeError: If the var is not a string.
        """
        if not types._issubclass(self.type_, str):
            raise TypeError(
                f"Cannot convert non-string var {self.full_name} to lowercase."
            )

        return BaseVar(
            name=f"{self.full_name}.toLowerCase()",
            type_=str,
            is_local=self.is_local,
        )

    def upper(self) -> Var:
        """Convert a string var to uppercase.

        Returns:
            A var with the uppercase string.

        Raises:
            TypeError: If the var is not a string.
        """
        if not types._issubclass(self.type_, str):
            raise TypeError(
                f"Cannot convert non-string var {self.full_name} to uppercase."
            )

        return BaseVar(
            name=f"{self.full_name}.toUpperCase()",
            type_=str,
            is_local=self.is_local,
        )

    def split(self, other: str | Var[str] = " ") -> Var:
        """Split a string var into a list.

        Args:
            other: The string to split the var with.

        Returns:
            A var with the list.

        Raises:
            TypeError: If the var is not a string.
        """
        if not types._issubclass(self.type_, str):
            raise TypeError(f"Cannot split non-string var {self.full_name}.")

        other = Var.create_safe(json.dumps(other)) if isinstance(other, str) else other

        return BaseVar(
            name=f"{self.full_name}.split({other.full_name})",
            type_=list[str],
            is_local=self.is_local,
        )

    def join(self, other: str | Var[str] | None = None) -> Var:
        """Join a list var into a string.

        Args:
            other: The string to join the list with.

        Returns:
            A var with the string.

        Raises:
            TypeError: If the var is not a list.
        """
        if not types._issubclass(self.type_, list):
            raise TypeError(f"Cannot join non-list var {self.full_name}.")

        if other is None:
            other = Var.create_safe("")
        if isinstance(other, str):
            other = Var.create_safe(json.dumps(other))
        else:
            other = Var.create_safe(other)

        return BaseVar(
            name=f"{self.full_name}.join({other.full_name})",
            type_=str,
            is_local=self.is_local,
        )

    def foreach(self, fn: Callable) -> Var:
        """Return a list of components. after doing a foreach on this var.

        Args:
            fn: The function to call on each component.

        Returns:
            A var representing foreach operation.
        """
        arg = BaseVar(
            name=get_unique_variable_name(),
            type_=self.type_,
        )
        return BaseVar(
            name=f"{self.full_name}.map(({arg.name}, i) => {fn(arg, key='i')})",
            type_=self.type_,
            is_local=self.is_local,
        )

    def to(self, type_: Type) -> Var:
        """Convert the type of the var.

        Args:
            type_: The type to convert to.

        Returns:
            The converted var.
        """
        return BaseVar(
            name=self.name,
            type_=type_,
            state=self.state,
            is_local=self.is_local,
        )

    @property
    def full_name(self) -> str:
        """Get the full name of the var.

        Returns:
            The full name of the var.
        """
        return self.name if self.state == "" else ".".join([self.state, self.name])

    def set_state(self, state: Type[State]) -> Any:
        """Set the state of the var.

        Args:
            state: The state to set.

        Returns:
            The var with the set state.
        """
        self.state = state.get_full_name()
        return self


class BaseVar(Var, Base):
    """A base (non-computed) var of the app state."""

    # The name of the var.
    name: str

    # The type of the var.
    type_: Any

    # The name of the enclosing state.
    state: str = ""

    # Whether this is a local javascript variable.
    is_local: bool = False

    # Whether this var is a raw string.
    is_string: bool = False

    def __hash__(self) -> int:
        """Define a hash function for a var.

        Returns:
            The hash of the var.
        """
        return hash((self.name, str(self.type_)))

    def get_default_value(self) -> Any:
        """Get the default value of the var.

        Returns:
            The default value of the var.

        Raises:
            ImportError: If the var is a dataframe and pandas is not installed.
        """
        type_ = (
            self.type_.__origin__ if types.is_generic_alias(self.type_) else self.type_
        )
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
        setter = constants.SETTER_PREFIX + self.name
        if not include_state or self.state == "":
            return setter
        return ".".join((self.state, setter))

    def get_setter(self) -> Callable[[State, Any], None]:
        """Get the var's setter function.

        Returns:
            A function that that creates a setter for the var.
        """

        def setter(state: State, value: Any):
            """Get the setter for the var.

            Args:
                state: The state within which we add the setter function.
                value: The value to set.
            """
            if self.type_ in [int, float]:
                try:
                    value = self.type_(value)
                    setattr(state, self.name, value)
                except ValueError:
                    console.warn(
                        f"{self.name}: Failed conversion of {value} to '{self.type_.__name__}'. Value not set.",
                    )
            else:
                setattr(state, self.name, value)

        setter.__qualname__ = self.get_setter_name()

        return setter


class ComputedVar(Var, property):
    """A field with computed getters."""

    # Whether to track dependencies and cache computed values
    cache: bool = False

    @property
    def name(self) -> str:
        """Get the name of the var.

        Returns:
            The name of the var.
        """
        assert self.fget is not None, "Var must have a getter."
        return self.fget.__name__

    @property
    def cache_attr(self) -> str:
        """Get the attribute used to cache the value on the instance.

        Returns:
            An attribute name.
        """
        return f"__cached_{self.name}"

    def __get__(self, instance, owner):
        """Get the ComputedVar value.

        If the value is already cached on the instance, return the cached value.

        Args:
            instance: the instance of the class accessing this computed var.
            owner: the class that this descriptor is attached to.

        Returns:
            The value of the var for the given instance.
        """
        if instance is None or not self.cache:
            return super().__get__(instance, owner)

        # handle caching
        if not hasattr(instance, self.cache_attr):
            setattr(instance, self.cache_attr, super().__get__(instance, owner))
        return getattr(instance, self.cache_attr)

    def deps(
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
        """
        d = set()
        if obj is None:
            if self.fget is not None:
                obj = cast(FunctionType, self.fget)
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
            if self_is_top_of_stack and instruction.opname == "LOAD_ATTR":
                # direct attribute access
                d.add(instruction.argval)
            elif self_is_top_of_stack and instruction.opname == "LOAD_METHOD":
                # method call on self
                d.update(
                    self.deps(
                        objclass=objclass,
                        obj=getattr(objclass, instruction.argval),
                    )
                )
            elif instruction.opname == "LOAD_CONST" and isinstance(
                instruction.argval, CodeType
            ):
                # recurse into nested functions / comprehensions, which can reference
                # instance attributes from the outer scope
                d.update(
                    self.deps(
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
            delattr(instance, self.cache_attr)

    @property
    def type_(self):
        """Get the type of the var.

        Returns:
            The type of the var.
        """
        hints = get_type_hints(self.fget)
        if "return" in hints:
            return hints["return"]
        return Any


def cached_var(fget: Callable[[Any], Any]) -> ComputedVar:
    """A field with computed getter that tracks other state dependencies.

    The cached_var will only be recalculated when other state vars that it
    depends on are modified.

    Args:
        fget: the function that calculates the variable value.

    Returns:
        ComputedVar that is recomputed when dependencies change.
    """
    cvar = ComputedVar(fget=fget)
    cvar.cache = True
    return cvar


class ImportVar(Base):
    """An import var."""

    # The name of the import tag.
    tag: Optional[str]

    # whether the import is default or named.
    is_default: Optional[bool] = False

    # The tag alias.
    alias: Optional[str] = None

    # Whether this import need to install the associated lib
    install: Optional[bool] = True

    # whether this import should be rendered or not
    render: Optional[bool] = True

    @property
    def name(self) -> str:
        """The name of the import.

        Returns:
            The name(tag name with alias) of tag.
        """
        return self.tag if not self.alias else " as ".join([self.tag, self.alias])  # type: ignore

    def __hash__(self) -> int:
        """Define a hash function for the import var.

        Returns:
            The hash of the var.
        """
        return hash((self.tag, self.is_default, self.alias, self.install, self.render))


class NoRenderImportVar(ImportVar):
    """A import that doesn't need to be rendered."""

    render: Optional[bool] = False


def get_local_storage(key: Var | str | None = None) -> BaseVar:
    """Provide a base var as payload to get local storage item(s).

    Args:
        key: Key to obtain value in the local storage.

    Returns:
        A BaseVar of the local storage method/function to call.

    Raises:
        TypeError:  if the wrong key type is provided.
    """
    console.deprecate(
        feature_name=f"rx.get_local_storage",
        reason="and has been replaced by rx.LocalStorage, which can be used as a state var",
        deprecation_version="0.2.9",
        removal_version="0.3.0",
    )
    if key is not None:
        if not (isinstance(key, Var) and key.type_ == str) and not isinstance(key, str):
            type_ = type(key) if not isinstance(key, Var) else key.type_
            raise TypeError(
                f"Local storage keys can only be of type `str` or `var` of type `str`. Got `{type_}` instead."
            )
        key = key.full_name if isinstance(key, Var) else format.wrap(key, "'")
        return BaseVar(name=f"localStorage.getItem({key})", type_=str)
    return BaseVar(name="getAllLocalStorageItems()", type_=Dict)
