"""rx.match."""

from typing import Any, Union, cast

from typing_extensions import Unpack

from reflex.components.base import Fragment
from reflex.components.component import BaseComponent, Component
from reflex.utils import types
from reflex.utils.exceptions import MatchTypeError
from reflex.vars.base import VAR_TYPE, Var
from reflex.vars.number import MatchOperation

CASE_TYPE = tuple[Unpack[tuple[Any, ...]], Var[VAR_TYPE] | VAR_TYPE]


def _process_match_cases(cases: tuple[CASE_TYPE[VAR_TYPE], ...]):
    """Process the individual match cases.

    Args:
        cases: The match cases.

    Raises:
        ValueError: If the default case is not the last case or the tuple elements are less than 2.
    """
    for case in cases:
        if not isinstance(case, tuple):
            raise ValueError(
                "rx.match should have tuples of cases and a default case as the last argument."
            )

        # There should be at least two elements in a case tuple(a condition and return value)
        if len(case) < 2:
            raise ValueError(
                "A case tuple should have at least a match case element and a return value."
            )


def _validate_return_types(match_cases: tuple[CASE_TYPE[VAR_TYPE], ...]) -> None:
    """Validate that match cases have the same return types.

    Args:
        match_cases: The match cases.

    Raises:
        MatchTypeError: If the return types of cases are different.
    """

    def is_component_or_component_var(obj: Any) -> bool:
        return types._isinstance(obj, BaseComponent) or (
            isinstance(obj, Var)
            and types.safe_typehint_issubclass(
                obj._var_type, Union[list[BaseComponent], BaseComponent]
            )
        )

    def type_of_return_type(obj: Any) -> Any:
        if isinstance(obj, Var):
            return obj._var_type
        return type(obj)

    return_types = [case[-1] for case in match_cases]

    if any(
        is_component_or_component_var(return_type) for return_type in return_types
    ) and not all(
        is_component_or_component_var(return_type) for return_type in return_types
    ):
        non_component_return_types = [
            (type_of_return_type(return_type), i)
            for i, return_type in enumerate(return_types)
            if not is_component_or_component_var(return_type)
        ]
        raise MatchTypeError(
            "Match cases should have the same return types. "
            + "Expected return types to be of type Component or Var[Component]. "
            + ". ".join(
                [
                    f"Return type of case {i} is {return_type}"
                    for return_type, i in non_component_return_types
                ]
            )
        )


def _create_match_var(
    match_cond_var: Var,
    match_cases: tuple[CASE_TYPE[VAR_TYPE], ...],
    default: VAR_TYPE | Var[VAR_TYPE],
) -> Var[VAR_TYPE]:
    """Create the match var.

    Args:
        match_cond_var: The match condition var.
        match_cases: The match cases.
        default: The default case.

    Returns:
        The match var.
    """
    return MatchOperation.create(match_cond_var, match_cases, default)


def match(
    cond: Any,
    *cases: Unpack[
        tuple[Unpack[tuple[CASE_TYPE[VAR_TYPE], ...]], Var[VAR_TYPE] | VAR_TYPE]
    ],
) -> Var[VAR_TYPE]:
    """Create a match var.

    Args:
        cond: The condition to match.
        cases: The match cases. Each case should be a tuple with the first elements as the match case and the last element as the return value. The last argument should be the default case.

    Returns:
        The match var.

    Raises:
        ValueError: If the default case is not the last case or the tuple elements are less than 2.
    """
    default = None

    if len([case for case in cases if not isinstance(case, tuple)]) > 1:
        raise ValueError("rx.match can only have one default case.")

    if not cases:
        raise ValueError("rx.match should have at least one case.")

    # Get the default case which should be the last non-tuple arg
    if not isinstance(cases[-1], tuple):
        default = cases[-1]
        actual_cases = cases[:-1]
    else:
        actual_cases = cast(tuple[CASE_TYPE[VAR_TYPE], ...], cases)

    _process_match_cases(actual_cases)

    _validate_return_types(actual_cases)

    if default is None and any(
        not (
            isinstance((return_type := case[-1]), Component)
            or (
                isinstance(return_type, Var)
                and types.typehint_issubclass(return_type._var_type, Component)
            )
        )
        for case in actual_cases
    ):
        raise ValueError(
            "For cases with return types as Vars, a default case must be provided"
        )
    elif default is None:
        default = Fragment.create()

    default = cast(Var[VAR_TYPE] | VAR_TYPE, default)

    return _create_match_var(
        cond,
        actual_cases,
        default,
    )
