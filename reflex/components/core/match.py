"""rx.match."""

import textwrap
from typing import Any, Dict, List, Optional, Tuple, Union

from reflex.components.base import Fragment
from reflex.components.component import BaseComponent, Component, MemoizationLeaf
from reflex.components.core.colors import Color
from reflex.components.tags import MatchTag, Tag
from reflex.style import Style
from reflex.utils import format, imports, types
from reflex.utils.exceptions import MatchTypeError
from reflex.vars import BaseVar, Var, VarData


class Match(MemoizationLeaf):
    """Match cases based on a condition."""

    # The condition to determine which case to match.
    cond: Var[Any]

    # The list of match cases to be matched.
    match_cases: List[Any] = []

    # The catchall case to match.
    default: Any

    @classmethod
    def create(cls, cond: Any, *cases) -> Union[Component, BaseVar]:
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

        cls._validate_return_types(match_cases)

        if default is None and types._issubclass(type(match_cases[0][-1]), BaseVar):
            raise ValueError(
                "For cases with return types as Vars, a default case must be provided"
            )

        return cls._create_match_cond_var_or_component(
            match_cond_var, match_cases, default
        )

    @classmethod
    def _create_condition_var(cls, cond: Any) -> BaseVar:
        """Convert the condition to a Var.

        Args:
            cond: The condition.

        Returns:
            The condition as a base var

        Raises:
            ValueError: If the condition is not provided.
        """
        match_cond_var = Var.create(cond, _var_is_string=type(cond) is str)

        if match_cond_var is None:
            raise ValueError("The condition must be set")
        return match_cond_var  # type: ignore

    @classmethod
    def _process_cases(
        cls, cases: List
    ) -> Tuple[List, Optional[Union[BaseVar, BaseComponent]]]:
        """Process the list of match cases and the catchall default case.

        Args:
            cases: The list of match cases.

        Returns:
            The default case and the list of match case tuples.

        Raises:
            ValueError: If there are multiple default cases.
        """
        default = None

        if len([case for case in cases if not isinstance(case, tuple)]) > 1:
            raise ValueError("rx.match can only have one default case.")

        # Get the default case which should be the last non-tuple arg
        if not isinstance(cases[-1], tuple):
            default = cases.pop()
            default = (
                cls._create_case_var_with_var_data(default)
                if not isinstance(default, BaseComponent)
                else default
            )

        return cases, default  # type: ignore

    @classmethod
    def _create_case_var_with_var_data(cls, case_element):
        """Convert a case element into a Var.If the case
        is a Style type, we extract the var data and merge it with the
        newly created Var.

        Args:
            case_element: The case element.

        Returns:
            The case element Var.
        """
        _var_data = case_element._var_data if isinstance(case_element, Style) else None  # type: ignore
        case_element = Var.create(
            case_element,
            _var_is_string=type(case_element) is str or isinstance(case_element, Color),
        )
        if _var_data is not None:
            case_element._var_data = VarData.merge(case_element._var_data, _var_data)  # type: ignore
        return case_element

    @classmethod
    def _process_match_cases(cls, cases: List) -> List[List[BaseVar]]:
        """Process the individual match cases.

        Args:
            cases: The match cases.

        Returns:
            The processed match cases.

        Raises:
            ValueError: If the default case is not the last case or the tuple elements are less than 2.
        """
        match_cases = []
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

            case_list = []
            for element in case:
                # convert all non component element to vars.
                el = (
                    cls._create_case_var_with_var_data(element)
                    if not isinstance(element, BaseComponent)
                    else element
                )
                if not isinstance(el, (BaseVar, BaseComponent)):
                    raise ValueError("Case element must be a var or component")
                case_list.append(el)

            match_cases.append(case_list)

        return match_cases

    @classmethod
    def _validate_return_types(cls, match_cases: List[List[BaseVar]]) -> None:
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
        elif types._isinstance(first_case_return, BaseVar):
            return_type = BaseVar

        for index, case in enumerate(match_cases):
            if not types._issubclass(type(case[-1]), return_type):
                raise MatchTypeError(
                    f"Match cases should have the same return types. Case {index} with return "
                    f"value `{case[-1]._var_name if isinstance(case[-1], BaseVar) else textwrap.shorten(str(case[-1]), width=250)}`"
                    f" of type {type(case[-1])!r} is not {return_type}"
                )

    @classmethod
    def _create_match_cond_var_or_component(
        cls,
        match_cond_var: Var,
        match_cases: List[List[BaseVar]],
        default: Optional[Union[BaseVar, BaseComponent]],
    ) -> Union[Component, BaseVar]:
        """Create and return the match condition var or component.

        Args:
            match_cond_var: The match condition.
            match_cases: The list of match cases.
            default: The default case.

        Returns:
            The match component wrapped in a fragment or the match var.

        Raises:
            ValueError: If the return types are not vars when creating a match var for Var types.
        """
        if default is None and types._issubclass(
            type(match_cases[0][-1]), BaseComponent
        ):
            default = Fragment.create()

        if types._issubclass(type(match_cases[0][-1]), BaseComponent):
            return Fragment.create(
                cls(
                    cond=match_cond_var,
                    match_cases=match_cases,
                    default=default,
                    children=[case[-1] for case in match_cases] + [default],  # type: ignore
                )
            )

        # Validate the match cases (as well as the default case) to have Var return types.
        if any(
            case for case in match_cases if not types._isinstance(case[-1], BaseVar)
        ) or not types._isinstance(default, BaseVar):
            raise ValueError("Return types of match cases should be Vars.")

        # match cases and default should all be Vars at this point.
        # Retrieve var data of every var in the match cases and default.
        var_data = [
            *[el._var_data for case in match_cases for el in case],
            default._var_data,  # type: ignore
        ]

        return match_cond_var._replace(
            _var_name=format.format_match(
                cond=match_cond_var._var_name_unwrapped,
                match_cases=match_cases,  # type: ignore
                default=default,  # type: ignore
            ),
            _var_type=default._var_type,  # type: ignore
            _var_is_local=False,
            _var_full_name_needs_state_prefix=False,
            _var_is_string=False,
            merge_var_data=VarData.merge(*var_data),
        )

    def _render(self) -> Tag:
        return MatchTag(
            cond=self.cond, match_cases=self.match_cases, default=self.default
        )

    def render(self) -> Dict:
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        tag = self._render()
        tag.name = "match"
        return dict(tag)

    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            getattr(self.cond._var_data, "imports", {}),
        )

    def _apply_theme(self, theme: Component):
        """Apply the theme to this component.

        Args:
            theme: The theme to apply.
        """
        # apply theme to return components.
        for match_case in self.match_cases:
            if isinstance(match_case[-1], Component):
                match_case[-1].apply_theme(theme)

        # apply theme to default component
        if isinstance(self.default, Component):
            self.default.apply_theme(theme)
