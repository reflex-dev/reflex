"""Window event listener component for Reflex."""

from __future__ import annotations

from typing import Any, cast

from reflex_base.components.component import StatefulComponent, field
from reflex_base.constants.compiler import Hooks
from reflex_base.event import EventHandler, key_event, no_args_event_spec
from reflex_base.vars.base import Var, VarData
from reflex_base.vars.object import ObjectVar

from reflex_components_core.base.fragment import Fragment


def _on_resize_spec() -> tuple[Var[int], Var[int]]:
    """Args spec for the on_resize event trigger.

    Returns:
        A tuple containing window width and height variables.
    """
    return (Var("window.innerWidth"), Var("window.innerHeight"))


def _on_scroll_spec() -> tuple[Var[float], Var[float]]:
    """Args spec for the on_scroll event trigger.

    Returns:
        A tuple containing window scroll X and Y position variables.
    """
    return (Var("window.scrollX"), Var("window.scrollY"))


def _on_visibility_change_spec() -> tuple[Var[bool]]:
    """Args spec for the on_visibility_change event trigger.

    Returns:
        A tuple containing the document hidden state variable.
    """
    return (Var("document.hidden"),)


def _on_storage_spec(e: ObjectVar) -> tuple[Var[str], Var[str], Var[str], Var[str]]:
    """Args spec for the on_storage event trigger.

    Args:
        e: The storage event.

    Returns:
        A tuple containing key, old value, new value, and URL variables.
    """
    return (e.key.to(str), e.oldValue.to(str), e.newValue.to(str), e.url.to(str))


class WindowEventListener(Fragment):
    """A component that listens for window events."""

    on_resize: EventHandler[_on_resize_spec] = field(
        doc="Triggered when the browser window is resized. Receives the new width and height in pixels."
    )
    on_scroll: EventHandler[_on_scroll_spec] = field(
        doc="Triggered when the user scrolls the page. Receives the current horizontal and vertical scroll positions."
    )
    on_focus: EventHandler[no_args_event_spec] = field(
        doc="Triggered when the browser tab or window gains focus (e.g. user switches back to the tab)."
    )
    on_blur: EventHandler[no_args_event_spec] = field(
        doc="Triggered when the browser tab or window loses focus (e.g. user switches to another tab)."
    )
    on_visibility_change: EventHandler[_on_visibility_change_spec] = field(
        doc="Triggered when the page becomes visible or hidden (e.g. tab switch or minimize). Receives a boolean indicating whether the document is hidden."
    )
    on_before_unload: EventHandler[no_args_event_spec] = field(
        doc="Triggered just before the user navigates away from or closes the page. Useful for cleanup or prompting unsaved-changes warnings."
    )
    on_key_down: EventHandler[key_event] = field(
        doc="Triggered when a key is pressed anywhere on the page. Receives the key name and active modifier keys (shift, ctrl, alt, meta)."
    )
    on_popstate: EventHandler[no_args_event_spec] = field(
        doc="Triggered when the user navigates back or forward via the browser history buttons."
    )
    on_storage: EventHandler[_on_storage_spec] = field(
        doc="Triggered when localStorage or sessionStorage is modified in another tab. Receives the key, old value, new value, and the URL of the document that changed the storage."
    )

    hooks: list[str] = field(default_factory=list, is_javascript_property=False)

    @classmethod
    def create(cls, **props) -> WindowEventListener:
        """Create a WindowEventListener component.

        Args:
            **props: The props to set on the component.

        Returns:
            The created component.
        """
        real_component = cast("WindowEventListener", super().create(**props))
        hooks = StatefulComponent._fix_event_triggers(real_component)
        real_component.hooks = hooks
        return real_component

    def _exclude_props(self) -> list[str]:
        """Exclude event handler props from being passed to Fragment.

        Returns:
            List of prop names to exclude from the Fragment.
        """
        return [*super()._exclude_props(), *self.event_triggers.keys()]

    def add_hooks(self) -> list[str | Var[Any]]:
        """Add hooks to register window event listeners.

        Returns:
            The hooks to add to the component.
        """
        hooks: list[str | Var[Any]] = [*self.hooks]

        for prop_name, event_trigger in self.event_triggers.items():
            # Get JS event name: remove on_ prefix and underscores
            event_name = prop_name.removeprefix("on_").replace("_", "")

            hook_expr = f"""
useEffect(() => {{
    if (typeof window === 'undefined') return;
    const fn = {Var.create(event_trigger)};
    window.addEventListener('{event_name}', fn);
    return () => window.removeEventListener('{event_name}', fn);
}}, []);
                """

            hooks.append(
                Var(
                    hook_expr,
                    _var_data=VarData(position=Hooks.HookPosition.POST_TRIGGER),
                )
            )

        return hooks


window_event_listener = WindowEventListener.create
