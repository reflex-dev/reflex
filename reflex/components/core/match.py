"""rx.match."""

import textwrap
from typing import Any, cast

from reflex.components.base import Fragment
from reflex.components.component import BaseComponent, Component, MemoizationLeaf, field
from reflex.components.tags import Tag
from reflex.components.tags.match_tag import MatchTag
from reflex.style import Style
from reflex.utils import format
from reflex.utils.exceptions import MatchTypeError
from reflex.utils.imports import ImportDict
from reflex.vars import VarData
from reflex.vars.base import LiteralVar, Var


class Match(MemoizationLeaf):
    """Match cases based on a condition."""

    # The condition to determine which case to match.
    cond: Var[Any]

    # The list of match cases to be matched.
    match_cases: list[tuple[list[Var], BaseComponent]] = field(
        default_factory=list, is_javascript_property=False
    )

    # The catchall case to match.
    default: BaseComponent = field(
        default_factory=Fragment.create, is_javascript_property=False
    )

    @classmethod
    def create(cls, cond: Any, *cases) -> Component | Var:
        """Create a Match Component.

        Args:
            cond: The condition to determine which case to match.
            cases: This list of cases to match.

        Returns:
            The match component.

        Raises:
            ValueError: When a default case is not provided for cases with Var return types.
        """
        match_cond_var = cls._create_condition_var(cond)
        cases, default = cls._process_cases(list(cases))
        match_cases = cls._process_match_cases(cases)

        match_cases = cls._validate_return_types(match_cases)

        if default is None and isinstance(match_cases[0][1], Var):
            msg = "For cases with return types as Vars, a default case must be provided"
            raise ValueError(msg)

        return cls._create_match_cond_var_or_component(
            match_cond_var, match_cases, default
        )

    @classmethod
    def _create_condition_var(cls, cond: Any) -> Var:
        """Convert the condition to a Var.

        Args:
            cond: The condition.

        Returns:
            The condition as a base var

        Raises:
            ValueError: If the condition is not provided.
        """
        match_cond_var = LiteralVar.create(cond)

        if match_cond_var is None:
            msg = "The condition must be set"
            raise ValueError(msg)
        return match_cond_var

    @classmethod
    def _process_cases(
        cls, cases: list
    ) -> tuple[list[tuple], Var | BaseComponent | None]:
        """Process the list of match cases and the catchall default case.

        Args:
            cases: The list of match cases.

        Returns:
            The default case and the list of match case tuples.

        Raises:
            ValueError: If there are multiple default cases.
        """
        if not cases:
            msg = "rx.match should have at least one case."
            raise ValueError(msg)

        if not isinstance(cases[-1], tuple):
            *cases, default_return = cases
            default_return = (
                cls._create_case_var_with_var_data(default_return)
                if not isinstance(default_return, BaseComponent)
                else default_return
            )
        else:
            default_return = None

        if any(case for case in cases if not isinstance(case, tuple)):
            msg = "rx.match should have tuples of cases and one default case as the last argument."
            raise ValueError(msg)

        if not cases:
            msg = "rx.match should have at least one case."
            raise ValueError(msg)

        return cases, default_return

    @classmethod
    def _create_case_var_with_var_data(cls, case_element: Any) -> Var:
        """Convert a case element into a Var.If the case
        is a Style type, we extract the var data and merge it with the
        newly created Var.

        Args:
            case_element: The case element.

        Returns:
            The case element Var.
        """
        var_data = case_element._var_data if isinstance(case_element, Style) else None
        return LiteralVar.create(case_element, _var_data=var_data)

    @classmethod
    def _process_match_cases(
        cls, cases: list[tuple]
    ) -> list[tuple[list[Var], BaseComponent | Var]]:
        """Process the individual match cases.

        Args:
            cases: The match cases.

        Returns:
            The processed match cases.

        Raises:
            ValueError: If the default case is not the last case or the tuple elements are less than 2.
        """
        match_cases: list[tuple[list[Var], BaseComponent | Var]] = []
        for case_index, case in enumerate(cases):
            # There should be at least two elements in a case tuple(a condition and return value)
            if len(case) < 2:
                msg = "A case tuple should have at least a match case element and a return value."
                raise ValueError(msg)

            *conditions, return_value = case

            conditions_vars: list[Var] = []
            for condition_index, condition in enumerate(conditions):
                if isinstance(condition, BaseComponent):
                    msg = f"Match condition {condition_index} of case {case_index} cannot be a component."
                    raise ValueError(msg)
                conditions_vars.append(cls._create_case_var_with_var_data(condition))

            return_value = (
                cls._create_case_var_with_var_data(return_value)
                if not isinstance(return_value, BaseComponent)
                else return_value
            )

            if not isinstance(return_value, (Var, BaseComponent)):
                msg = "Return value must be a var or component"
                raise ValueError(msg)

            match_cases.append((conditions_vars, return_value))

        return match_cases

    @classmethod
    def _validate_return_types(
        cls, match_cases: list[tuple[list[Var], BaseComponent | Var]]
    ) -> list[tuple[list[Var], Var]] | list[tuple[list[Var], BaseComponent]]:
        """Validate that match cases have the same return types.

        Args:
            match_cases: The match cases.

        Returns:
            The validated match cases.

        Raises:
            MatchTypeError: If the return types of cases are different.
        """
        first_case_return = match_cases[0][-1]
        return_type = type(first_case_return)

        if isinstance(first_case_return, BaseComponent):
            return_type = BaseComponent
        elif isinstance(first_case_return, Var):
            return_type = Var

        cases = []
        for index, case in enumerate(match_cases):
            conditions, return_value = case
            if not isinstance(return_value, return_type):
                msg = (
                    f"Match cases should have the same return types. Case {index} with return "
                    f"value `{return_value._js_expr if isinstance(return_value, Var) else textwrap.shorten(str(return_value), width=250)}`"
                    f" of type {type(return_value)!r} is not {return_type}"
                )
                raise MatchTypeError(msg)
            cases.append((conditions, return_value))
        return cases

    @classmethod
    def _create_match_cond_var_or_component(
        cls,
        match_cond_var: Var,
        match_cases: list[tuple[list[Var], BaseComponent]]
        | list[tuple[list[Var], Var]],
        default: Var | BaseComponent | None,
    ) -> Component | Var:
        """Create and return the match condition var or component.

        Args:
            match_cond_var: The match condition.
            match_cases: The list of match cases.
            default: The default case.

        Returns:
            The match component wrapped in a fragment or the match var.
        """
        if isinstance(match_cases[0][1], BaseComponent):
            if default is None:
                default = Fragment.create()

            return Fragment.create(
                cls._create(
                    cond=match_cond_var,
                    match_cases=match_cases,
                    default=default,
                    children=[case[1] for case in match_cases] + [default],  # pyright: ignore [reportArgumentType]
                )
            )

        match_cases = cast("list[tuple[list[Var], Var]]", match_cases)
        default = cast("Var", default)

        return Var(
            _js_expr=format.format_match(
                cond=str(match_cond_var),
                match_cases=match_cases,
                default=default,
            ),
            _var_type=default._var_type,
            _var_data=VarData.merge(
                match_cond_var._get_all_var_data(),
                *[el._get_all_var_data() for case in match_cases for el in case[0]],
                *[case[1]._get_all_var_data() for case in match_cases],
                default._get_all_var_data(),
            ),
        )

    def _render(self) -> Tag:
        return MatchTag(
            cond=str(self.cond),
            match_cases=[
                ([str(cond) for cond in conditions], return_value.render())
                for conditions, return_value in self.match_cases
            ],
            default=self.default.render(),
        )

    def render(self) -> dict:
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        return dict(self._render())

    def add_imports(self) -> ImportDict:
        """Add imports for the Match component.

        Returns:
            The import dict.
        """
        var_data = VarData.merge(self.cond._get_all_var_data())
        return var_data.old_school_imports() if var_data else {}


match = Match.create
