"""Built-in compiler plugins and the default plugin pipeline."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence
from typing import Any

from reflex_base.components.component import BaseComponent, Component, ComponentStyle
from reflex_base.config import get_config
from reflex_base.plugins import CompileContext, PageContext, PageDefinition, Plugin
from reflex_base.plugins.base import HookOrder
from reflex_base.utils.format import make_default_page_title
from reflex_base.utils.imports import collapse_imports, merge_imports
from reflex_base.vars import VarData
from reflex_components_core.base.fragment import Fragment

from reflex.compiler import utils


@dataclasses.dataclass(frozen=True, slots=True)
class DefaultPagePlugin(Plugin):
    """Evaluate an unevaluated page into a mutable page context."""

    def eval_page(
        self,
        page_fn: Any,
        /,
        *,
        page: PageDefinition,
        **kwargs: Any,
    ) -> PageContext:
        """Evaluate the page function and attach legacy page metadata.

        Returns:
            The evaluated page context.
        """
        from reflex.compiler import compiler

        try:
            component = compiler.into_component(page_fn)
            component = Fragment.create(component)

            title = getattr(page, "title", None)
            meta_args = {
                "title": (
                    title
                    if title is not None
                    else make_default_page_title(get_config().app_name, page.route)
                ),
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
class ApplyStylePlugin(Plugin):
    """Apply app-level styles in the descending phase of the walk."""

    style: ComponentStyle | None = None

    @staticmethod
    def _apply_style(
        comp: Component, style: ComponentStyle, page_context: PageContext
    ) -> Component | None:
        """Apply app-level styles to a single component.

        Args:
            comp: The component to style.
            style: The app-level component style map.
            page_context: The active page context, used to obtain a page-local
                clone before rewriting ``style``.

        Returns:
            A page-local clone with the merged style, or ``None`` when the
            component has no type-level or app-level style to apply.
        """
        if type(comp)._add_style != Component._add_style:
            msg = "Do not override _add_style directly. Use add_style instead."
            raise UserWarning(msg)

        new_style = comp._add_style()
        component_style = comp._get_component_style(style)
        if not new_style and not component_style:
            return None

        style_vars = [new_style._var_data]
        if component_style:
            new_style.update(component_style)
            style_vars.append(component_style._var_data)
        new_style.update(comp.style)
        style_vars.append(comp.style._var_data)
        new_style._var_data = VarData.merge(*style_vars)

        owned = page_context.own(comp)
        owned.style = new_style
        return owned

    def enter_component(
        self,
        comp: BaseComponent,
        /,
        *,
        page_context: PageContext,
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> BaseComponent | None:
        """Apply the non-recursive portion of ``_add_style_recursive``.

        Returns:
            A page-local clone carrying the merged style, or ``None`` when no
            style change applies to this component.
        """
        if self.style is not None and isinstance(comp, Component) and not in_prop_tree:
            return self._apply_style(comp, self.style, page_context)
        return None

    def _compiler_bind_enter_component(
        self,
        page_context: PageContext,
        compile_context: CompileContext,
    ) -> Callable[[BaseComponent, bool], BaseComponent | None]:
        """Bind a positional fast-path enter hook for style application.

        Returns:
            A compiled enter hook that only takes hot-loop positional state.
        """
        style = self.style
        if style is None:

            def enter_component(
                comp: BaseComponent,
                in_prop_tree: bool,
            ) -> BaseComponent | None:
                return None

            return enter_component

        apply_style = self._apply_style

        def enter_component(
            comp: BaseComponent,
            in_prop_tree: bool,
        ) -> BaseComponent | None:
            if not isinstance(comp, Component) or in_prop_tree:
                return None
            return apply_style(comp, style, page_context)

        return enter_component


@dataclasses.dataclass(frozen=True, slots=True)
class DefaultCollectorPlugin(Plugin):
    """Collect page artifacts in one fused enter/leave hook pair."""

    # Run after replacing leave hooks so collected imports/custom-code reflect
    # the final post-replacement component (e.g. memoize wrappers).
    _compiler_leave_component_order = HookOrder.POST
    _compiler_can_replace_leave_component = False

    def leave_component(
        self,
        comp: BaseComponent,
        children: tuple[BaseComponent, ...],
        /,
        *,
        page_context: PageContext,
        compile_context: Any,
        in_prop_tree: bool = False,
    ) -> None:
        """Collect imports and page artifacts for the active component node."""
        if not isinstance(comp, Component):
            return

        imports = comp._get_imports()
        if imports:
            self._extend_imports(page_context.frontend_imports, imports)

        self._collect_component_custom_code(page_context.module_code, comp)

        if not in_prop_tree:
            self._collect_component_hooks(page_context.hooks, comp)

            if (
                type(comp)._get_app_wrap_components
                is not Component._get_app_wrap_components
            ):
                self._collect_app_wrap_components(
                    page_context.app_wrap_components,
                    comp,
                )

        if (dynamic_import := comp._get_dynamic_imports()) is not None:
            page_context.dynamic_imports.add(dynamic_import)

        if (ref := comp.get_ref()) is not None:
            page_context.refs[ref] = None

    def compile_page(
        self,
        page_ctx: PageContext,
        /,
        **kwargs: Any,
    ) -> None:
        """Collapse collected imports into a single legacy-shaped entry."""
        if page_ctx.frontend_imports:
            collapsed_imports = collapse_imports(
                merge_imports(page_ctx.frontend_imports, *page_ctx.imports)
                if page_ctx.imports
                else page_ctx.frontend_imports
            )
            page_ctx.frontend_imports = collapsed_imports
            page_ctx.imports = [collapsed_imports]
            return

        page_ctx.imports = (
            [collapse_imports(merge_imports(*page_ctx.imports))]
            if page_ctx.imports
            else []
        )

    def _compiler_bind_leave_component(
        self,
        page_context: PageContext,
        compile_context: CompileContext,
    ) -> Callable[[BaseComponent, tuple[BaseComponent, ...], bool], None]:
        """Bind a positional fast-path leave hook for artifact collection.

        Returns:
            A compiled leave hook that only takes hot-loop positional state.
        """
        frontend_imports = page_context.frontend_imports
        module_code = page_context.module_code
        hooks = page_context.hooks
        dynamic_imports = page_context.dynamic_imports
        refs = page_context.refs
        app_wrap_components = page_context.app_wrap_components
        extend_imports = self._extend_imports
        collect_component_hooks = self._collect_component_hooks
        collect_component_custom_code = self._collect_component_custom_code
        collect_app_wrap_components = self._collect_app_wrap_components
        base_get_app_wrap_components = Component._get_app_wrap_components
        seen_app_wrap_methods: set[object] = set()

        def leave_component(
            comp: BaseComponent,
            children: tuple[BaseComponent, ...],
            in_prop_tree: bool,
        ) -> None:
            if not isinstance(comp, Component):
                return

            imports_for_component = comp._get_imports()
            if imports_for_component:
                extend_imports(frontend_imports, imports_for_component)

            collect_component_custom_code(module_code, comp)

            if not in_prop_tree:
                collect_component_hooks(hooks, comp)

                app_wrap_method = type(comp)._get_app_wrap_components
                if (
                    app_wrap_method is not base_get_app_wrap_components
                    and app_wrap_method not in seen_app_wrap_methods
                ):
                    seen_app_wrap_methods.add(app_wrap_method)
                    collect_app_wrap_components(app_wrap_components, comp)

            dynamic_import = comp._get_dynamic_imports()
            if dynamic_import is not None:
                dynamic_imports.add(dynamic_import)

            ref = comp.get_ref()
            if ref is not None:
                refs[ref] = None

        return leave_component

    @staticmethod
    def _collect_component_hooks(
        page_hooks: dict[str, VarData | None],
        component: Component,
    ) -> None:
        """Collect hooks for one structural-tree component in legacy order."""
        page_hooks.update(component._get_hooks_internal())
        if (user_hooks := component._get_hooks()) is not None:
            page_hooks[user_hooks] = None
        page_hooks.update(component._get_added_hooks())

    @staticmethod
    def _extend_imports(
        target: dict[str, list[Any]],
        source: dict[str, list[Any]],
    ) -> None:
        """Extend a parsed import mapping in place."""
        for lib, fields in source.items():
            target.setdefault(lib, []).extend(fields)

    @staticmethod
    def _collect_component_custom_code(
        module_code: dict[str, None],
        component: Component,
    ) -> None:
        """Collect custom code contributed directly by one component.

        The compiler walker visits every structural child and every component
        in prop subtrees, firing ``leave_component`` on each — so this helper
        only handles the current node and does not recurse.
        """
        if (custom_code := component._get_custom_code()) is not None:
            module_code[custom_code] = None

        for clz in component._iter_parent_classes_with_method("add_custom_code"):
            for item in clz.add_custom_code(component):
                module_code[item] = None

    def _collect_app_wrap_components(
        self,
        page_app_wrap_components: dict[tuple[int, str], Component],
        component: Component,
    ) -> None:
        """Collect app-wrap components for a structural-tree component."""
        direct_wrappers = component._get_app_wrap_components()
        if not direct_wrappers:
            return

        ignore_ids = {id(wrapper) for wrapper in page_app_wrap_components.values()}
        page_app_wrap_components.update(direct_wrappers)
        for wrapper in direct_wrappers.values():
            wrapper_id = id(wrapper)
            if wrapper_id in ignore_ids:
                continue
            ignore_ids.add(wrapper_id)
            self._collect_wrapper_subtree_into(
                wrapper,
                ignore_ids,
                page_app_wrap_components,
            )

    @staticmethod
    def _collect_wrapper_subtree_into(
        component: Component,
        ignore_ids: set[int],
        components: dict[tuple[int, str], Component],
    ) -> None:
        """Collect nested app-wrap components into ``components``."""
        direct_wrappers = component._get_app_wrap_components()
        for key, wrapper in direct_wrappers.items():
            wrapper_id = id(wrapper)
            if wrapper_id in ignore_ids:
                continue
            ignore_ids.add(wrapper_id)
            components[key] = wrapper
            DefaultCollectorPlugin._collect_wrapper_subtree_into(
                wrapper,
                ignore_ids,
                components,
            )

        for child in component.children:
            if not isinstance(child, Component):
                continue
            child_id = id(child)
            if child_id in ignore_ids:
                continue
            ignore_ids.add(child_id)
            DefaultCollectorPlugin._collect_wrapper_subtree_into(
                child,
                ignore_ids,
                components,
            )


def default_page_plugins(
    *,
    style: ComponentStyle | None = None,
    plugins: Sequence[Plugin] = (),
) -> tuple[Plugin, ...]:
    """Return the default compiler plugin ordering for page compilation."""
    from reflex.compiler.plugins.memoize import MemoizeStatefulPlugin

    chain: list[Plugin] = [*plugins, DefaultPagePlugin()]
    if style is not None:
        chain.append(ApplyStylePlugin(style=style))
    chain.extend((DefaultCollectorPlugin(), MemoizeStatefulPlugin()))
    return tuple(chain)


__all__ = [
    "ApplyStylePlugin",
    "DefaultCollectorPlugin",
    "DefaultPagePlugin",
    "default_page_plugins",
]
