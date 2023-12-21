"""rx.match"""
from typing import Any, List, Dict, Optional, overload, Set

from reflex.components.component import BaseComponent, Component, MemoizationLeaf
from reflex.components.base import Fragment
from reflex.vars import BaseVar, Var
from reflex.components.tags import CondTag, Tag, MatchTag
from reflex.utils import format, imports, types

class Match(MemoizationLeaf):
    cond: Var[Any]

    match_cases: List[Any] = []

    default: Any

    @classmethod
    def create(cls, cond: Var, *cases):
        # Convert the condition to a Var.
        cond_var = Var.create(cond)
        assert cond_var is not None, "The condition must be set."

        cases = list(cases)
        default = None

        # Can only have one default
        if len([case for case in cases if not isinstance(case, tuple)]) > 1:
            raise ValueError("rx.match can only have one default case.")

        if not isinstance(cases[-1], tuple):
            default = cases.pop()
            default = Var.create(default) if not isinstance(default, BaseComponent) else default

        match_cases = []
        for case in cases:
            if not isinstance(case, tuple):
                # The default must be the last arg.
                raise ValueError("rx.match should have tuples of cases and default case as the last argument ")
            if len(case) < 2:
                raise ValueError("a case tuple should have at least a match case element and a return value ")

            case_list = []
            for element in case:
                el = Var.create(element) if not isinstance(element, BaseComponent) else element
                assert isinstance(el, (BaseVar, BaseComponent)), "case element must be a var or component"
                case_list.append(el)

            match_cases.append(case_list)

        return_type = BaseComponent if types._isinstance(match_cases[0][-1], BaseComponent) else BaseVar if types._isinstance(match_cases[0][-1], BaseVar) else type(match_cases[0][-1])

        # types.get_base_class()
        for case in match_cases:
            if not types._issubclass(type(case[-1]), return_type):
                raise TypeError("match cases should have the same return types")

        if default is None and types._issubclass(return_type, BaseVar):
            raise ValueError("For cases with return types as Vars, a default case must be provided")

        if default is None and types._issubclass(return_type, BaseComponent):
            default = Fragment.create()

        if types._issubclass(return_type, BaseComponent) :
            comp =  cls(
                cond=cond_var,
                match_cases=match_cases,
                default=default,
            )
            return Fragment.create(comp)

        return cond_var._replace(
            _var_name=format.format_match(
                cond = cond_var._var_full_name,
                match_cases=match_cases,
                default=default,

            ),
            _var_type=default._var_type,
            _var_is_local=False,
            _var_full_name_needs_state_prefix=False,
        )
    def _render(self) -> Tag:
        return MatchTag(
            cond = self.cond,
            match_cases=self.match_cases,
            default=self.default
        )
    def render(self) -> Dict:
        tag = self._render()
        tag.name = "match"
        tag.set(props=tag.format_props())
        a = dict(tag)
        return a


    def _get_imports(self):
        merged_imports = super()._get_imports()
        for case in self.match_cases:
            if isinstance(case[-1], BaseComponent):
                merged_imports = imports.merge_imports(merged_imports, case[-1].get_imports())
        if isinstance(self.default, BaseComponent):
            merged_imports = imports.merge_imports(merged_imports, self.default.get_imports())
        return merged_imports
