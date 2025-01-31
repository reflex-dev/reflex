"""Immutable function vars."""

from __future__ import annotations

import dataclasses
import inspect
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Mapping,
    NoReturn,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    overload,
)

from typing_extensions import Concatenate, Generic, ParamSpec, TypeVar

from reflex.utils import format
from reflex.utils.exceptions import VarTypeError
from reflex.utils.types import GenericType, Unset, get_origin

from .base import (
    CachedVarOperation,
    LiteralVar,
    ReflexCallable,
    TypeComputer,
    Var,
    VarData,
    VarWithDefault,
    cached_property_no_lock,
    unwrap_reflex_callalbe,
)

if TYPE_CHECKING:
    from .number import BooleanVar, NumberVar
    from .object import ObjectVar
    from .sequence import ArrayVar, StringVar

P = ParamSpec("P")
R = TypeVar("R")
R2 = TypeVar("R2")
V1 = TypeVar("V1")
V2 = TypeVar("V2")
V3 = TypeVar("V3")
V4 = TypeVar("V4")
V5 = TypeVar("V5")
V6 = TypeVar("V6")


CALLABLE_TYPE = TypeVar("CALLABLE_TYPE", bound=ReflexCallable, infer_variance=True)
OTHER_CALLABLE_TYPE = TypeVar(
    "OTHER_CALLABLE_TYPE", bound=ReflexCallable, infer_variance=True
)

MAPPING_TYPE = TypeVar("MAPPING_TYPE", bound=Mapping, covariant=True)
SEQUENCE_TYPE = TypeVar("SEQUENCE_TYPE", bound=Sequence, covariant=True)


def type_is_reflex_callable(type_: Any) -> bool:
    """Check if a type is a ReflexCallable.

    Args:
        type_: The type to check.

    Returns:
        True if the type is a ReflexCallable.
    """
    return type_ is ReflexCallable or get_origin(type_) is ReflexCallable


K = TypeVar("K", covariant=True)
V = TypeVar("V", covariant=True)
T = TypeVar("T", covariant=True)


class FunctionVar(
    Var[CALLABLE_TYPE],
    default_type=ReflexCallable[Any, Any],
    is_subclass=type_is_reflex_callable,
):
    """Base class for immutable function vars."""

    @overload
    def partial(self) -> FunctionVar[CALLABLE_TYPE]: ...

    @overload
    def partial(
        self: FunctionVar[ReflexCallable[Concatenate[VarWithDefault[V1], P], R]]
        | FunctionVar[ReflexCallable[Concatenate[V1, P], R]],
        arg1: Union[V1, Var[V1]],
    ) -> FunctionVar[ReflexCallable[P, R]]: ...

    @overload
    def partial(
        self: FunctionVar[
            ReflexCallable[Concatenate[VarWithDefault[V1], VarWithDefault[V2], P], R]
        ]
        | FunctionVar[ReflexCallable[Concatenate[V1, VarWithDefault[V2], P], R]]
        | FunctionVar[ReflexCallable[Concatenate[V1, V2, P], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
    ) -> FunctionVar[ReflexCallable[P, R]]: ...

    @overload
    def partial(
        self: FunctionVar[
            ReflexCallable[
                Concatenate[
                    VarWithDefault[V1], VarWithDefault[V2], VarWithDefault[V3], P
                ],
                R,
            ]
        ]
        | FunctionVar[
            ReflexCallable[
                Concatenate[V1, VarWithDefault[V2], VarWithDefault[V3], P], R
            ]
        ]
        | FunctionVar[ReflexCallable[Concatenate[V1, V2, VarWithDefault[V3], P], R]]
        | FunctionVar[ReflexCallable[Concatenate[V1, V2, V3, P], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
    ) -> FunctionVar[ReflexCallable[P, R]]: ...

    @overload
    def partial(
        self: FunctionVar[ReflexCallable[Concatenate[V1, V2, V3, V4, P], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
    ) -> FunctionVar[ReflexCallable[P, R]]: ...

    @overload
    def partial(
        self: FunctionVar[ReflexCallable[Concatenate[V1, V2, V3, V4, V5, P], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
        arg5: Union[V5, Var[V5]],
    ) -> FunctionVar[ReflexCallable[P, R]]: ...

    @overload
    def partial(
        self: FunctionVar[ReflexCallable[Concatenate[V1, V2, V3, V4, V5, V6, P], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
        arg5: Union[V5, Var[V5]],
        arg6: Union[V6, Var[V6]],
    ) -> FunctionVar[ReflexCallable[P, R]]: ...

    @overload
    def partial(
        self: FunctionVar[ReflexCallable[P, R]], *args: Var | Any
    ) -> FunctionVar[ReflexCallable[P, R]]: ...

    @overload
    def partial(self, *args: Var | Any) -> FunctionVar: ...

    def partial(self, *args: Var | Any) -> FunctionVar:  # pyright: ignore [reportInconsistentOverload]
        """Partially apply the function with the given arguments.

        Args:
            *args: The arguments to partially apply the function with.

        Returns:
            The partially applied function.
        """
        if not args:
            return self

        args = tuple(map(LiteralVar.create, args))

        remaining_validators = self._pre_check(*args)

        partial_types, type_computer = self._partial_type(*args)

        if self.__call__ is self.partial:
            # if the default behavior is partial, we should return a new partial function
            return ArgsFunctionOperationBuilder.create(
                (),
                VarOperationCall.create(
                    self,
                    *args,
                    Var(_js_expr="...args"),
                    _var_type=self._return_type(*args),
                ),
                rest="args",
                validators=remaining_validators,
                type_computer=type_computer,
                _var_type=partial_types,
            )
        return ArgsFunctionOperation.create(
            (),
            VarOperationCall.create(
                self, *args, Var(_js_expr="...args"), _var_type=self._return_type(*args)
            ),
            rest="args",
            validators=remaining_validators,
            type_computer=type_computer,
            _var_type=partial_types,
        )

    # THIS CODE IS GENERATED BY `_generate_overloads_for_function_var_call` function below.

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[], bool]],
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[], int]],
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[], float]],
    ) -> NumberVar[float]: ...

    @overload
    def call(  # pyright: ignore[reportOverlappingOverload]
        self: FunctionVar[ReflexCallable[[], str]],
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[], SEQUENCE_TYPE]],
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[], MAPPING_TYPE]],
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[], R]],
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[VarWithDefault[V1]], bool]],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[VarWithDefault[V1]], int]],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[VarWithDefault[V1]], float]],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[VarWithDefault[V1]], str]],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[VarWithDefault[V1]], SEQUENCE_TYPE]],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[VarWithDefault[V1]], MAPPING_TYPE]],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[VarWithDefault[V1]], R]],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[VarWithDefault[V1], VarWithDefault[V2]], bool]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[VarWithDefault[V1], VarWithDefault[V2]], int]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[VarWithDefault[V1], VarWithDefault[V2]], float]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[VarWithDefault[V1], VarWithDefault[V2]], str]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[VarWithDefault[V1], VarWithDefault[V2]], SEQUENCE_TYPE]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[VarWithDefault[V1], VarWithDefault[V2]], MAPPING_TYPE]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[VarWithDefault[V1], VarWithDefault[V2]], R]],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [VarWithDefault[V1], VarWithDefault[V2], VarWithDefault[V3]], bool
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [VarWithDefault[V1], VarWithDefault[V2], VarWithDefault[V3]], int
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [VarWithDefault[V1], VarWithDefault[V2], VarWithDefault[V3]], float
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [VarWithDefault[V1], VarWithDefault[V2], VarWithDefault[V3]], str
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [VarWithDefault[V1], VarWithDefault[V2], VarWithDefault[V3]],
                SEQUENCE_TYPE,
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [VarWithDefault[V1], VarWithDefault[V2], VarWithDefault[V3]],
                MAPPING_TYPE,
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [VarWithDefault[V1], VarWithDefault[V2], VarWithDefault[V3]], R
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [
                    VarWithDefault[V1],
                    VarWithDefault[V2],
                    VarWithDefault[V3],
                    VarWithDefault[V4],
                ],
                bool,
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [
                    VarWithDefault[V1],
                    VarWithDefault[V2],
                    VarWithDefault[V3],
                    VarWithDefault[V4],
                ],
                int,
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [
                    VarWithDefault[V1],
                    VarWithDefault[V2],
                    VarWithDefault[V3],
                    VarWithDefault[V4],
                ],
                float,
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [
                    VarWithDefault[V1],
                    VarWithDefault[V2],
                    VarWithDefault[V3],
                    VarWithDefault[V4],
                ],
                str,
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [
                    VarWithDefault[V1],
                    VarWithDefault[V2],
                    VarWithDefault[V3],
                    VarWithDefault[V4],
                ],
                SEQUENCE_TYPE,
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [
                    VarWithDefault[V1],
                    VarWithDefault[V2],
                    VarWithDefault[V3],
                    VarWithDefault[V4],
                ],
                MAPPING_TYPE,
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [
                    VarWithDefault[V1],
                    VarWithDefault[V2],
                    VarWithDefault[V3],
                    VarWithDefault[V4],
                ],
                R,
            ]
        ],
        arg1: Union[V1, Var[V1], Unset] = Unset(),
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1], bool]], arg1: Union[V1, Var[V1]]
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1], int]], arg1: Union[V1, Var[V1]]
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1], float]], arg1: Union[V1, Var[V1]]
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1], str]], arg1: Union[V1, Var[V1]]
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1], SEQUENCE_TYPE]], arg1: Union[V1, Var[V1]]
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1], MAPPING_TYPE]], arg1: Union[V1, Var[V1]]
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1], R]], arg1: Union[V1, Var[V1]]
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, VarWithDefault[V2]], bool]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, VarWithDefault[V2]], int]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, VarWithDefault[V2]], float]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, VarWithDefault[V2]], str]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, VarWithDefault[V2]], SEQUENCE_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, VarWithDefault[V2]], MAPPING_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, VarWithDefault[V2]], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, VarWithDefault[V2], VarWithDefault[V3]], bool]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, VarWithDefault[V2], VarWithDefault[V3]], int]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, VarWithDefault[V2], VarWithDefault[V3]], float]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, VarWithDefault[V2], VarWithDefault[V3]], str]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, VarWithDefault[V2], VarWithDefault[V3]], SEQUENCE_TYPE]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, VarWithDefault[V2], VarWithDefault[V3]], MAPPING_TYPE]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, VarWithDefault[V2], VarWithDefault[V3]], R]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [V1, VarWithDefault[V2], VarWithDefault[V3], VarWithDefault[V4]], bool
            ]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [V1, VarWithDefault[V2], VarWithDefault[V3], VarWithDefault[V4]], int
            ]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [V1, VarWithDefault[V2], VarWithDefault[V3], VarWithDefault[V4]], float
            ]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [V1, VarWithDefault[V2], VarWithDefault[V3], VarWithDefault[V4]], str
            ]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [V1, VarWithDefault[V2], VarWithDefault[V3], VarWithDefault[V4]],
                SEQUENCE_TYPE,
            ]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [V1, VarWithDefault[V2], VarWithDefault[V3], VarWithDefault[V4]],
                MAPPING_TYPE,
            ]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [V1, VarWithDefault[V2], VarWithDefault[V3], VarWithDefault[V4]], R
            ]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2], Unset] = Unset(),
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2], bool]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2], int]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2], float]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2], str]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2], SEQUENCE_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2], MAPPING_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, VarWithDefault[V3]], bool]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, VarWithDefault[V3]], int]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, VarWithDefault[V3]], float]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, VarWithDefault[V3]], str]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, VarWithDefault[V3]], SEQUENCE_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, VarWithDefault[V3]], MAPPING_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, VarWithDefault[V3]], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, V2, VarWithDefault[V3], VarWithDefault[V4]], bool]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, V2, VarWithDefault[V3], VarWithDefault[V4]], int]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, V2, VarWithDefault[V3], VarWithDefault[V4]], float]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, V2, VarWithDefault[V3], VarWithDefault[V4]], str]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [V1, V2, VarWithDefault[V3], VarWithDefault[V4]], SEQUENCE_TYPE
            ]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[
                [V1, V2, VarWithDefault[V3], VarWithDefault[V4]], MAPPING_TYPE
            ]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, V2, VarWithDefault[V3], VarWithDefault[V4]], R]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3], Unset] = Unset(),
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3], bool]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3], int]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3], float]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3], str]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3], SEQUENCE_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3], MAPPING_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, VarWithDefault[V4]], bool]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, VarWithDefault[V4]], int]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, VarWithDefault[V4]], float]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, VarWithDefault[V4]], str]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, V2, V3, VarWithDefault[V4]], SEQUENCE_TYPE]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[
            ReflexCallable[[V1, V2, V3, VarWithDefault[V4]], MAPPING_TYPE]
        ],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, VarWithDefault[V4]], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4], Unset] = Unset(),
    ) -> Var[R]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, V4], bool]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
    ) -> BooleanVar: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, V4], int]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
    ) -> NumberVar[int]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, V4], float]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
    ) -> NumberVar[float]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, V4], str]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
    ) -> StringVar[str]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, V4], SEQUENCE_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
    ) -> ArrayVar[SEQUENCE_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, V4], MAPPING_TYPE]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
    ) -> ObjectVar[MAPPING_TYPE]: ...

    @overload
    def call(
        self: FunctionVar[ReflexCallable[[V1, V2, V3, V4], R]],
        arg1: Union[V1, Var[V1]],
        arg2: Union[V2, Var[V2]],
        arg3: Union[V3, Var[V3]],
        arg4: Union[V4, Var[V4]],
    ) -> Var[R]: ...

    # Capture Any to allow for arbitrary number of arguments
    @overload
    def call(self: FunctionVar[NoReturn], *args: Var | Any) -> Var: ...

    def call(self, *args: Var | Any) -> Var:  # pyright: ignore [reportInconsistentOverload]
        """Call the function with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            The function call operation.

        Raises:
            VarTypeError: If the number of arguments is invalid
        """
        required_arg_len = self._required_arg_len()
        arg_len = self._arg_len()
        if arg_len is not None:
            if len(args) < required_arg_len:
                raise VarTypeError(
                    f"Passed {len(args)} arguments, expected at least {required_arg_len} for {self!s}"
                )
            if len(args) > arg_len:
                raise VarTypeError(
                    f"Passed {len(args)} arguments, expected at most {arg_len} for {self!s}"
                )
        args = tuple(map(LiteralVar.create, args))
        self._pre_check(*args)
        return_type = self._return_type(*args)
        if isinstance(self, (ArgsFunctionOperation, ArgsFunctionOperationBuilder)):
            default_args = self._default_args()
            max_allowed_arguments = (
                arg_len if arg_len is not None else len(args) + len(default_args)
            )
            provided_argument_count = len(args)

            # we skip default args which we provided
            default_args_provided = len(default_args) - (
                max_allowed_arguments - provided_argument_count
            )

            full_args = args + tuple(default_args[default_args_provided:])

            if self._raw_js_function is not None:
                return VarOperationCall.create(
                    FunctionStringVar.create(
                        self._raw_js_function,
                        _var_type=self._var_type,
                        _var_data=self._get_all_var_data(),
                    ),
                    *full_args,
                    _var_type=return_type,
                ).guess_type()
            if self._original_var_operation is not None:
                return ExpressionCall.create(
                    self._original_var_operation,
                    *full_args,
                    _var_data=self._get_all_var_data(),
                    _var_type=return_type,
                ).guess_type()

        return VarOperationCall.create(self, *args, _var_type=return_type).guess_type()

    def chain(
        self: FunctionVar[ReflexCallable[P, R]],
        other: FunctionVar[ReflexCallable[[R], R2]]
        | FunctionVar[ReflexCallable[[R, VarWithDefault[Any]], R2]]
        | FunctionVar[
            ReflexCallable[[R, VarWithDefault[Any], VarWithDefault[Any]], R2]
        ],
    ) -> FunctionVar[ReflexCallable[P, R2]]:
        """Chain two functions together.

        Args:
            other: The other function to chain.

        Returns:
            The chained function.
        """
        self_arg_type, self_return_type = unwrap_reflex_callalbe(self._var_type)
        _, other_return_type = unwrap_reflex_callalbe(other._var_type)

        return ArgsFunctionOperationBuilder.create(
            (),
            VarOperationCall.create(
                other,
                VarOperationCall.create(
                    self, Var(_js_expr="...args"), _var_type=self_return_type
                ),
                _var_type=other_return_type,
            ),
            rest="arg",
            _var_type=ReflexCallable[self_arg_type, other_return_type],  # pyright: ignore [reportInvalidTypeArguments]
        )

    def _partial_type(
        self, *args: Var | Any
    ) -> Tuple[GenericType, Optional[TypeComputer]]:
        """Override the type of the function call with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            The overridden type of the function call.
        """
        args_types, return_type = unwrap_reflex_callalbe(self._var_type)
        if isinstance(args_types, tuple):
            return ReflexCallable[[*args_types[len(args) :]], return_type], None
        return ReflexCallable[..., return_type], None

    def _arg_len(self) -> int | None:
        """Get the number of arguments the function takes.

        Returns:
            The number of arguments the function takes.
        """
        args_types, _ = unwrap_reflex_callalbe(self._var_type)
        if isinstance(args_types, tuple):
            return len(args_types)
        return None

    def _required_arg_len(self) -> int:
        """Get the number of required arguments the function takes.

        Returns:
            The number of required arguments the function takes.
        """
        args_types, _ = unwrap_reflex_callalbe(self._var_type)
        if isinstance(args_types, tuple):
            return sum(
                1
                for arg_type in args_types
                if get_origin(arg_type) is not VarWithDefault
            )
        return 0

    def _default_args(self) -> list[Any]:
        """Get the default arguments of the function.

        Returns:
            The default arguments of the function.
        """
        if isinstance(self, (ArgsFunctionOperation, ArgsFunctionOperationBuilder)):
            return [
                arg.default
                for arg in self._default_values
                if not isinstance(arg, inspect.Parameter.empty)
            ]
        return []

    def _return_type(self, *args: Var | Any) -> GenericType:
        """Override the type of the function call with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            The overridden type of the function call.
        """
        partial_types, _ = self._partial_type(*args)
        return unwrap_reflex_callalbe(partial_types)[1]

    def _pre_check(
        self, *args: Var | Any
    ) -> Tuple[Callable[[Any], Optional[str]], ...]:
        """Check if the function can be called with the given arguments.

        Args:
            *args: The arguments to call the function with.

        Returns:
            True if the function can be called with the given arguments.
        """
        return ()

    @overload
    def __get__(self, instance: None, owner: Any) -> FunctionVar[CALLABLE_TYPE]: ...

    @overload
    def __get__(
        self: FunctionVar[ReflexCallable[Concatenate[V1, P], R]],
        instance: Var[V1],
        owner: Any,
    ) -> FunctionVar[ReflexCallable[P, R]]: ...

    def __get__(self, instance: Any, owner: Any):
        """Get the function var.

        Args:
            instance: The instance of the class.
            owner: The owner of the class.

        Returns:
            The function var.
        """
        if instance is None:
            return self
        return self.partial(instance)

    __call__ = call


@dataclasses.dataclass(frozen=True)
class ExpressionCall(CachedVarOperation, Var[R]):
    """Class for expression calls."""

    _original_var_operation: Callable = dataclasses.field(default=lambda *args: "")
    _args: Tuple[Var, ...] = dataclasses.field(default_factory=tuple)

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return self._original_var_operation(*self._args)

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the var data associated with the var.

        Returns:
            All the var data associated with the var.
        """
        return VarData.merge(
            *[arg._get_all_var_data() for arg in self._args],
            self._var_data,
        )

    @classmethod
    def create(
        cls,
        _original_var_operation: Callable,
        *args: Var | Any,
        _var_type: GenericType = Any,
        _var_data: VarData | None = None,
    ) -> ExpressionCall:
        """Create a new expression call.

        Args:
            _original_var_operation: The original var operation.
            *args: The arguments to call the expression with.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The expression call var.
        """
        return ExpressionCall(
            _js_expr="",
            _var_type=_var_type,
            _var_data=_var_data,
            _original_var_operation=_original_var_operation,
            _args=args,
        )


class BuilderFunctionVar(
    FunctionVar[CALLABLE_TYPE], default_type=ReflexCallable[Any, Any]
):
    """Base class for immutable function vars with the builder pattern."""

    __call__ = FunctionVar.partial


class FunctionStringVar(FunctionVar[CALLABLE_TYPE]):
    """Base class for immutable function vars from a string."""

    @classmethod
    def create(
        cls,
        func: str,
        _var_type: Type[OTHER_CALLABLE_TYPE] = ReflexCallable[Any, Any],
        _var_data: VarData | None = None,
    ) -> FunctionStringVar[OTHER_CALLABLE_TYPE]:
        """Create a new function var from a string.

        Args:
            func: The function to call.
            _var_type: The type of the Var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The function var.
        """
        return FunctionStringVar(
            _js_expr=func,
            _var_type=_var_type,
            _var_data=_var_data,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class VarOperationCall(Generic[P, R], CachedVarOperation, Var[R]):
    """Base class for immutable vars that are the result of a function call."""

    _func: Optional[FunctionVar[ReflexCallable[..., R]]] = dataclasses.field(
        default=None
    )
    _args: Tuple[Union[Var, Any], ...] = dataclasses.field(default_factory=tuple)

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """The name of the var.

        Returns:
            The name of the var.
        """
        return f"({self._func!s}({', '.join([str(LiteralVar.create(arg)) for arg in self._args])}))"

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get all the var data associated with the var.

        Returns:
            All the var data associated with the var.
        """
        return VarData.merge(
            self._func._get_all_var_data() if self._func is not None else None,
            *[LiteralVar.create(arg)._get_all_var_data() for arg in self._args],
            self._var_data,
        )

    @classmethod
    def create(
        cls,
        func: FunctionVar[ReflexCallable[P, R]],
        *args: Var | Any,
        _var_type: GenericType = Any,
        _var_data: VarData | None = None,
    ) -> VarOperationCall:
        """Create a new function call var.

        Args:
            func: The function to call.
            *args: The arguments to call the function with.
            _var_type: The type of the Var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The function call var.
        """
        function_return_type = (
            func._var_type.__args__[1]
            if getattr(func._var_type, "__args__", None)
            else Any
        )
        var_type = _var_type if _var_type is not Any else function_return_type
        return cls(
            _js_expr="",
            _var_type=var_type,
            _var_data=_var_data,
            _func=func,
            _args=args,
        )


@dataclasses.dataclass(frozen=True)
class DestructuredArg:
    """Class for destructured arguments."""

    fields: Tuple[str, ...] = ()
    rest: Optional[str] = None

    def to_javascript(self) -> str:
        """Convert the destructured argument to JavaScript.

        Returns:
            The destructured argument in JavaScript.
        """
        return format.wrap(
            ", ".join(self.fields) + (f", ...{self.rest}" if self.rest else ""),
            "{",
            "}",
        )


@dataclasses.dataclass(
    frozen=True,
)
class FunctionArgs:
    """Class for function arguments."""

    args: Tuple[Union[str, DestructuredArg], ...] = ()
    rest: Optional[str] = None


def format_args_function_operation(
    self: ArgsFunctionOperation | ArgsFunctionOperationBuilder,
) -> str:
    """Format an args function operation.

    Args:
        self: The function operation.

    Returns:
        The formatted args function operation.
    """
    arg_names_str = ", ".join(
        [
            (arg if isinstance(arg, str) else arg.to_javascript())
            + (
                f" = {default_value.default!s}"
                if i < len(self._default_values)
                and not isinstance(
                    (default_value := self._default_values[i]), inspect.Parameter.empty
                )
                else ""
            )
            for i, arg in enumerate(self._args.args)
        ]
        + ([f"...{self._args.rest}"] if self._args.rest else [])
    )

    return_expr_str = str(LiteralVar.create(self._return_expr))

    # Wrap return expression in curly braces if explicit return syntax is used.
    return_expr_str_wrapped = (
        format.wrap(return_expr_str, "{", "}")
        if self._explicit_return
        else return_expr_str
    )

    return f"(({arg_names_str}) => {return_expr_str_wrapped})"


def pre_check_args(
    self: ArgsFunctionOperation | ArgsFunctionOperationBuilder, *args: Var | Any
) -> Tuple[Callable[[Any], Optional[str]], ...]:
    """Check if the function can be called with the given arguments.

    Args:
        self: The function operation.
        *args: The arguments to call the function with.

    Returns:
        True if the function can be called with the given arguments.

    Raises:
        VarTypeError: If the arguments are invalid.
    """
    for i, (validator, arg) in enumerate(zip(self._validators, args, strict=False)):
        if (validation_message := validator(arg)) is not None:
            arg_name = self._args.args[i] if i < len(self._args.args) else None
            if arg_name is not None:
                raise VarTypeError(
                    f"Invalid argument {arg!s} provided to {arg_name} in {self._function_name or 'var operation'}. {validation_message}"
                )
            raise VarTypeError(
                f"Invalid argument {arg!s} provided to argument {i} in {self._function_name or 'var operation'}. {validation_message}"
            )
    return self._validators[len(args) :]


def figure_partial_type(
    self: ArgsFunctionOperation | ArgsFunctionOperationBuilder,
    *args: Var | Any,
) -> Tuple[GenericType, Optional[TypeComputer]]:
    """Figure out the return type of the function.

    Args:
        self: The function operation.
        *args: The arguments to call the function with.

    Returns:
        The return type of the function.
    """
    return (
        self._type_computer(*args)
        if self._type_computer is not None
        else FunctionVar._partial_type(self, *args)
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class ArgsFunctionOperation(CachedVarOperation, FunctionVar[CALLABLE_TYPE]):
    """Base class for immutable function defined via arguments and return expression."""

    _args: FunctionArgs = dataclasses.field(default_factory=FunctionArgs)
    _default_values: Tuple[VarWithDefault | inspect.Parameter.empty, ...] = (
        dataclasses.field(default_factory=tuple)
    )
    _validators: Tuple[Callable[[Any], Optional[str]], ...] = dataclasses.field(
        default_factory=tuple
    )
    _return_expr: Union[Var, Any] = dataclasses.field(default=None)
    _function_name: str = dataclasses.field(default="")
    _type_computer: Optional[TypeComputer] = dataclasses.field(default=None)
    _explicit_return: bool = dataclasses.field(default=False)
    _raw_js_function: str | None = dataclasses.field(default=None)
    _original_var_operation: Callable | None = dataclasses.field(default=None)

    _cached_var_name = cached_property_no_lock(format_args_function_operation)

    _pre_check = pre_check_args

    _partial_type = figure_partial_type

    @classmethod
    def create(
        cls,
        args_names: Sequence[Union[str, DestructuredArg]],
        return_expr: Var | Any,
        default_values: Sequence[VarWithDefault | inspect.Parameter.empty] = (),
        rest: str | None = None,
        validators: Sequence[Callable[[Any], Optional[str]]] = (),
        function_name: str = "",
        explicit_return: bool = False,
        type_computer: Optional[TypeComputer] = None,
        _raw_js_function: str | None = None,
        _original_var_operation: Callable | None = None,
        _var_type: GenericType = Callable,
        _var_data: VarData | None = None,
    ):
        """Create a new function var.

        Args:
            args_names: The names of the arguments.
            return_expr: The return expression of the function.
            default_values: The default values of the arguments.
            rest: The name of the rest argument.
            validators: The validators for the arguments.
            function_name: The name of the function.
            explicit_return: Whether to use explicit return syntax.
            type_computer: A function to compute the return type.
            _raw_js_function: If provided, it will be used when the operation is being called with all of its arguments at once.
            _original_var_operation: The original var operation, if any.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The function var.
        """
        return_expr = Var.create(return_expr)
        return cls(
            _js_expr="",
            _var_type=_var_type,
            _var_data=_var_data,
            _args=FunctionArgs(args=tuple(args_names), rest=rest),
            _raw_js_function=_raw_js_function,
            _original_var_operation=_original_var_operation,
            _default_values=tuple(default_values),
            _function_name=function_name,
            _validators=tuple(validators),
            _return_expr=return_expr,
            _explicit_return=explicit_return,
            _type_computer=type_computer,
        )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class ArgsFunctionOperationBuilder(
    CachedVarOperation, BuilderFunctionVar[CALLABLE_TYPE]
):
    """Base class for immutable function defined via arguments and return expression with the builder pattern."""

    _args: FunctionArgs = dataclasses.field(default_factory=FunctionArgs)
    _default_values: Tuple[VarWithDefault | inspect.Parameter.empty, ...] = (
        dataclasses.field(default_factory=tuple)
    )
    _validators: Tuple[Callable[[Any], Optional[str]], ...] = dataclasses.field(
        default_factory=tuple
    )
    _return_expr: Union[Var, Any] = dataclasses.field(default=None)
    _function_name: str = dataclasses.field(default="")
    _type_computer: Optional[TypeComputer] = dataclasses.field(default=None)
    _explicit_return: bool = dataclasses.field(default=False)
    _raw_js_function: str | None = dataclasses.field(default=None)
    _original_var_operation: Callable | None = dataclasses.field(default=None)

    _cached_var_name = cached_property_no_lock(format_args_function_operation)

    _pre_check = pre_check_args

    _partial_type = figure_partial_type

    @classmethod
    def create(
        cls,
        args_names: Sequence[Union[str, DestructuredArg]],
        return_expr: Var | Any,
        default_values: Sequence[VarWithDefault | inspect.Parameter.empty] = (),
        rest: str | None = None,
        validators: Sequence[Callable[[Any], Optional[str]]] = (),
        function_name: str = "",
        explicit_return: bool = False,
        type_computer: Optional[TypeComputer] = None,
        _raw_js_function: str | None = None,
        _original_var_operation: Callable | None = None,
        _var_type: GenericType = Callable,
        _var_data: VarData | None = None,
    ):
        """Create a new function var.

        Args:
            args_names: The names of the arguments.
            return_expr: The return expression of the function.
            default_values: The default values of the arguments.
            rest: The name of the rest argument.
            validators: The validators for the arguments.
            function_name: The name of the function.
            explicit_return: Whether to use explicit return syntax.
            type_computer: A function to compute the return type.
            _raw_js_function: If provided, it will be used when the operation is being called with all of its arguments at once.
            _original_var_operation: The original var operation, if any.
            _var_type: The type of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The function var.
        """
        return_expr = Var.create(return_expr)
        return cls(
            _js_expr="",
            _var_type=_var_type,
            _var_data=_var_data,
            _args=FunctionArgs(args=tuple(args_names), rest=rest),
            _raw_js_function=_raw_js_function,
            _original_var_operation=_original_var_operation,
            _default_values=tuple(default_values),
            _function_name=function_name,
            _validators=tuple(validators),
            _return_expr=return_expr,
            _explicit_return=explicit_return,
            _type_computer=type_computer,
        )


if python_version := sys.version_info[:2] >= (3, 10):
    JSON_STRINGIFY = FunctionStringVar.create(
        "JSON.stringify", _var_type=ReflexCallable[[Any], str]
    )
    ARRAY_ISARRAY = FunctionStringVar.create(
        "Array.isArray", _var_type=ReflexCallable[[Any], bool]
    )
    PROTOTYPE_TO_STRING = FunctionStringVar.create(
        "((__to_string) => __to_string.toString())",
        _var_type=ReflexCallable[[Any], str],
    )
else:
    JSON_STRINGIFY = FunctionStringVar.create(
        "JSON.stringify", _var_type=ReflexCallable[Any, str]
    )
    ARRAY_ISARRAY = FunctionStringVar.create(
        "Array.isArray", _var_type=ReflexCallable[Any, bool]
    )
    PROTOTYPE_TO_STRING = FunctionStringVar.create(
        "((__to_string) => __to_string.toString())",
        _var_type=ReflexCallable[Any, str],
    )


def _generate_overloads_for_function_var_call(maximum_args: int = 4) -> str:
    """Generate overloads for the function var call method.

    Args:
        maximum_args: The maximum number of arguments to generate overloads for.

    Returns:
        The generated overloads.
    """
    overloads = []
    return_type_mapping = {
        "bool": "BooleanVar",
        "int": "NumberVar[int]",
        "float": "NumberVar[float]",
        "str": "StringVar[str]",
        "SEQUENCE_TYPE": "ArrayVar[SEQUENCE_TYPE]",
        "MAPPING_TYPE": "ObjectVar[MAPPING_TYPE]",
        "R": "Var[R]",
    }
    for number_of_required_args in range(maximum_args + 1):
        for number_of_optional_args in range(
            maximum_args + 1 - number_of_required_args
        ):
            for return_type, return_type_var in return_type_mapping.items():
                required_args = [
                    f"arg{j + 1}: Union[V" f"{j + 1}, Var[V{j + 1}]]"
                    for j in range(number_of_required_args)
                ]
                optional_args = [
                    f"arg{j + 1}: Union[V" f"{j + 1}, Var[V{j + 1}], Unset] = Unset()"
                    for j in range(
                        number_of_required_args,
                        number_of_required_args + number_of_optional_args,
                    )
                ]
                required_params = [f"V{j + 1}" for j in range(number_of_required_args)]
                optional_params = [
                    f"VarWithDefault[V{j + 1}]"
                    for j in range(
                        number_of_required_args,
                        number_of_required_args + number_of_optional_args,
                    )
                ]
                function_type_hint = f"""FunctionVar[ReflexCallable[[{", ".join(required_params + optional_params)}], {return_type}]]"""
                new_line = "\n"
                overloads.append(
                    f"""
    @overload
    def call(
        self: {function_type_hint},
        {"," + new_line + "        ".join(required_args + optional_args)}
    ) -> {return_type_var}: ...
    """
                )
    return "\n".join(overloads)
