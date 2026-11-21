"""A bare component."""

from __future__ import annotations

import functools
import logging
from collections.abc import Iterator, Sequence
from typing import Any

from reflex_base.components.component import BaseComponent, Component, ComponentStyle
from reflex_base.components.tags import CommonTag
from reflex_base.components.tags.tagless import Tagless
from reflex_base.environment import PerformanceMode, environment
from reflex_base.utils.decorator import once
from reflex_base.vars import BooleanVar, ObjectVar, Var
from reflex_base.vars.base import GLOBAL_CACHE, VarData
from reflex_base.vars.sequence import LiteralStringVar

logger = logging.getLogger(__name__)


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
            logger.warning(
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
        for component in self._contents_components():
            hooks |= component._get_all_hooks_internal()
        return hooks

    def _get_all_hooks(self) -> dict[str, VarData | None]:
        """Include the hooks for the component.

        Returns:
            The hooks for the component.
        """
        hooks = super()._get_all_hooks()
        for component in self._contents_components():
            hooks |= component._get_all_hooks()
        return hooks

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
        for component in self._contents_components():
            component_id = id(component)
            if isinstance(component, Component) and component_id not in ignore_ids:
                ignore_ids.add(component_id)
                app_wrap_components |= component._get_all_app_wrap_components(
                    ignore_ids=ignore_ids
                )
        return app_wrap_components

    @functools.cached_property
    def _get_component_prop_property(self) -> Sequence[BaseComponent]:
        """The components of the props and of the var rendered for the contents.

        The compiler and the import, custom code, dynamic import and ref collectors
        follow this traversal, so components a custom ``to_string()`` brings count.

        Returns:
            Each component of the props, then the rendered var's others.
        """
        components = super()._get_component_prop_property
        seen = {id(component) for component in components}
        return [
            *components,
            *(c for c in self._contents_components() if id(c) not in seen),
        ]

    def _contents_vars(self) -> tuple[Var, ...]:
        """The contents and, when it differs, the var rendered for them, built once.

        The rendered var shows booleans and objects as their string form.

        Returns:
            The vars, the rendered one last.
        """
        contents = self.contents
        cached = self.__dict__.get("_vars_cache")
        # The base class's vars cache, dropped with the other compile caches;
        # keyed on the contents too, so reassigning them never renders stale.
        if cached is not None and cached[0] is contents:
            return cached
        rendered = contents if isinstance(contents, Var) else Var.create(contents)
        if isinstance(rendered, (BooleanVar, ObjectVar)):
            rendered = rendered.to_string()
        cached = (contents,) if rendered is contents else (contents, rendered)
        self._vars_cache = cached
        return cached

    def _contents_components(self) -> Iterator[BaseComponent]:
        """The components carried by the contents and the var rendered for them.

        A custom ``to_string()`` can bring components the contents lack.

        Yields:
            Each component once, those of the contents first.
        """
        seen: set[int] = set()
        for var in self._contents_vars():
            for component in _components_from_var(var):
                if id(component) not in seen:
                    seen.add(id(component))
                    yield component

    def _render(self) -> CommonTag:
        return Tagless(contents=f"{self._contents_vars()[-1]!s}")

    def render(self) -> dict:
        """Render the component as a dictionary.

        This is overridden to provide a short performant path for rendering.

        Returns:
            The rendered component.
        """
        return {"contents": f"{self._contents_vars()[-1]!s}"}

    def _add_style_recursive(
        self, style: ComponentStyle, theme: Component | None = None
    ) -> Component:
        """Add style to the component and its children.

        Args:
            style: The style to add.
            theme: The theme to add.

        Returns:
            The component with the style added.
        """
        new_self = super()._add_style_recursive(style, theme)

        are_components_touched = False

        for component in self._contents_components():
            if isinstance(component, Component):
                component._add_style_recursive(style, theme)
                are_components_touched = True

        if are_components_touched:
            GLOBAL_CACHE.clear()

        return new_self

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in this component.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            The contents, and the var rendered for them when that differs.
        """
        yield from self._contents_vars()
