"""Base component definitions."""

from __future__ import annotations

from abc import ABC
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

from pynecone import utils
from pynecone.base import Base
from pynecone.components.tags import Tag
from pynecone.event import (
    EVENT_ARG,
    EVENT_TRIGGERS,
    EventChain,
    EventHandler,
    EventSpec,
)
from pynecone.style import Style
from pynecone.var import Var

ImportDict = Dict[str, Set[str]]


class Component(Base, ABC):
    """The base class for all Pynecone components."""

    # The children nested within the component.
    children: List[Component] = []

    # The style of the component.
    style: Style = Style()

    # A mapping from event triggers to event chains.
    event_triggers: Dict[str, EventChain] = {}

    # The library that the component is based on.
    library: Optional[str] = None

    # The tag to use when rendering the component.
    tag: Optional[str] = None

    # A unique key for the component.
    key: Any = None

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
            if utils._issubclass(field.type_, Var):
                field.required = False
                field.default = Var.create(field.default)

    def __init__(self, *args, **kwargs):
        """Initialize the component.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
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
            else:
                # If the key is not in the fields, skip it.
                if key not in props:
                    continue

                # Set the field type.
                field_type = fields[key].type_

            # Check whether the key is a component prop.
            if utils._issubclass(field_type, Var):
                # Convert any constants into vars and make sure the types match.
                kwargs[key] = Var.create(value)
                passed_type = kwargs[key].type_
                expected_type = fields[key].outer_type_.__args__[0]
                assert utils._issubclass(
                    passed_type, expected_type
                ), f"Invalid var passed for {key}, expected {expected_type}, got {passed_type}."

            # Check if the key is an event trigger.
            if key in triggers:
                kwargs["event_triggers"][key] = self._create_event_chain(key, value)

        # Remove any keys that were added as events.
        for key in kwargs["event_triggers"]:
            del kwargs[key]

        # Add style props to the component.
        kwargs["style"] = Style(
            {
                **kwargs.get("style", {}),
                **{attr: value for attr, value in kwargs.items() if attr not in fields},
            }
        )

        # Construct the component.
        super().__init__(*args, **kwargs)

    def _create_event_chain(
        self,
        event_trigger: str,
        value: Union[EventHandler, List[EventHandler], Callable],
    ) -> EventChain:
        """Create an event chain from a variety of input types.

        Args:
            event_trigger: The event trigger to bind the chain to.
            value: The value to create the event chain from.

        Returns:
            The event chain.

        Raises:
            ValueError: If the value is not a valid event chain.
        """
        arg = self.get_controlled_value()

        # If the input is a single event handler, wrap it in a list.
        if isinstance(value, EventHandler):
            value = [value]

        # If the input is a list of event handlers, create an event chain.
        if isinstance(value, List):
            events = [utils.call_event_handler(v, arg) for v in value]

        # If the input is a callable, create an event chain.
        elif isinstance(value, Callable):
            events = utils.call_event_fn(value, arg)

        # Otherwise, raise an error.
        else:
            raise ValueError(f"Invalid event chain: {value}")

        # Add args to the event specs if necessary.
        if event_trigger in self.get_controlled_triggers():
            events = [
                EventSpec(
                    handler=e.handler,
                    local_args=(EVENT_ARG.name,),
                    args=utils.get_handler_args(e, arg),
                )
                for e in events
            ]

        # Return the event chain.
        return EventChain(events=events)

    @classmethod
    def get_triggers(cls) -> Set[str]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return EVENT_TRIGGERS | cls.get_controlled_triggers()

    @classmethod
    def get_controlled_triggers(cls) -> Set[str]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            The controlled event triggers.
        """
        return set()

    @classmethod
    def get_controlled_value(cls) -> Var:
        """Get the var that is passed to the event handler for controlled triggers.

        Returns:
            The controlled value.
        """
        return EVENT_ARG

    def __repr__(self) -> str:
        """Represent the component in React.

        Returns:
            The code to render the component.
        """
        return self.render()

    def __str__(self) -> str:
        """Represent the component in React.

        Returns:
            The code to render the component.
        """
        return self.render()

    def _render(self) -> Tag:
        """Define how to render the component in React.

        Returns:
            The tag to render.
        """
        # Create the base tag.
        tag = Tag(name=self.tag)

        # Add component props to the tag.
        props = {attr: getattr(self, attr) for attr in self.get_props()}

        # Special case for props named `type_`.
        if hasattr(self, "type_"):
            props["type"] = getattr(self, "type_")

        return tag.add_props(**props)

    @classmethod
    def get_props(cls) -> Set[str]:
        """Get the unique fields for the component.

        Returns:
            The unique fields.
        """
        return set(cls.get_fields()) - set(Component.get_fields())

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.
        """
        # Import here to avoid circular imports.
        from pynecone.components.base.bare import Bare

        children = [
            Bare.create(contents=Var.create(child, is_string=True))
            if not isinstance(child, Component)
            else child
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

            # Only add stylee props that are not overriden.
            component_style = {
                k: v for k, v in component_style.items() if k not in self.style
            }

            # Add the style to the component.
            self._add_style(component_style)

        # Recursively add style to the children.
        for child in self.children:
            child.add_style(style)
        return self

    def render(self) -> str:
        """Render the component.

        Returns:
            The code to render the component.
        """
        tag = self._render()
        return str(
            tag.add_props(**self.event_triggers, key=self.key, sx=self.style).set(
                contents=utils.join(
                    [str(tag.contents)] + [child.render() for child in self.children]
                ),
            )
        )

    def _get_custom_code(self) -> str:
        """Get custom code for the component.

        Returns:
            The custom code.
        """
        return ""

    def get_custom_code(self) -> str:
        """Get custom code for the component and its children.

        Returns:
            The custom code.
        """
        code = self._get_custom_code()
        for child in self.children:
            child_code = child.get_custom_code()
            if child_code != "" and child_code not in code:
                code += "\n" + child_code
        return code

    def _get_imports(self) -> ImportDict:
        if self.library is not None and self.tag is not None:
            return {self.library: {self.tag}}
        return {}

    def get_imports(self) -> ImportDict:
        """Get all the libraries and fields that are used by the component.

        Returns:
            The import dict with the required imports.
        """
        return utils.merge_imports(
            self._get_imports(), *[child.get_imports() for child in self.children]
        )


# Map from component to styling.
ComponentStyle = Dict[Union[str, Type[Component]], Any]
