"""rx.match."""

import textwrap
from typing import Any, List, cast

from typing_extensions import Unpack

from reflex.components.base import Fragment
from reflex.components.component import BaseComponent, Component, MemoizationLeaf
from reflex.utils import types
from reflex.utils.exceptions import MatchTypeError
from reflex.vars.base import VAR_TYPE, Var
from reflex.vars.number import MatchOperation

CASE_TYPE = tuple[Unpack[tuple[Any, ...]], Var[VAR_TYPE] | VAR_TYPE]


class Match(MemoizationLeaf):
    """Match cases based on a condition."""

    # The condition to determine which case to match.
    cond: Var[Any]

    # The list of match cases to be matched.
    match_cases: List[Any] = []

    # The catchall case to match.
    default: Any

    @classmethod
    def create(
        cls,
        cond: Any,
        *cases: Unpack[
            tuple[Unpack[tuple[CASE_TYPE[VAR_TYPE], ...]], Var[VAR_TYPE] | VAR_TYPE]
        ],
    ) -> Var[VAR_TYPE]:
        """Create a Match Component.

        Args:
            cond: The condition to determine which case to match.
            cases: This list of cases to match.

        Returns:
            The match component.

        Raises:
            ValueError: When a default case is not provided for cases with Var return types.
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

        cls._process_match_cases(actual_cases)

        cls._validate_return_types(actual_cases)

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

        return cls._create_match_cond_var_or_component(
            cond,
            actual_cases,
            default,
        )

    @classmethod
    def _process_match_cases(cls, cases: tuple[CASE_TYPE[VAR_TYPE], ...]):
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

    @classmethod
    def _validate_return_types(
        cls, match_cases: tuple[CASE_TYPE[VAR_TYPE], ...]
    ) -> None:
        """Validate that match cases have the same return types.

        Args:
            match_cases: The match cases.

        Raises:
            MatchTypeError: If the return types of cases are different.
        """
        first_case_return = match_cases[0][-1]
        return_type = type(first_case_return)

        if types._isinstance(first_case_return, BaseComponent):
            return_type = BaseComponent
        elif types._isinstance(first_case_return, Var):
            return_type = Var

        for index, case in enumerate(match_cases):
            if not (
                types._issubclass(type(case[-1]), return_type)
                or (
                    isinstance(case[-1], Var)
                    and types.typehint_issubclass(case[-1]._var_type, return_type)
                )
            ):
                raise MatchTypeError(
                    f"Match cases should have the same return types. Case {index} with return "
                    f"value `{case[-1]._js_expr if isinstance(case[-1], Var) else textwrap.shorten(str(case[-1]), width=250)}`"
                    f" of type {(type(case[-1]) if not isinstance(case[-1], Var) else case[-1]._var_type)!r} is not {return_type}"
                )

    @classmethod
    def _create_match_cond_var_or_component(
        cls,
        match_cond_var: Var,
        match_cases: tuple[CASE_TYPE[VAR_TYPE], ...],
        default: VAR_TYPE | Var[VAR_TYPE],
    ) -> Var[VAR_TYPE]:
        """Create and return the match condition var or component.

        Args:
            match_cond_var: The match condition.
            match_cases: The list of match cases.
            default: The default case.

        Returns:
            The match component wrapped in a fragment or the match var.
        """
        return MatchOperation.create(match_cond_var, match_cases, default)


match = Match.create
