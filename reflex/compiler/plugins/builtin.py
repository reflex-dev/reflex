"""Built-in compiler plugins and the default plugin pipeline."""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncGenerator
from typing import Any

from reflex_components_core.base.fragment import Fragment
from reflex_core.components.component import (
    BaseComponent,
    Component,
    ComponentStyle,
    StatefulComponent,
)
from reflex_core.config import get_config
from reflex_core.utils.format import make_default_page_title
from reflex_core.utils.imports import collapse_imports, merge_imports
from reflex_core.vars import VarData

from reflex.compiler import utils
from reflex.compiler.plugins.base import (
    CompilerPlugin,
    ComponentAndChildren,
    PageContext,
    PageDefinition,
)


@dataclasses.dataclass(frozen=True, slots=True)
class DefaultPagePlugin(CompilerPlugin):
    """Evaluate an unevaluated page into a mutable page context."""

    async def eval_page(
        self,
        page_fn: Any,
        /,
        *,
        page: PageDefinition,
        **kwargs: Any,
    ) -> PageContext:
        """Evaluate the page function and attach legacy page metadata.

        Returns:
            The initialized page context for the evaluated page.
        """
        from reflex.compiler import compiler

        try:
            component = compiler.into_component(page_fn)
            component = Fragment.create(component)

            meta_args = {
                "title": getattr(page, "title", None)
                or make_default_page_title(get_config().app_name, page.route),
                "image": getattr(page, "image", ""),
                "meta": getattr(page, "meta", ()),
            }
            if (description := getattr(page, "description", None)) is not None:
                meta_args["description"] = description

            utils.add_meta(component, **meta_args)
        except Exception as err:
            if hasattr(err, "add_note"):
                err.add_note(f"Happened while evaluating page {page.route!r}")
            raise

        return PageContext(
            name=getattr(page_fn, "__name__", page.route),
            route=page.route,
            root_component=component,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class ApplyStylePlugin(CompilerPlugin):
    """Apply app-level styles in the descending phase of the walk."""

    style: ComponentStyle | None = None
    theme: Component | None = None

    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        *,
        in_prop_tree: bool = False,
        stateful_component: StatefulComponent | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[None, ComponentAndChildren]:
        """Apply the non-recursive portion of ``_add_style_recursive``."""
        del kwargs, stateful_component
        if self.style is not None and isinstance(comp, Component) and not in_prop_tree:
            if type(comp)._add_style != Component._add_style:
                msg = "Do not override _add_style directly. Use add_style instead."
                raise UserWarning(msg)

            new_style = comp._add_style()
            style_vars = [new_style._var_data]

            component_style = comp._get_component_style(self.style)
            if component_style:
                new_style.update(component_style)
                style_vars.append(component_style._var_data)

            new_style.update(comp.style)
            style_vars.append(comp.style._var_data)
            new_style._var_data = VarData.merge(*style_vars)
            comp.style = new_style

        yield


class ConsolidateImportsPlugin(CompilerPlugin):
    """Collect per-component imports and merge them after traversal."""

    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        *,
        in_prop_tree: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[None, ComponentAndChildren]:
        """Collect non-recursive imports for structural components."""
        del kwargs
        if isinstance(comp, StatefulComponent):
            if comp.rendered_as_shared:
                PageContext.get().imports.append(comp._get_all_imports())
            yield
            return

        if not in_prop_tree and isinstance(comp, Component):
            imports = comp._get_imports()
            if imports:
                PageContext.get().imports.append(imports)

        yield

    async def compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        """Collapse collected imports into a single legacy-shaped entry."""
        del kwargs
        page_ctx.imports = (
            [collapse_imports(merge_imports(*page_ctx.imports))]
            if page_ctx.imports
            else []
        )


class ConsolidateHooksPlugin(CompilerPlugin):
    """Collect component hooks while skipping prop and stateful subtrees."""

    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        *,
        in_prop_tree: bool = False,
        stateful_component: StatefulComponent | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[None, ComponentAndChildren]:
        """Collect the single-component hook contributions."""
        del kwargs
        compiled_component, _ = yield
        if (
            in_prop_tree
            or stateful_component is not None
            or isinstance(compiled_component, StatefulComponent)
            or not isinstance(compiled_component, Component)
        ):
            return

        hooks = {}
        hooks.update(compiled_component._get_hooks_internal())
        if (user_hooks := compiled_component._get_hooks()) is not None:
            hooks[user_hooks] = None
        hooks.update(compiled_component._get_added_hooks())
        PageContext.get().hooks.update(hooks)


@dataclasses.dataclass(frozen=True, slots=True)
class ConsolidateCustomCodePlugin(CompilerPlugin):
    """Collect custom module code while preserving legacy ordering."""

    stateful_custom_code_export: bool = False

    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        *,
        in_prop_tree: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[None, ComponentAndChildren]:
        """Collect custom code in legacy order for the active subtree."""
        del kwargs
        page_ctx = PageContext.get()

        if isinstance(comp, StatefulComponent):
            yield
            if not comp.rendered_as_shared:
                page_ctx.module_code[
                    comp._render_stateful_code(export=self.stateful_custom_code_export)
                ] = None
            return

        if in_prop_tree or not isinstance(comp, Component):
            yield
            return

        if (custom_code := comp._get_custom_code()) is not None:
            page_ctx.module_code[custom_code] = None

        for prop_component in comp._get_components_in_props():
            page_ctx.module_code.update(self._collect_prop_custom_code(prop_component))

        for clz in comp._iter_parent_classes_with_method("add_custom_code"):
            for item in clz.add_custom_code(comp):
                page_ctx.module_code[item] = None

        yield

    def _collect_prop_custom_code(
        self,
        component: BaseComponent,
    ) -> dict[str, None]:
        """Recursively collect custom code for a prop-component subtree.

        Returns:
            The collected custom-code snippets keyed in legacy order.
        """
        if isinstance(component, StatefulComponent):
            if component.rendered_as_shared:
                return {}

            code = self._collect_prop_custom_code(component.component)
            code[
                component._render_stateful_code(export=self.stateful_custom_code_export)
            ] = None
            return code

        if not isinstance(component, Component):
            return component._get_all_custom_code()

        code: dict[str, None] = {}
        if (custom_code := component._get_custom_code()) is not None:
            code[custom_code] = None

        for prop_component in component._get_components_in_props():
            code.update(self._collect_prop_custom_code(prop_component))

        for clz in component._iter_parent_classes_with_method("add_custom_code"):
            for item in clz.add_custom_code(component):
                code[item] = None

        for child in component.children:
            code.update(self._collect_prop_custom_code(child))

        return code


class ConsolidateDynamicImportsPlugin(CompilerPlugin):
    """Collect dynamic imports from the active component tree."""

    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        **kwargs: Any,
    ) -> AsyncGenerator[None, ComponentAndChildren]:
        """Collect the current component's dynamic import."""
        del kwargs
        compiled_component, _ = yield
        if isinstance(compiled_component, StatefulComponent) or not isinstance(
            compiled_component, Component
        ):
            return
        if dynamic_import := compiled_component._get_dynamic_imports():
            PageContext.get().dynamic_imports.add(dynamic_import)


class ConsolidateRefsPlugin(CompilerPlugin):
    """Collect refs from the active component tree."""

    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        **kwargs: Any,
    ) -> AsyncGenerator[None, ComponentAndChildren]:
        """Collect the current component ref when present."""
        del kwargs
        compiled_component, _ = yield
        if isinstance(compiled_component, StatefulComponent) or not isinstance(
            compiled_component, Component
        ):
            return
        if (ref := compiled_component.get_ref()) is not None:
            PageContext.get().refs[ref] = None


class ConsolidateAppWrapPlugin(CompilerPlugin):
    """Collect app-wrap components using the page walk plus wrapper recursion."""

    async def compile_component(
        self,
        comp: BaseComponent,
        /,
        *,
        in_prop_tree: bool = False,
        stateful_component: StatefulComponent | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[None, ComponentAndChildren]:
        """Collect direct wrappers and recursively expand wrapper subtrees."""
        del kwargs
        compiled_component, _ = yield
        if (
            in_prop_tree
            or stateful_component is not None
            or not isinstance(compiled_component, Component)
        ):
            return

        page_ctx = PageContext.get()
        direct_wrappers = compiled_component._get_app_wrap_components()
        if not direct_wrappers:
            return

        ignore_ids = {id(wrapper) for wrapper in page_ctx.app_wrap_components.values()}
        page_ctx.app_wrap_components.update(direct_wrappers)
        for wrapper in direct_wrappers.values():
            wrapper_id = id(wrapper)
            if wrapper_id in ignore_ids:
                continue
            ignore_ids.add(wrapper_id)
            page_ctx.app_wrap_components.update(
                self._collect_wrapper_subtree(wrapper, ignore_ids)
            )

    def _collect_wrapper_subtree(
        self,
        component: Component,
        ignore_ids: set[int],
    ) -> dict[tuple[int, str], Component]:
        """Collect app-wrap components reachable through a wrapper subtree.

        Returns:
            The nested wrapper mapping discovered from the wrapper subtree.
        """
        components: dict[tuple[int, str], Component] = {}

        direct_wrappers = component._get_app_wrap_components()
        for key, wrapper in direct_wrappers.items():
            wrapper_id = id(wrapper)
            if wrapper_id in ignore_ids:
                continue
            ignore_ids.add(wrapper_id)
            components[key] = wrapper
            components.update(self._collect_wrapper_subtree(wrapper, ignore_ids))

        for child in component.children:
            if not isinstance(child, Component):
                continue
            child_id = id(child)
            if child_id in ignore_ids:
                continue
            ignore_ids.add(child_id)
            components.update(self._collect_wrapper_subtree(child, ignore_ids))

        return components


def default_page_plugins(
    *,
    style: ComponentStyle | None = None,
    theme: Component | None = None,
    stateful_custom_code_export: bool = False,
) -> tuple[CompilerPlugin, ...]:
    """Return the default compiler plugin ordering for page compilation."""
    return (
        DefaultPagePlugin(),
        ApplyStylePlugin(style=style, theme=theme),
        ConsolidateCustomCodePlugin(
            stateful_custom_code_export=stateful_custom_code_export
        ),
        ConsolidateDynamicImportsPlugin(),
        ConsolidateRefsPlugin(),
        ConsolidateHooksPlugin(),
        ConsolidateAppWrapPlugin(),
        ConsolidateImportsPlugin(),
    )


__all__ = [
    "ApplyStylePlugin",
    "ConsolidateAppWrapPlugin",
    "ConsolidateCustomCodePlugin",
    "ConsolidateDynamicImportsPlugin",
    "ConsolidateHooksPlugin",
    "ConsolidateImportsPlugin",
    "ConsolidateRefsPlugin",
    "DefaultPagePlugin",
    "default_page_plugins",
]
