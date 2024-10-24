"""A bare component."""

from __future__ import annotations

from typing import Any, Iterator

from reflex.components.component import Component, LiteralComponentVar
from reflex.components.tags import Tag
from reflex.components.tags.tagless import Tagless
from reflex.utils.imports import ParsedImportDict
from reflex.vars import BooleanVar, ObjectVar, Var


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
            return cls(contents=contents)
        else:
            contents = str(contents) if contents is not None else ""
        return cls(contents=contents)  # type: ignore

    def _get_all_hooks_internal(self) -> dict[str, None]:
        """Include the hooks for the component.

        Returns:
            The hooks for the component.
        """
        hooks = super()._get_all_hooks_internal()
        if isinstance(self.contents, LiteralComponentVar):
            hooks |= self.contents._var_value._get_all_hooks_internal()
        return hooks

    def _get_all_hooks(self) -> dict[str, None]:
        """Include the hooks for the component.

        Returns:
            The hooks for the component.
        """
        hooks = super()._get_all_hooks()
        if isinstance(self.contents, LiteralComponentVar):
            hooks |= self.contents._var_value._get_all_hooks()
        return hooks

    def _get_all_imports(self) -> ParsedImportDict:
        """Include the imports for the component.

        Returns:
            The imports for the component.
        """
        imports = super()._get_all_imports()
        if isinstance(self.contents, LiteralComponentVar):
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
        if isinstance(self.contents, LiteralComponentVar):
            dynamic_imports |= self.contents._var_value._get_all_dynamic_imports()
        return dynamic_imports

    def _get_all_custom_code(self) -> set[str]:
        """Get custom code for the component.

        Returns:
            The custom code.
        """
        custom_code = super()._get_all_custom_code()
        if isinstance(self.contents, LiteralComponentVar):
            custom_code |= self.contents._var_value._get_all_custom_code()
        return custom_code

    def _get_all_refs(self) -> set[str]:
        """Get the refs for the children of the component.

        Returns:
            The refs for the children.
        """
        refs = super()._get_all_refs()
        if isinstance(self.contents, LiteralComponentVar):
            refs |= self.contents._var_value._get_all_refs()
        return refs

    def _render(self) -> Tag:
        if isinstance(self.contents, Var):
            if isinstance(self.contents, (BooleanVar, ObjectVar)):
                return Tagless(contents=f"{{{str(self.contents.to_string())}}}")
            return Tagless(contents=f"{{{str(self.contents)}}}")
        return Tagless(contents=str(self.contents))

    def _get_vars(self, include_children: bool = False) -> Iterator[Var]:
        """Walk all Vars used in this component.

        Args:
            include_children: Whether to include Vars from children.

        Yields:
            The contents if it is a Var, otherwise nothing.
        """
        yield self.contents
