"""Built-in compiler plugins and the default plugin pipeline."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence
from typing import Any

from reflex_base.components.component import BaseComponent, Component, ComponentStyle
from reflex_base.components.state_context import get_events_hooks_var_data
from reflex_base.config import get_config
from reflex_base.constants.compiler import Hooks
from reflex_base.plugins import CompileContext, PageContext, PageDefinition, Plugin
from reflex_base.plugins.base import HookOrder
from reflex_base.utils.format import make_default_page_title
from reflex_base.utils.imports import collapse_imports, merge_imports
from reflex_base.vars import VarData
from reflex_base.vars.base import insert_app_wraps
from reflex_components_core.base.fragment import Fragment

from reflex.compiler import utils


def collect_var_app_wraps_in_subtree(
    page_app_wrap_components: dict[tuple[int, str], Component],
    root: Component,
) -> None:
    """Walk ``root`` and its descendants, surfacing Var-declared app_wraps.

    Each visited component contributes via :func:`collect_var_app_wraps_for_component`.
    Used wherever the page walker doesn't reach — e.g. snapshot-boundary
    descendants sealed by ``MemoizeStatefulPlugin``, or the app-wrap chain
    components assembled by ``App._app_root`` (their own subtrees, e.g.
    ``ErrorBoundary``'s fallback render, are not pages).
    """
    visited: set[int] = set()
    stack: list[Component] = [root]
    while stack:
        node = stack.pop()
        node_id = id(node)
        if node_id in visited:
            continue
        visited.add(node_id)
        page_app_wrap_components.update(
            collect_var_app_wraps_for_component(page_app_wrap_components, node)
        )
        stack.extend(child for child in node.children if isinstance(child, Component))
        stack.extend(
            component
            for component in node._get_components_in_props()
            if isinstance(component, Component)
        )


def _ingest_component_var_app_wraps(
    wraps_by_key: dict[tuple[int, str], Component],
    existing: dict[tuple[int, str], Component],
    component: Component,
    hooks_internal: dict[str, VarData | None],
    added_hooks: dict[str, VarData | None],
) -> None:
    """Ingest app_wraps from a component's Vars, pre-fetched hooks, and events.

    Scans the component's Vars (props/style/event-trigger args), the VarData on
    its framework-managed internal hooks and ``add_hooks`` output (e.g.
    ``Hooks.EVENTS``), and the state/event-loop providers it requires via
    :meth:`Component._get_event_app_wraps`.

    ``hooks_internal`` and ``added_hooks`` are supplied by the caller rather than
    re-fetched here so the page collector — which already pulls them to populate
    ``page_hooks`` — doesn't pay for a second ``_get_hooks_internal`` /
    ``_get_added_hooks`` (and the latter is uncached). New entries are written
    into ``wraps_by_key``; entries already in ``existing`` are skipped.
    """
    for var in component._get_vars():
        var_data = var._get_all_var_data()
        if var_data is None:
            continue
        _ingest_var_data_app_wraps(wraps_by_key, existing, var_data)
    for hook_var_data in hooks_internal.values():
        if hook_var_data is None:
            continue
        _ingest_var_data_app_wraps(wraps_by_key, existing, hook_var_data)
    for hook, hook_var_data in added_hooks.items():
        if hook_var_data is None and hook == Hooks.EVENTS:
            hook_var_data = get_events_hooks_var_data()
        if hook_var_data is None:
            continue
        _ingest_var_data_app_wraps(wraps_by_key, existing, hook_var_data)
    insert_app_wraps(
        wraps_by_key,
        (
            (priority, wrapper)
            for (priority, _tag), wrapper in component._get_event_app_wraps().items()
        ),
        existing=existing,
    )


def collect_var_app_wraps_for_component(
    page_app_wrap_components: dict[tuple[int, str], Component],
    component: Component,
) -> dict[tuple[int, str], Component]:
    """Return Var-declared app_wraps newly contributed by ``component``.

    Convenience wrapper over :func:`_ingest_component_var_app_wraps` for callers
    (snapshot-boundary and app-root walks) that don't already have the
    component's hooks in hand. The page collector fetches the hooks once and
    calls the underlying helper directly instead.

    Entries already in ``page_app_wrap_components`` are skipped, leaving the
    caller to decide how to merge the result and whether to recurse into
    each wrapper's own subtree.

    Returns:
        Mapping of ``(priority, name)`` -> wrapper for new entries only.
    """
    wraps_by_key: dict[tuple[int, str], Component] = {}
    _ingest_component_var_app_wraps(
        wraps_by_key,
        page_app_wrap_components,
        component,
        component._get_hooks_internal(),
        component._get_added_hooks(),
    )
    return wraps_by_key


def _ingest_var_data_app_wraps(
    wraps_by_key: dict[tuple[int, str], Component],
    existing: dict[tuple[int, str], Component],
    var_data: VarData,
) -> None:
    """Insert app_wraps carried or implied by ``var_data``."""
    if var_data.app_wraps:
        _ingest_app_wraps(wraps_by_key, existing, var_data.app_wraps)
    if Hooks.EVENTS in var_data.hooks:
        _ingest_app_wraps(
            wraps_by_key,
            existing,
            get_events_hooks_var_data().app_wraps,
        )


def _ingest_app_wraps(
    wraps_by_key: dict[tuple[int, str], Component],
    existing: dict[tuple[int, str], Component],
    app_wraps: tuple[tuple[int, BaseComponent], ...],
) -> None:
    """Insert app_wraps not already present in ``existing`` or ``wraps_by_key``."""
    insert_app_wraps(
        wraps_by_key,
        (
            (priority, wrapper)
            for priority, wrapper in app_wraps
            if isinstance(wrapper, Component)
        ),
        existing=existing,
    )


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

            component = utils.add_meta(component, **meta_args)
        except Exception as err:
            if hasattr(err, "add_note"):
                err.add_note(f"Happened while evaluating page {page.route!r}")
            raise

        return PageContext(
            name=getattr(page_fn, "__name__", page.route),
            route=page.route,
            root_component=component,
            source_module=getattr(page, "_source_module", None),
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

        # Fetch once and reuse for both page-hook aggregation and the app-wrap
        # scan; ``_get_added_hooks`` is uncached, so a second call recomputes.
        hooks_internal = comp._get_hooks_internal()
        added_hooks = comp._get_added_hooks()

        if not in_prop_tree:
            self._apply_component_hooks(
                page_context.hooks, comp, hooks_internal, added_hooks
            )

            if (
                type(comp)._get_app_wrap_components
                is not Component._get_app_wrap_components
            ):
                self._collect_app_wrap_components(
                    page_context.app_wrap_components,
                    comp,
                )

        self._collect_var_app_wraps(
            page_context.app_wrap_components, comp, hooks_internal, added_hooks
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
        apply_component_hooks = self._apply_component_hooks
        collect_component_custom_code = self._collect_component_custom_code
        collect_app_wrap_components = self._collect_app_wrap_components
        collect_var_app_wraps = self._collect_var_app_wraps
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

            # Fetch once and reuse for both page-hook aggregation and the
            # app-wrap scan; ``_get_added_hooks`` is uncached.
            hooks_internal = comp._get_hooks_internal()
            added_hooks = comp._get_added_hooks()

            if not in_prop_tree:
                apply_component_hooks(hooks, comp, hooks_internal, added_hooks)

                app_wrap_method = type(comp)._get_app_wrap_components
                if (
                    app_wrap_method is not base_get_app_wrap_components
                    and app_wrap_method not in seen_app_wrap_methods
                ):
                    seen_app_wrap_methods.add(app_wrap_method)
                    collect_app_wrap_components(app_wrap_components, comp)

            collect_var_app_wraps(
                app_wrap_components, comp, hooks_internal, added_hooks
            )

            dynamic_import = comp._get_dynamic_imports()
            if dynamic_import is not None:
                dynamic_imports.add(dynamic_import)

            ref = comp.get_ref()
            if ref is not None:
                refs[ref] = None

        return leave_component

    @staticmethod
    def _apply_component_hooks(
        page_hooks: dict[str, VarData | None],
        component: Component,
        hooks_internal: dict[str, VarData | None],
        added_hooks: dict[str, VarData | None],
    ) -> None:
        """Add one structural-tree component's hooks in legacy order.

        ``hooks_internal`` and ``added_hooks`` are passed in (rather than
        re-fetched) so the same dicts feed both this aggregation and the
        app-wrap scan.
        """
        page_hooks.update(hooks_internal)
        if (user_hooks := component._get_hooks()) is not None:
            page_hooks[user_hooks] = None
        page_hooks.update(added_hooks)

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
        """Collect subclass-declared app-wrap components for a component.

        Var-driven providers (including event-trigger ones) are collected by
        :meth:`_collect_var_app_wraps`, which visits every component.
        """
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

    def _collect_var_app_wraps(
        self,
        page_app_wrap_components: dict[tuple[int, str], Component],
        component: Component,
        hooks_internal: dict[str, VarData | None],
        added_hooks: dict[str, VarData | None],
    ) -> None:
        """Collect app-wrap components declared by VarData on ``component``.

        ``hooks_internal`` and ``added_hooks`` are the dicts already fetched for
        page-hook aggregation, reused here to avoid a second uncached
        ``_get_added_hooks`` per component.
        """
        wraps_by_key: dict[tuple[int, str], Component] = {}
        _ingest_component_var_app_wraps(
            wraps_by_key,
            page_app_wrap_components,
            component,
            hooks_internal,
            added_hooks,
        )
        if not wraps_by_key:
            return

        ignore_ids = {id(wrapper) for wrapper in page_app_wrap_components.values()}
        page_app_wrap_components.update(wraps_by_key)
        for wrapper in wraps_by_key.values():
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
