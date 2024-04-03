"""Create a list of components from an iterable."""
from __future__ import annotations

import inspect
from hashlib import md5
from typing import Any, Callable, Iterable, Optional

from reflex.components.base.fragment import Fragment
from reflex.components.component import Component
from reflex.components.tags import IterTag
from reflex.constants import MemoizationMode
from reflex.vars import Var


class Foreach(Component):
    """A component that takes in an iterable and a render function and renders a list of components."""

    _memoization_mode = MemoizationMode(recursive=False)

    # The iterable to create components from.
    iterable: Var[Iterable]

    # A function from the render args to the component.
    render_fn: Callable = Fragment.create

    # The theme if set.
    theme: Optional[Component] = None

    def _apply_theme(self, theme: Component):
        """Apply the theme to this component.

        Args:
            theme: The theme to apply.
        """
        self.theme = theme

    @classmethod
    def create(cls, iterable: Var[Iterable], render_fn: Callable, **props) -> Foreach:
        """Create a foreach component.

        Args:
            iterable: The iterable to create components from.
            render_fn: A function from the render args to the component.
            **props: The attributes to pass to each child component.

        Returns:
            The foreach component.

        Raises:
            TypeError: If the iterable is of type Any.
        """
        iterable = Var.create(iterable)  # type: ignore
        if iterable._var_type == Any:
            raise TypeError(
                f"Could not foreach over var of type Any. (If you are trying to foreach over a state var, add a type annotation to the var.)"
            )
        component = cls(
            iterable=iterable,
            render_fn=render_fn,
            **props,
        )
        # Keep a ref to a rendered component to determine correct imports.
        component.children = [
            component._render(props=dict(index_var_name="i")).render_component()
        ]
        return component

    def _render(self, props: dict[str, Any] | None = None) -> IterTag:
        props = {} if props is None else props.copy()

        # Determine the arg var name based on the params accepted by render_fn.
        render_sig = inspect.signature(self.render_fn)
        params = list(render_sig.parameters.values())
        if len(params) >= 1:
            props.setdefault("arg_var_name", params[0].name)

        if len(params) >= 2:
            # Determine the index var name based on the params accepted by render_fn.
            props.setdefault("index_var_name", params[1].name)
        elif "index_var_name" not in props:
            # Otherwise, use a deterministic index, based on the rendered code.
            code_hash = md5(str(self.children[0].render()).encode("utf-8")).hexdigest()
            props.setdefault("index_var_name", f"index_{code_hash}")

        return IterTag(
            iterable=self.iterable,
            render_fn=self.render_fn,
            **props,
        )

    def render(self):
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        tag = self._render()
        component = tag.render_component()

        # Apply the theme to the children.
        if self.theme is not None:
            component.apply_theme(self.theme)

        return dict(
            tag.add_props(
                **self.event_triggers,
                key=self.key,
                sx=self.style,
                id=self.id,
                class_name=self.class_name,
            ).set(
                children=[component.render()],
                props=tag.format_props(),
            ),
            iterable_state=tag.iterable._var_full_name,
            arg_name=tag.arg_var_name,
            arg_index=tag.get_index_var_arg(),
            iterable_type=tag.iterable._var_type.mro()[0].__name__,
        )
