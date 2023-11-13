"""Wrapper around react-debounce-input."""
from __future__ import annotations

from typing import Any, Iterator, Set, Type

from reflex.components.component import Component
from reflex.utils import imports
from reflex.vars import Var


def _empty_iterator() -> Iterator[Var]:
    """Return an empty iterator.

    Yields:
        No values, ever. Will raise StopIteration immediately.
    """
    yield from []


class DebounceInput(Component):
    """The DebounceInput component is used to buffer input events on the client side.

    It is intended to wrap various form controls and should be used whenever a
    fully-controlled input is needed to prevent lost input data when the backend
    is experiencing high latency.
    """

    library = "react-debounce-input@3.3.0"
    tag = "DebounceInput"

    # Minimum input characters before triggering the on_change event
    min_length: Var[int]

    # Time to wait between end of input and triggering on_change
    debounce_timeout: Var[int]

    # If true, notify when Enter key is pressed
    force_notify_by_enter: Var[bool]

    # If true, notify when form control loses focus
    force_notify_on_blur: Var[bool]

    # If provided, create a fully-controlled input
    value: Var[str]

    # The ref to attach to the created input
    input_ref: Var[str]

    # The element to wrap
    element: Var[Type[Component]]

    @classmethod
    def create(cls, child: Component, **props: Any) -> Component:
        """Create a DebounceInput component.

        Carry first child props directly on this tag.

        Since react-debounce-input wants to create and manage the underlying
        input component itself, we carry all props, events, and styles from
        the child, and then neuter the child's render method so it produces no output.

        Args:
            child: The child component to wrap.
            props: The component props.

        Returns:
            The DebounceInput component.

        Raises:
            RuntimeError: unless exactly one child element is provided.
            ValueError: if the child element does not have an on_change handler.
        """
        child, collected_props = _collect_first_child_and_props(child)
        props.update(collected_props)
        if isinstance(child, cls):
            raise RuntimeError(
                "Provide a single child for DebounceInput, such as rx.input() or "
                "rx.text_area()",
            )
        if "on_change" not in child.event_triggers:
            raise ValueError("DebounceInput child requires an on_change handler")
        # Carry all child props directly via custom_attrs
        props.setdefault("custom_attrs", {}).update(props_not_none(child))
        props.setdefault("style", {}).update(child.style)
        if child.class_name:
            props["class_name"] = f"{props.get('class_name', '')} {child.class_name}"

        child_ref = child.get_ref()
        if not props.get("input_ref") and child_ref:
            props["input_ref"] = Var.create_safe(child_ref, _var_is_local=False)
            props["id"] = child.id
        props.setdefault(
            "element",
            Var.create_safe(
                "{%s}" % (child.alias or child.tag),
                _var_is_local=False,
                _var_is_string=False,
            )._replace(
                _var_type=Type[Component],
            ),
        )

        comp = super().create(child, **props)
        comp.event_triggers.update(child.event_triggers)

        # Do NOT render the child, DebounceInput will create it.
        object.__setattr__(child, "render", lambda: "")
        # Prevent the child from being memoized as a stateful component.
        object.__setattr__(child, "_get_vars", _empty_iterator)
        child.event_triggers = {}

        return comp

    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            *[c._get_imports() for c in self.children if isinstance(c, Component)],
        )

    def _get_hooks_internal(self) -> Set[str]:
        hooks = super()._get_hooks_internal()
        for child in self.children:
            if not isinstance(child, Component):
                continue
            hooks.update(child._get_hooks_internal())
        return hooks

    def get_ref(self) -> str | None:
        """Get the ref for this component.

        The DebounceInput itself cannot have a ref, the ID applies to the child created internally.

        Returns:
            None
        """
        return None


def props_not_none(c: Component) -> dict[str, Any]:
    """Get all properties of the component that are not None.

    Args:
        c: the component to get_props from

    Returns:
        dict of all props that are not None.
    """
    cdict = {a: getattr(c, a) for a in c.get_props() if getattr(c, a, None) is not None}
    return cdict


def _collect_first_child_and_props(c: Component) -> tuple[Component, dict[str, Any]]:
    """Recursively find the first child of a different type than `c` with props.

    This function is used to collapse nested DebounceInput components by
    applying props from each level. Parent props take precedent over child
    props. The first child component that differs in type will be returned
    along with all combined parent props seen along the way.

    Args:
        c: the component to get_props from

    Returns:
        tuple containing the first nested child of a different type and the collected
        props from each component traversed.

    Raises:
        TypeError: if any children are not Component instances.
    """
    props = props_not_none(c)
    if not c.children:
        return c, props
    child = c.children[0]
    if not isinstance(child, Component):
        raise TypeError(f"DebounceInput child must be a Component, got {child!r}")
    if not isinstance(child, DebounceInput):
        return child, props
    # carry props from nested DebounceInput components
    recursive_child, child_props = _collect_first_child_and_props(child)
    return recursive_child, {**child_props, **props}
