"""Create a list of components from an iterable."""
from __future__ import annotations

from typing import Any, Callable, Iterable

from reflex.components.component import Component
from reflex.components.layout.fragment import Fragment
from reflex.components.tags import IterTag
from reflex.vars import BaseVar, Var, get_unique_variable_name


class Foreach(Component):
    """A component that takes in an iterable and a render function and renders a list of components."""

    # The iterable to create components from.
    iterable: Var[Iterable]

    # A function from the render args to the component.
    render_fn: Callable = Fragment.create

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
        try:
            type_ = (
                iterable.type_
                if iterable.type_.mro()[0] == dict
                else iterable.type_.__args__[0]
            )
        except Exception:
            type_ = Any
        iterable = Var.create(iterable)  # type: ignore
        if iterable.type_ == Any:
            raise TypeError(
                f"Could not foreach over var of type Any. (If you are trying to foreach over a state var, add a type annotation to the var.)"
            )
        arg = BaseVar(name="_", type_=type_, is_local=True)
        return cls(
            iterable=iterable,
            render_fn=render_fn,
            children=[IterTag.render_component(render_fn, arg=arg)],
            **props,
        )

    def _render(self) -> IterTag:
        return IterTag(iterable=self.iterable, render_fn=self.render_fn)

    def render(self):
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        tag = self._render()
        try:
            type_ = (
                self.iterable.type_
                if self.iterable.type_.mro()[0] == dict
                else self.iterable.type_.__args__[0]
            )
        except Exception:
            type_ = Any
        arg = BaseVar(
            name=get_unique_variable_name(),
            type_=type_,
        )
        index_arg = tag.get_index_var_arg()
        component = tag.render_component(self.render_fn, arg)
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
            iterable_state=tag.iterable.full_name,
            arg_name=arg.name,
            arg_index=index_arg,
            iterable_type=tag.iterable.type_.mro()[0].__name__,
        )
