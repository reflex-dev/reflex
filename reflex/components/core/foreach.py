"""Create a list of components from an iterable."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Iterable
from typing import Any

from reflex.components.base.fragment import Fragment
from reflex.components.component import Component, field
from reflex.components.core.cond import cond
from reflex.components.tags import IterTag
from reflex.constants import MemoizationMode
from reflex.constants.state import FIELD_MARKER
from reflex.state import ComponentState
from reflex.utils import types
from reflex.utils.exceptions import UntypedVarError
from reflex.vars.base import LiteralVar, Var


class ForeachVarError(TypeError):
    """Raised when the iterable type is Any."""


class ForeachRenderError(TypeError):
    """Raised when there is an error with the foreach render function."""


class Foreach(Component):
    """A component that takes in an iterable and a render function and renders a list of components."""

    _memoization_mode = MemoizationMode(recursive=False)

    # The iterable to create components from.
    iterable: Var[Iterable]

    # A function from the render args to the component.
    render_fn: Callable = field(default=Fragment.create, is_javascript_property=False)

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
        from reflex.vars import ArrayVar, ObjectVar, StringVar

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
            iterable = iterable.split()

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
        try:
            # Keep a ref to a rendered component to determine correct imports/hooks/styles.
            component.children = [component._render().render_component()]
        except UntypedVarError as e:
            raise UntypedVarError(
                iterable,
                "foreach",
                "https://reflex.dev/docs/library/dynamic-rendering/foreach/",
            ).with_traceback(e.__traceback__) from None
        return component

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
            code_hash = (
                hash(
                    getattr(
                        render_fn,
                        "__code__",
                        (
                            repr(self.render_fn)
                            if not isinstance(render_fn, functools.partial)
                            else render_fn.func.__code__
                        ),
                    )
                )
                .to_bytes(
                    length=8,
                    byteorder="big",
                    signed=True,
                )
                .hex()
            )
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

        return dict(
            tag,
            iterable_state=str(tag.iterable),
            arg_name=tag.arg_var_name,
            arg_index=tag.get_index_var_arg(),
        )


foreach = Foreach.create
