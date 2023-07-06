"""Base component definitions."""

from __future__ import annotations

import typing
from abc import ABC
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

from reflex import constants
from reflex.base import Base
from reflex.components.tags import Tag
from reflex.event import (
    EVENT_ARG,
    EVENT_TRIGGERS,
    EventChain,
    EventHandler,
    EventSpec,
    call_event_fn,
    call_event_handler,
    get_handler_args,
)
from reflex.style import Style
from reflex.utils import format, imports, types
from reflex.vars import BaseVar, ImportVar, Var


class Component(Base, ABC):
    """The base class for all Reflex components."""

    # The children nested within the component.
    children: List[Component] = []

    # The style of the component.
    style: Style = Style()

    # A mapping from event triggers to event chains.
    event_triggers: Dict[str, Union[EventChain, Var]] = {}

    # The library that the component is based on.
    library: Optional[str] = None

    # The tag to use when rendering the component.
    tag: Optional[str] = None

    # The alias for the tag.
    alias: Optional[str] = None

    # Whether the import is default or named.
    is_default: Optional[bool] = False

    # A unique key for the component.
    key: Any = None

    # The id for the component.
    id: Any = None

    # The class name for the component.
    class_name: Any = None

    # Special component props.
    special_props: Set[Var] = set()

    # Whether the component should take the focus once the page is loaded
    autofocus: bool = False

    # components that cannot be children
    invalid_children: List[str] = []
    # custom attribute
    custom_attrs: Dict[str, str] = {}

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Set default properties.

        Args:
            **kwargs: The kwargs to pass to the superclass.
        """
        super().__init_subclass__(**kwargs)

        # Get all the props for the component.
        props = cls.get_props()

        # Convert fields to props, setting default values.
        for field in cls.get_fields().values():
            # If the field is not a component prop, skip it.
            if field.name not in props:
                continue

            # Set default values for any props.
            if types._issubclass(field.type_, Var):
                field.required = False
                field.default = Var.create(field.default)

    def __init__(self, *args, **kwargs):
        """Initialize the component.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.

        Raises:
            TypeError: If an invalid prop is passed.
        """
        # Set the id and children initially.
        initial_kwargs = {
            "id": kwargs.get("id"),
            "children": kwargs.get("children", []),
            **{
                prop: Var.create(kwargs[prop])
                for prop in self.get_initial_props()
                if prop in kwargs
            },
        }
        super().__init__(**initial_kwargs)

        # Get the component fields, triggers, and props.
        fields = self.get_fields()
        triggers = self.get_triggers()
        props = self.get_props()

        # Add any events triggers.
        if "event_triggers" not in kwargs:
            kwargs["event_triggers"] = {}
        kwargs["event_triggers"] = kwargs["event_triggers"].copy()

        # Iterate through the kwargs and set the props.
        for key, value in kwargs.items():
            if key in triggers:
                # Event triggers are bound to event chains.
                field_type = EventChain
            elif key in props:
                # Set the field type.
                field_type = fields[key].type_

            else:
                continue

            # Check whether the key is a component prop.
            if types._issubclass(field_type, Var):
                try:
                    # Try to create a var from the value.
                    kwargs[key] = Var.create(value)

                    # Check that the var type is not None.
                    if kwargs[key] is None:
                        raise TypeError

                    # Get the passed type and the var type.
                    passed_type = kwargs[key].type_
                    expected_type = fields[key].outer_type_.__args__[0]
                except TypeError:
                    # If it is not a valid var, check the base types.
                    passed_type = type(value)
                    expected_type = fields[key].outer_type_
                if not types._issubclass(passed_type, expected_type):
                    raise TypeError(
                        f"Invalid var passed for prop {key}, expected type {expected_type}, got value {value} of type {passed_type}."
                    )

            # Check if the key is an event trigger.
            if key in triggers:
                state_name = kwargs["value"].name if kwargs.get("value", False) else ""
                # Temporarily disable full control for event triggers.
                full_control = False
                kwargs["event_triggers"][key] = self._create_event_chain(
                    key, value, state_name, full_control
                )

        # Remove any keys that were added as events.
        for key in kwargs["event_triggers"]:
            del kwargs[key]

        # Add style props to the component.
        style = kwargs.get("style", {})
        if isinstance(style, List):
            # Merge styles, the later ones overriding keys in the earlier ones.
            style = {k: v for style_dict in style for k, v in style_dict.items()}

        kwargs["style"] = Style(
            {
                **style,
                **{attr: value for attr, value in kwargs.items() if attr not in fields},
            }
        )
        if "custom_attrs" not in kwargs:
            kwargs["custom_attrs"] = {}

        # Convert class_name to str if it's list
        class_name = kwargs.get("class_name", "")
        if isinstance(class_name, (List, tuple)):
            kwargs["class_name"] = " ".join(class_name)

        # Construct the component.
        super().__init__(*args, **kwargs)

    def _create_event_chain(
        self,
        event_trigger: str,
        value: Union[
            Var, EventHandler, EventSpec, List[Union[EventHandler, EventSpec]], Callable
        ],
        state_name: str = "",
        full_control: bool = False,
    ) -> Union[EventChain, Var]:
        """Create an event chain from a variety of input types.

        Args:
            event_trigger: The event trigger to bind the chain to.
            value: The value to create the event chain from.
            state_name: The state to be fully controlled.
            full_control: Whether full controlled or not.

        Returns:
            The event chain.

        Raises:
            ValueError: If the value is not a valid event chain.
        """
        # Check if the trigger is a controlled event.
        controlled_triggers = self.get_controlled_triggers()
        is_controlled_event = event_trigger in controlled_triggers

        # If it's an event chain var, return it.
        if isinstance(value, Var):
            if value.type_ is not EventChain:
                raise ValueError(f"Invalid event chain: {value}")
            return value

        arg = controlled_triggers.get(event_trigger, EVENT_ARG)

        # If the input is a single event handler, wrap it in a list.
        if isinstance(value, (EventHandler, EventSpec)):
            value = [value]

        # If the input is a list of event handlers, create an event chain.
        if isinstance(value, List):
            events = []
            for v in value:
                if isinstance(v, EventHandler):
                    # Call the event handler to get the event.
                    event = call_event_handler(v, arg)

                    # Check that the event handler takes no args if it's uncontrolled.
                    if not is_controlled_event and (
                        event.args is not None and len(event.args) > 0
                    ):
                        raise ValueError(
                            f"Event handler: {v.fn} for uncontrolled event {event_trigger} should not take any args."
                        )

                    # Add the event to the chain.
                    events.append(event)
                elif isinstance(v, EventSpec):
                    # Add the event to the chain.
                    events.append(v)
                elif isinstance(v, Callable):
                    # Call the lambda to get the event chain.
                    events.extend(call_event_fn(v, arg))
                else:
                    raise ValueError(f"Invalid event: {v}")

        # If the input is a callable, create an event chain.
        elif isinstance(value, Callable):
            events = call_event_fn(value, arg)

        # Otherwise, raise an error.
        else:
            raise ValueError(f"Invalid event chain: {value}")

        # Add args to the event specs if necessary.
        if is_controlled_event:
            events = [
                EventSpec(
                    handler=e.handler,
                    args=get_handler_args(e, arg),
                )
                for e in events
            ]

        # set state name when fully controlled input
        state_name = state_name if full_control else ""

        # Return the event chain.
        return EventChain(
            events=events, state_name=state_name, full_control=full_control
        )

    def get_triggers(self) -> Set[str]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return EVENT_TRIGGERS | set(self.get_controlled_triggers())

    def get_controlled_triggers(self) -> Dict[str, Var]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {}

    def __repr__(self) -> str:
        """Represent the component in React.

        Returns:
            The code to render the component.
        """
        return format.json_dumps(self.render())

    def __str__(self) -> str:
        """Represent the component in React.

        Returns:
            The code to render the component.
        """
        return format.json_dumps(self.render())

    def _render(self) -> Tag:
        """Define how to render the component in React.

        Returns:
            The tag to render.
        """
        # Create the base tag.
        tag = Tag(
            name=self.tag if not self.alias else self.alias,
            special_props=self.special_props,
        )

        # Add component props to the tag.
        props = {
            attr[:-1] if attr.endswith("_") else attr: getattr(self, attr)
            for attr in self.get_props()
        }

        # Add ref to element if `id` is not None.
        ref = self.get_ref()
        if ref is not None:
            props["ref"] = Var.create(ref, is_local=False)

        return tag.add_props(**props)

    @classmethod
    def get_props(cls) -> Set[str]:
        """Get the unique fields for the component.

        Returns:
            The unique fields.
        """
        return set(cls.get_fields()) - set(Component.get_fields())

    @classmethod
    def get_initial_props(cls) -> Set[str]:
        """Get the initial props to set for the component.

        Returns:
            The initial props to set.
        """
        return set()

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.

        Raises:
            TypeError: If an invalid child is passed.
        """
        # Import here to avoid circular imports.
        from reflex.components.base.bare import Bare

        # Validate all the children.
        for child in children:
            # Make sure the child is a valid type.
            if not types._isinstance(child, ComponentChild):
                raise TypeError(
                    "Children of Reflex components must be other components, "
                    "state vars, or primitive Python types. "
                    f"Got child {child} of type {type(child)}.",
                )

        children = [
            child
            if isinstance(child, Component)
            else Bare.create(contents=Var.create(child, is_string=True))
            for child in children
        ]
        return cls(children=children, **props)

    def _add_style(self, style):
        self.style.update(style)

    def add_style(self, style: ComponentStyle) -> Component:
        """Add additional style to the component and its children.

        Args:
            style: A dict from component to styling.

        Returns:
            The component with the additional style.
        """
        if type(self) in style:
            # Extract the style for this component.
            component_style = Style(style[type(self)])

            # Only add style props that are not overridden.
            component_style = {
                k: v for k, v in component_style.items() if k not in self.style
            }

            # Add the style to the component.
            self._add_style(component_style)

        # Recursively add style to the children.
        for child in self.children:
            child.add_style(style)
        return self

    def render(self) -> Dict:
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        tag = self._render()

        rendered_dict = dict(
            tag.add_props(
                **self.event_triggers,
                key=self.key,
                sx=self.style,
                id=self.id,
                class_name=self.class_name,
                **self.custom_attrs,
            ).set(
                children=[child.render() for child in self.children],
                contents=str(tag.contents),
                props=tag.format_props(),
            ),
            autofocus=self.autofocus,
        )
        self._validate_component_children(
            rendered_dict["name"], rendered_dict["children"]
        )
        return rendered_dict

    def _validate_component_children(self, comp_name: str, children: List[Dict]):
        """Validate the children components.

        Args:
            comp_name: name of the component.
            children: list of children components.

        Raises:
            ValueError: when an unsupported component is matched.
        """
        if not self.invalid_children:
            return
        for child in children:
            name = child["name"]
            if name in self.invalid_children:
                raise ValueError(
                    f"The component `{comp_name.lower()}` cannot have `{name.lower()}` as a child component"
                )

    def _get_custom_code(self) -> Optional[str]:
        """Get custom code for the component.

        Returns:
            The custom code.
        """
        return None

    def get_custom_code(self) -> Set[str]:
        """Get custom code for the component and its children.

        Returns:
            The custom code.
        """
        # Store the code in a set to avoid duplicates.
        code = set()

        # Add the custom code for this component.
        custom_code = self._get_custom_code()
        if custom_code is not None:
            code.add(custom_code)

        # Add the custom code for the children.
        for child in self.children:
            code |= child.get_custom_code()

        # Return the code.
        return code

    def _get_imports(self) -> imports.ImportDict:
        if self.library is not None and self.tag is not None:
            return {self.library: {self.import_var}}
        return {}

    def get_imports(self) -> imports.ImportDict:
        """Get all the libraries and fields that are used by the component.

        Returns:
            The import dict with the required imports.
        """
        return imports.merge_imports(
            self._get_imports(), *[child.get_imports() for child in self.children]
        )

    def _get_hooks(self) -> Optional[str]:
        """Get the React hooks for this component.

        Returns:
            The hooks for just this component.
        """
        ref = self.get_ref()
        if ref is not None:
            return f"const {ref} = useRef(null); refs['{ref}'] = {ref};"
        return None

    def get_hooks(self) -> Set[str]:
        """Get the React hooks for this component and its children.

        Returns:
            The code that should appear just before returning the rendered component.
        """
        # Store the code in a set to avoid duplicates.
        code = set()

        # Add the hook code for this component.
        hooks = self._get_hooks()
        if hooks is not None:
            code.add(hooks)

        # Add the hook code for the children.
        for child in self.children:
            code |= child.get_hooks()

        return code

    def get_ref(self) -> Optional[str]:
        """Get the name of the ref for the component.

        Returns:
            The ref name.
        """
        # do not create a ref if the id is dynamic or unspecified
        if self.id is None or isinstance(self.id, BaseVar):
            return None
        return format.format_ref(self.id)

    def get_refs(self) -> Set[str]:
        """Get the refs for the children of the component.

        Returns:
            The refs for the children.
        """
        refs = set()
        ref = self.get_ref()
        if ref is not None:
            refs.add(ref)
        for child in self.children:
            refs |= child.get_refs()
        return refs

    def get_custom_components(
        self, seen: Optional[Set[str]] = None
    ) -> Set[CustomComponent]:
        """Get all the custom components used by the component.

        Args:
            seen: The tags of the components that have already been seen.

        Returns:
            The set of custom components.
        """
        custom_components = set()

        # Store the seen components in a set to avoid infinite recursion.
        if seen is None:
            seen = set()
        for child in self.children:
            custom_components |= child.get_custom_components(seen=seen)
        return custom_components

    @property
    def import_var(self):
        """The tag to import.

        Returns:
            An import var.
        """
        return ImportVar(tag=self.tag, is_default=self.is_default, alias=self.alias)

    def is_full_control(self, kwargs: dict) -> bool:
        """Return if the component is fully controlled input.

        Args:
            kwargs: The component kwargs.

        Returns:
            Whether fully controlled.
        """
        value = kwargs.get("value")
        if value is None or type(value) != BaseVar:
            return False

        on_change = kwargs.get("on_change")
        if on_change is None or type(on_change) != EventHandler:
            return False

        value = value.full_name
        on_change = on_change.fn.__qualname__
        return value == on_change.replace(constants.SETTER_PREFIX, "")


# Map from component to styling.
ComponentStyle = Dict[Union[str, Type[Component]], Any]
ComponentChild = Union[types.PrimitiveType, Var, Component]


class CustomComponent(Component):
    """A custom user-defined component."""

    # Use the components library.
    library = f"/{constants.COMPONENTS_PATH}"

    # The function that creates the component.
    component_fn: Callable[..., Component] = Component.create

    # The props of the component.
    props: Dict[str, Any] = {}

    def __init__(self, *args, **kwargs):
        """Initialize the custom component.

        Args:
            *args: The args to pass to the component.
            **kwargs: The kwargs to pass to the component.
        """
        super().__init__(*args, **kwargs)

        # Unset the style.
        self.style = Style()

        # Set the tag to the name of the function.
        self.tag = format.to_title_case(self.component_fn.__name__)

        # Set the props.
        props = typing.get_type_hints(self.component_fn)
        for key, value in kwargs.items():
            if key not in props:
                continue
            type_ = props[key]
            if types._issubclass(type_, EventChain):
                value = self._create_event_chain(key, value)
                self.props[format.to_camel_case(key)] = value
                continue
            if not types._issubclass(type_, Var):
                type_ = Var[type_]
            type_ = types.get_args(type_)[0]
            if types._issubclass(type_, Base):
                try:
                    value = BaseVar(name=value.json(), type_=type_, is_local=True)
                except Exception:
                    value = Var.create(value)
            else:
                value = Var.create(value, is_string=type(value) is str)
            self.props[format.to_camel_case(key)] = value

    def __eq__(self, other: Any) -> bool:
        """Check if the component is equal to another.

        Args:
            other: The other component.

        Returns:
            Whether the component is equal to the other.
        """
        return isinstance(other, CustomComponent) and self.tag == other.tag

    def __hash__(self) -> int:
        """Get the hash of the component.

        Returns:
            The hash of the component.
        """
        return hash(self.tag)

    @classmethod
    def get_props(cls) -> Set[str]:
        """Get the props for the component.

        Returns:
            The set of component props.
        """
        return set()

    def get_custom_components(
        self, seen: Optional[Set[str]] = None
    ) -> Set[CustomComponent]:
        """Get all the custom components used by the component.

        Args:
            seen: The tags of the components that have already been seen.

        Returns:
            The set of custom components.
        """
        assert self.tag is not None, "The tag must be set."

        # Store the seen components in a set to avoid infinite recursion.
        if seen is None:
            seen = set()
        custom_components = {self} | super().get_custom_components(seen=seen)

        # Avoid adding the same component twice.
        if self.tag not in seen:
            seen.add(self.tag)
            custom_components |= self.get_component().get_custom_components(seen=seen)
        return custom_components

    def _render(self) -> Tag:
        """Define how to render the component in React.

        Returns:
            The tag to render.
        """
        return Tag(name=self.tag).add_props(**self.props)

    def get_prop_vars(self) -> List[BaseVar]:
        """Get the prop vars.

        Returns:
            The prop vars.
        """
        return [
            BaseVar(
                name=name,
                type_=prop.type_ if types._isinstance(prop, Var) else type(prop),
            )
            for name, prop in self.props.items()
        ]

    def get_component(self) -> Component:
        """Render the component.

        Returns:
            The code to render the component.
        """
        return self.component_fn(*self.get_prop_vars())


def custom_component(
    component_fn: Callable[..., Component]
) -> Callable[..., CustomComponent]:
    """Create a custom component from a function.

    Args:
        component_fn: The function that creates the component.

    Returns:
        The decorated function.
    """

    @wraps(component_fn)
    def wrapper(*children, **props) -> CustomComponent:
        return CustomComponent(component_fn=component_fn, children=children, **props)

    return wrapper
