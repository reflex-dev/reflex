"""The built-in states used by reflex apps."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar, Type

import reflex.istate.dynamic
from reflex import constants, event
from reflex.event import Event, EventSpec, fix_events
from reflex.state import BaseState
from reflex.utils import prerequisites

if TYPE_CHECKING:
    from reflex.components.component import Component


class State(BaseState):
    """The app Base State."""

    # The hydrated bool.
    is_hydrated: bool = False


class FrontendEventExceptionState(State):
    """Substate for handling frontend exceptions."""

    @event
    def handle_frontend_exception(self, stack: str, component_stack: str) -> None:
        """Handle frontend exceptions.

        If a frontend exception handler is provided, it will be called.
        Otherwise, the default frontend exception handler will be called.

        Args:
            stack: The stack trace of the exception.
            component_stack: The stack trace of the component where the exception occurred.

        """
        app_instance = getattr(prerequisites.get_app(), constants.CompileVars.APP)
        app_instance.frontend_exception_handler(Exception(stack))


class UpdateVarsInternalState(State):
    """Substate for handling internal state var updates."""

    async def update_vars_internal(self, vars: dict[str, Any]) -> None:
        """Apply updates to fully qualified state vars.

        The keys in `vars` should be in the form of `{state.get_full_name()}.{var_name}`,
        and each value will be set on the appropriate substate instance.

        This function is primarily used to apply cookie and local storage
        updates from the frontend to the appropriate substate.

        Args:
            vars: The fully qualified vars and values to update.
        """
        for var, value in vars.items():
            state_name, _, var_name = var.rpartition(".")
            var_state_cls = State.get_class_substate(state_name)
            var_state = await self.get_state(var_state_cls)
            setattr(var_state, var_name, value)


class OnLoadInternalState(State):
    """Substate for handling on_load event enumeration.

    This is a separate substate to avoid deserializing the entire state tree for every page navigation.
    """

    def on_load_internal(self) -> list[Event | EventSpec] | None:
        """Queue on_load handlers for the current page.

        Returns:
            The list of events to queue for on load handling.
        """
        # Do not app._compile()!  It should be already compiled by now.
        app = getattr(prerequisites.get_app(), constants.CompileVars.APP)
        load_events = app.get_load_events(self.router.page.path)
        if not load_events:
            self.is_hydrated = True
            return  # Fast path for navigation with no on_load events defined.
        self.is_hydrated = False
        return [
            *fix_events(
                load_events,
                self.router.session.client_token,
                router_data=self.router_data,
            ),
            State.set_is_hydrated(True),  # type: ignore
        ]


class ComponentState(State, mixin=True):
    """Base class to allow for the creation of a state instance per component.

    This allows for the bundling of UI and state logic into a single class,
    where each instance has a separate instance of the state.

    Subclass this class and define vars and event handlers in the traditional way.
    Then define a `get_component` method that returns the UI for the component instance.

    See the full [docs](https://reflex.dev/docs/substates/component-state/) for more.

    Basic example:
    ```python
    # Subclass ComponentState and define vars and event handlers.
    class Counter(rx.ComponentState):
        # Define vars that change.
        count: int = 0

        # Define event handlers.
        def increment(self):
            self.count += 1

        def decrement(self):
            self.count -= 1

        @classmethod
        def get_component(cls, **props):
            # Access the state vars and event handlers using `cls`.
            return rx.hstack(
                rx.button("Decrement", on_click=cls.decrement),
                rx.text(cls.count),
                rx.button("Increment", on_click=cls.increment),
                **props,
            )

    counter = Counter.create()
    ```
    """

    # The number of components created from this class.
    _per_component_state_instance_count: ClassVar[int] = 0

    @classmethod
    def __init_subclass__(cls, mixin: bool = True, **kwargs):
        """Overwrite mixin default to True.

        Args:
            mixin: Whether the subclass is a mixin and should not be initialized.
            **kwargs: The kwargs to pass to the pydantic init_subclass method.
        """
        super().__init_subclass__(mixin=mixin, **kwargs)

    @classmethod
    def get_component(cls, *children, **props) -> "Component":
        """Get the component instance.

        Args:
            children: The children of the component.
            props: The props of the component.

        Raises:
            NotImplementedError: if the subclass does not override this method.
        """
        raise NotImplementedError(
            f"{cls.__name__} must implement get_component to return the component instance."
        )

    @classmethod
    def create(cls, *children, **props) -> "Component":
        """Create a new instance of the Component.

        Args:
            children: The children of the component.
            props: The props of the component.

        Returns:
            A new instance of the Component with an independent copy of the State.
        """
        cls._per_component_state_instance_count += 1
        state_cls_name = f"{cls.__name__}_n{cls._per_component_state_instance_count}"
        component_state = type(
            state_cls_name,
            (cls, State),
            {"__module__": reflex.istate.dynamic.__name__},
            mixin=False,
        )
        # Save a reference to the dynamic state for pickle/unpickle.
        setattr(reflex.istate.dynamic, state_cls_name, component_state)
        component = component_state.get_component(*children, **props)
        component.State = component_state
        return component


def reload_state_module(
    module: str,
    state: Type[BaseState] = State,
) -> None:
    """Reset rx.State subclasses to avoid conflict when reloading.

    Args:
        module: The module to reload.
        state: Recursive argument for the state class to reload.

    """
    for subclass in tuple(state.class_subclasses):
        reload_state_module(module=module, state=subclass)
        if subclass.__module__ == module and module is not None:
            state.class_subclasses.remove(subclass)
            state._always_dirty_substates.discard(subclass.get_name())
            state._computed_var_dependencies = defaultdict(set)
            state._substate_var_dependencies = defaultdict(set)
            state._init_var_dependency_dicts()
    state.get_class_substate.cache_clear()
