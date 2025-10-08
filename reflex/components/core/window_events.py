"""Window event listener component for Reflex."""

import reflex as rx
from reflex.components.base.fragment import Fragment
from reflex.constants.compiler import Hooks
from reflex.event import key_event, no_args_event_spec
from reflex.vars.base import Var, VarData
from reflex.vars.object import ObjectVar


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

    # Event handlers
    on_resize: rx.EventHandler[_on_resize_spec]
    on_scroll: rx.EventHandler[_on_scroll_spec]
    on_focus: rx.EventHandler[no_args_event_spec]
    on_blur: rx.EventHandler[no_args_event_spec]
    on_visibility_change: rx.EventHandler[_on_visibility_change_spec]
    on_before_unload: rx.EventHandler[no_args_event_spec]
    on_key_down: rx.EventHandler[key_event]
    on_popstate: rx.EventHandler[no_args_event_spec]
    on_storage: rx.EventHandler[_on_storage_spec]

    def _exclude_props(self) -> list[str]:
        """Exclude event handler props from being passed to Fragment.

        Returns:
            List of prop names to exclude from the Fragment.
        """
        return [*super()._exclude_props(), *self.event_triggers.keys()]

    def add_hooks(self) -> list[str | Var[str]]:
        """Add hooks to register window event listeners.

        Returns:
            The hooks to add to the component.
        """
        hooks = []

        for prop_name, event_trigger in self.event_triggers.items():
            # Get JS event name: remove on_ prefix and underscores
            event_name = prop_name.removeprefix("on_").replace("_", "")

            hook_expr = f"""
                    useEffect(() => {{
                        if (typeof window === 'undefined') return;

                        window.addEventListener('{event_name}', {event_trigger});
                        return () => window.removeEventListener('{event_name}', {event_trigger});
                    }}, []);
                """

            hooks.append(
                Var(
                    hook_expr,
                    _var_type="str",
                    _var_data=VarData(position=Hooks.HookPosition.POST_TRIGGER),
                )
            )

        return hooks


window_event_listener = WindowEventListener.create
