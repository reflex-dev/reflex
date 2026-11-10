"""Create a list of components from an iterable."""

from __future__ import annotations

import functools
import inspect
import re
from collections.abc import Callable, Iterable
from hashlib import md5
from typing import Any, cast

from reflex_base.compiler.templates import _RenderUtils
from reflex_base.components.component import ENCLOSING_SCOPE_VARS, Component, field
from reflex_base.components.tags import IterTag
from reflex_base.constants import MemoizationMode
from reflex_base.constants.state import FIELD_MARKER
from reflex_base.utils import types
from reflex_base.utils.exceptions import UntypedVarError
from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var, var_operation, var_operation_return

from reflex_components_core.base.fragment import Fragment
from reflex_components_core.core.cond import cond


@var_operation
def _string_chars_operation(string: Var[Any]):
    """Convert a string to an array of Unicode code points.

    Args:
        string: The string to convert.

    Returns:
        A Var representing the string's Unicode code points.
    """
    return var_operation_return(
        js_expression=f'Array.from(({string!s}) ?? "")',
        var_type=list[str],
    )


def _has_instance_hooks(component: Component) -> bool:
    """Check whether a subtree has hooks that belong to one component instance.

    Lifecycle events and hooks that a component adds run once per rendered
    instance, so inside a loop they must run once per item.

    Args:
        component: The root of the subtree.

    Returns:
        Whether the component or a descendant outside a scoped loop has such hooks.
    """
    if (
        component._get_mount_lifecycle_hook()
        or component._get_hooks() is not None
        or component._get_added_hooks()
    ):
        return True
    if isinstance(component, Foreach) and component._item_scoped:
        return False
    return any(
        isinstance(child, Component) and _has_instance_hooks(child)
        for child in (*component.children, *component._get_components_in_props())
    )


class ForeachVarError(TypeError):
    """Raised when the iterable type is Any."""


class ForeachRenderError(TypeError):
    """Raised when there is an error with the foreach render function."""


class Foreach(Component):
    """A component that takes in an iterable and a render function and renders a list of components."""

    _memoization_mode = MemoizationMode(recursive=False)

    iterable: Var[Iterable] = field(doc="The iterable to create components from.")

    render_fn: Callable = field(
        doc="A function from the render args to the component.",
        default=Fragment.create,
        is_javascript_property=False,
    )

    _item_scoped: bool = field(
        doc="Whether each item renders as its own component, so its hooks run once per item.",
        default=False,
        is_javascript_property=False,
    )

    _scope_vars: tuple[str, ...] = field(
        doc="The variables in scope for an item: those the enclosing generated function binds, then the loop variables.",
        default=(),
        is_javascript_property=False,
    )

    @classmethod
    def create(
        cls,
        iterable: Var[Iterable] | Iterable,
        render_fn: Callable,
    ) -> Foreach:
        """Create a foreach component.

        Args:
            iterable: The iterable to create components from.
            render_fn: A function from the render args to the component.

        Returns:
            The foreach component.

        Raises:
            ForeachVarError: If the iterable is of type Any.
            TypeError: If the render function is a ComponentState.
            UntypedVarError: If the iterable is of type Any without a type annotation.

        # noqa: DAR401 with_traceback
        # noqa: DAR402 UntypedVarError
        """
        from reflex_base.vars import ArrayVar, ObjectVar, SetVar, StringVar

        from reflex.state import ComponentState

        iterable = (
            LiteralVar.create(iterable).guess_type()
            if not isinstance(iterable, Var)
            else iterable.guess_type()
        )

        if iterable._var_type == Any:
            msg = (
                f"Could not foreach over var `{iterable!s}` of type Any. "
                "(If you are trying to foreach over a state var, add a type annotation to the var). "
                "See https://reflex.dev/docs/library/dynamic-rendering/foreach/"
            )
            raise ForeachVarError(msg)

        if (
            hasattr(render_fn, "__qualname__")
            and render_fn.__qualname__ == ComponentState.create.__qualname__
        ):
            msg = "Using a ComponentState as `render_fn` inside `rx.foreach` is not supported yet."
            raise TypeError(msg)

        if isinstance(iterable, ObjectVar):
            iterable = iterable.entries()

        if isinstance(iterable, StringVar):
            iterable = _string_chars_operation(iterable)

        if isinstance(iterable, SetVar):
            iterable = iterable.to_array()

        if not isinstance(iterable, ArrayVar):
            msg = (
                f"Could not foreach over var `{iterable!s}` of type {iterable._var_type}. "
                "See https://reflex.dev/docs/library/dynamic-rendering/foreach/"
            )
            raise ForeachVarError(msg)

        if types.is_optional(iterable._var_type):
            iterable = cond(iterable, iterable, [])

        component = cls._create(
            children=[],
            iterable=iterable,
            render_fn=render_fn,
        )
        tag = component._render()
        loop_vars = (tag.arg_var_name, tag.index_var_name)
        component._scope_vars = tuple(
            dict.fromkeys((*ENCLOSING_SCOPE_VARS.get(), *loop_vars))
        )
        enclosing = ENCLOSING_SCOPE_VARS.set(component._scope_vars)
        try:
            # Keep a ref to a rendered component to determine correct imports/hooks/styles.
            item = tag.render_component()
        except UntypedVarError as e:
            raise UntypedVarError(
                iterable,
                "foreach",
                "https://reflex.dev/docs/library/dynamic-rendering/foreach/",
            ).with_traceback(e.__traceback__) from None
        finally:
            ENCLOSING_SCOPE_VARS.reset(enclosing)
        component.children = [item]
        reads_loop_var = re.compile(
            rf"(?<![\w$])(?:{'|'.join(map(re.escape, loop_vars))})(?![\w$])"
        )
        component._item_scoped = _has_instance_hooks(item) or any(
            reads_loop_var.search(hook) for hook in item._get_all_hooks()
        )
        return component

    def _item_component(self) -> tuple[str, str]:
        """Compile the item into a module-level component.

        The item's hooks run in that component, once per item, and the
        variables in scope reach it as props.

        Returns:
            The component name and its definition.
        """
        item = self.children[0]
        params = ",".join(self._scope_vars)
        hooks = "\n".join(item._get_all_hooks())
        body = _RenderUtils.render(item.render())
        name = f"ForeachItem_{md5(f'{params}{hooks}{body}'.encode()).hexdigest()}"
        return (
            name,
            f"const {name} = (({{{params}}}) => {{\n{hooks}\nreturn ({body})\n}});",
        )

    def _item_key(self) -> Var:
        """Get the key of the rendered item.

        Returns:
            The key, which the loop body evaluates outside the item component.
        """
        return LiteralVar.create(cast("Component", self.children[0]).key)

    def _item_key_hooks(self) -> dict[str, VarData | None]:
        """Get the hooks that the item key needs where the loop body evaluates it.

        Returns:
            The hooks of the key.
        """
        var_data = self._item_key()._get_all_var_data()
        return dict.fromkeys(var_data.hooks) if var_data is not None else {}

    def _get_all_hooks_internal(self) -> dict[str, VarData | None]:
        """Get the internal hooks that compile outside the loop body.

        Returns:
            The component's own hooks when each item is its own component,
            otherwise the hooks of the whole subtree.
        """
        if self._item_scoped:
            return {**self._get_hooks_internal(), **self._item_key_hooks()}
        return super()._get_all_hooks_internal()

    def _get_all_hooks(self) -> dict[str, VarData | None]:
        """Get the hooks that compile outside the loop body.

        Returns:
            The component's own hooks when each item is its own component,
            otherwise the hooks of the whole subtree.
        """
        if not self._item_scoped:
            return super()._get_all_hooks()
        code = {**self._get_hooks_internal(), **self._item_key_hooks()}
        if (hooks := self._get_hooks()) is not None:
            code[hooks] = None
        code.update(self._get_added_hooks())
        return code

    def add_custom_code(self) -> list[str]:
        """Add the item component definition when each item is its own component.

        Returns:
            The module-level code for the component.
        """
        return [self._item_component()[1]] if self._item_scoped else []

    def _render(self) -> IterTag:
        props = {}

        render_sig = inspect.signature(self.render_fn)
        params = list(render_sig.parameters.values())

        # Validate the render function signature.
        if len(params) == 0 or len(params) > 2:
            msg = (
                "Expected 1 or 2 parameters in foreach render function, got "
                f"{[p.name for p in params]}. See "
                "https://reflex.dev/docs/library/dynamic-rendering/foreach/"
            )
            raise ForeachRenderError(msg)

        if len(params) >= 1:
            # Determine the arg var name based on the params accepted by render_fn.
            props["arg_var_name"] = params[0].name + FIELD_MARKER

        if len(params) == 2:
            # Determine the index var name based on the params accepted by render_fn.
            props["index_var_name"] = params[1].name + FIELD_MARKER
        else:
            render_fn = self.render_fn
            # Otherwise, use a deterministic index, based on the render function bytecode.
            if (render_fn_code := getattr(render_fn, "__code__", None)) is not None:
                code_hash = md5(render_fn_code.co_code).hexdigest()
            elif isinstance(render_fn, functools.partial):
                code_hash = md5(render_fn.func.__code__.co_code).hexdigest()
            else:
                code_hash = md5(repr(render_fn).encode()).hexdigest()
            props["index_var_name"] = f"index_{code_hash}"

        return IterTag(
            iterable=self.iterable,
            render_fn=self.render_fn,
            children=self.children,
            **props,
        )

    def render(self):
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        tag = self._render()

        rendered = dict(
            tag,
            iterable_state=str(tag.iterable),
            arg_name=tag.arg_var_name,
            arg_index=tag.index_var_name,
        )
        if self._item_scoped:
            name, _ = self._item_component()
            rendered["item_call"] = (
                f"jsx({name},{{key:{self._item_key()!s},{','.join(self._scope_vars)}}},)"
            )
        return rendered


foreach = Foreach.create
