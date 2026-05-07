"""A bare component."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from typing import Any

from reflex_base.components.component import BaseComponent, Component, ComponentStyle
from reflex_base.components.tags import Tag
from reflex_base.components.tags.tagless import Tagless
from reflex_base.environment import PerformanceMode, environment
from reflex_base.utils import console
from reflex_base.utils.decorator import once
from reflex_base.utils.imports import ParsedImportDict
from reflex_base.vars import BooleanVar, ObjectVar, Var
from reflex_base.vars.base import VarData
from reflex_base.vars.sequence import LiteralStringVar


@once
def get_performance_mode():
    """Get the performance mode.

    Returns:
        The performance mode.
    """
    return environment.REFLEX_PERF_MODE.get()


def validate_str(value: str):
    """Validate a string value.

    Args:
        value: The value to validate.

    Raises:
        ValueError: If the value is a Var and the performance mode is set to raise.
    """
    perf_mode = get_performance_mode()
    if perf_mode != PerformanceMode.OFF and value.startswith("reflex___state"):
        if perf_mode == PerformanceMode.WARN:
            console.warn(
                f"Output includes {value!s} which will be displayed as a string. If you are calling `str` on a Var, consider using .to_string() instead."
            )
        elif perf_mode == PerformanceMode.RAISE:
            msg = f"Output includes {value!s} which will be displayed as a string. If you are calling `str` on a Var, consider using .to_string() instead."
            raise ValueError(msg)


def _components_from_var(var: Var) -> Sequence[BaseComponent]:
    var_data = var._get_all_var_data()
    return var_data.components if var_data else ()


class Bare(Component):
    """A component with no tag."""

    contents: Var[Any]

    @classmethod
    def create(cls, contents: Any) -> Component:
        """Create a Bare component, with no tag.

        Args:
            contents: The contents of the component.

        Returns:
            The component.
        """
        if isinstance(contents, Var):
            if isinstance(contents, LiteralStringVar):
                validate_str(contents._var_value)
            return cls._unsafe_create(children=[], contents=contents)
        if isinstance(contents, str):
            validate_str(contents)
        contents = Var.create(contents if contents is not None else "")

        return cls._unsafe_create(children=[], contents=contents)

    def _get_all_hooks_internal(self) -> dict[str, VarData | None]:
        """Include the hooks for the component.

        Returns:
            The hooks for the component.
        """
        hooks = super()._get_all_hooks_internal()
        if isinstance(self.contents, Var):
            for component in _components_from_var(self.contents):
                hooks |= component._get_all_hooks_internal()
        return hooks

    def _get_all_hooks(self) -> dict[str, VarData | None]:
        """Include the hooks for the component.

        Returns:
            The hooks for the component.
        """
        hooks = super()._get_all_hooks()
        if isinstance(self.contents, Var):
            for component in _components_from_var(self.contents):
                hooks |= component._get_all_hooks()
        return hooks

    def _get_all_imports(self, collapse: bool = False) -> ParsedImportDict:
        """Include the imports for the component.

        Args:
            collapse: Whether to collapse the imports.

        Returns:
            The imports for the component.
        """
        imports = super()._get_all_imports(collapse=collapse)
        if isinstance(self.contents, Var):
            var_data = self.contents._get_all_var_data()
            if var_data:
                imports |= {k: list(v) for k, v in var_data.imports}
        return imports

    def _get_all_dynamic_imports(self) -> set[str]:
        """Get dynamic imports for the component.

        Returns:
            The dynamic imports.
        """
        dynamic_imports = super()._get_all_dynamic_imports()
        if isinstance(self.contents, Var):
            for component in _components_from_var(self.contents):
                dynamic_imports |= component._get_all_dynamic_imports()
        return dynamic_imports

    def _get_all_custom_code(self) -> dict[str, None]:
        """Get custom code for the component.

        Returns:
            The custom code.
        """
        custom_code = super()._get_all_custom_code()
        if isinstance(self.contents, Var):
            for component in _components_from_var(self.contents):
                custom_code |= component._get_all_custom_code()
        return custom_code

    def _get_all_app_wrap_components(
        self, *, ignore_ids: set[int] | None = None
    ) -> dict[tuple[int, str], Component]:
        """Get the components that should be wrapped in the app.

        Args:
            ignore_ids: The ids to ignore when collecting components.

        Returns:
            The components that should be wrapped in the app.
        """
        ignore_ids = ignore_ids or set()
        app_wrap_components = super()._get_all_app_wrap_components(
            ignore_ids=ignore_ids
        )
        if isinstance(self.contents, Var):
            for component in _components_from_var(self.contents):
                component_id = id(component)
                if isinstance(component, Component) and component_id not in ignore_ids:
                    ignore_ids.add(component_id)
                    app_wrap_components |= component._get_all_app_wrap_components(
                        ignore_ids=ignore_ids
                    )
        return app_wrap_components

    def _get_all_refs(self) -> dict[str, None]:
        """Get the refs for the children of the component.

        Returns:
            The refs for the children.
        """
        refs = super()._get_all_refs()
        if isinstance(self.contents, Var):
            for component in _components_from_var(self.contents):
                refs |= component._get_all_refs()
        return refs

    def _render(self) -> Tag:
        contents = (
            Var.create(self.contents)
            if not isinstance(self.contents, Var)
            else self.contents
        )
        if isinstance(contents, (BooleanVar, ObjectVar)):
            return Tagless(contents=f"{contents.to_string()!s}")
        return Tagless(contents=f"{contents!s}")

    def render(self) -> dict:
        """Render the component as a dictionary.

        This is overridden to provide a short performant path for rendering.

        Returns:
            The rendered component.
        """
        contents = (
            Var.create(self.contents)
            if not isinstance(self.contents, Var)
            else self.contents
        )
        if isinstance(contents, (BooleanVar, ObjectVar)):
            return {"contents": f"{contents.to_string()!s}"}
        return {"contents": f"{contents!s}"}

    def _add_style_recursive(
        self, style: ComponentStyle, theme: Component | None = None
    ) -> Component:
        """Add style to the component and its children.

        Args:
            style: The style to add.
            theme: The theme to add.

        Returns:
            A component with the style added; ``self`` if nothing changed.
        """
        new_self = super()._add_style_recursive(style, theme)

        if not isinstance(self.contents, Var):
            return new_self
        var_data = self.contents._var_data
        if not var_data or not var_data.components:
            return new_self

        rebuilt: list | None = None
        for i, embedded in enumerate(var_data.components):
            if not isinstance(embedded, Component):
                continue
            updated = embedded._add_style_recursive(style, theme)
            if updated is embedded:
                continue
            if rebuilt is None:
                rebuilt = list(var_data.components)
            rebuilt[i] = updated

        if rebuilt is None:
            return new_self

        new_var_data = VarData(
            state=var_data.state,
            field_name=var_data.field_name,
            imports=var_data.old_school_imports(),
            hooks=dict.fromkeys(var_data.hooks),
            deps=list(var_data.deps),
            position=var_data.position,
            components=tuple(rebuilt),
        )
        new_contents = dataclasses.replace(
            self.contents,
            _var_data=new_var_data,
        )
        return new_self.copy_with(contents=new_contents)

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in this component.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            The contents if it is a Var, otherwise nothing.
        """
        yield self.contents
