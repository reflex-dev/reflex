"""Base component definitions."""

from __future__ import annotations

import copy
import typing
from abc import ABC, abstractmethod
from functools import lru_cache, wraps
from hashlib import md5
from types import SimpleNamespace
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Type,
    Union,
)

from reflex.base import Base
from reflex.compiler.templates import STATEFUL_COMPONENT
from reflex.components.tags import Tag
from reflex.constants import (
    Dirs,
    EventTriggers,
    Hooks,
    Imports,
    MemoizationDisposition,
    MemoizationMode,
    PageNames,
)
from reflex.event import (
    EventChain,
    EventHandler,
    EventSpec,
    call_event_fn,
    call_event_handler,
    get_handler_args,
)
from reflex.style import Style, format_as_emotion
from reflex.utils import console, format, imports, types
from reflex.utils.imports import ImportVar
from reflex.utils.serializers import serializer
from reflex.vars import BaseVar, Var, VarData


class BaseComponent(Base, ABC):
    """The base class for all Reflex components.

    This is something that can be rendered as a Component via the Reflex compiler.
    """

    # The children nested within the component.
    children: List[BaseComponent] = []

    # The library that the component is based on.
    library: Optional[str] = None

    # List here the non-react dependency needed by `library`
    lib_dependencies: List[str] = []

    # The tag to use when rendering the component.
    tag: Optional[str] = None

    @abstractmethod
    def render(self) -> dict:
        """Render the component.

        Returns:
            The dictionary for template of the component.
        """

    @abstractmethod
    def get_hooks(self) -> set[str]:
        """Get the React hooks for this component.

        Returns:
            The code that should appear just before returning the rendered component.
        """

    @abstractmethod
    def get_imports(self) -> imports.ImportDict:
        """Get all the libraries and fields that are used by the component.

        Returns:
            The import dict with the required imports.
        """

    @abstractmethod
    def get_dynamic_imports(self) -> set[str]:
        """Get dynamic imports for the component.

        Returns:
            The dynamic imports.
        """

    @abstractmethod
    def get_custom_code(self) -> set[str]:
        """Get custom code for the component.

        Returns:
            The custom code.
        """

    @abstractmethod
    def get_refs(self) -> set[str]:
        """Get the refs for the children of the component.

        Returns:
            The refs for the children.
        """


class ComponentNamespace(SimpleNamespace):
    """A namespace to manage components with subcomponents."""

    def __hash__(self) -> int:
        """Get the hash of the namespace.


        Returns:
            The hash of the namespace.
        """
        return hash(self.__class__.__name__)


def evaluate_style_namespaces(style: ComponentStyle) -> dict:
    """Evaluate namespaces in the style.

    Args:
        style: The style to evaluate.

    Returns:
        The evaluated style.
    """
    return {
        k.__call__ if isinstance(k, ComponentNamespace) else k: v
        for k, v in style.items()
    }


# Map from component to styling.
ComponentStyle = Dict[
    Union[str, Type[BaseComponent], Callable, ComponentNamespace], Any
]
ComponentChild = Union[types.PrimitiveType, Var, BaseComponent]


class Component(BaseComponent, ABC):
    """A component with style, event trigger and other props."""

    # The style of the component.
    style: Style = Style()

    # A mapping from event triggers to event chains.
    event_triggers: Dict[str, Union[EventChain, Var]] = {}

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
    _invalid_children: List[str] = []

    # only components that are allowed as children
    _valid_children: List[str] = []

    # only components that are allowed as parent
    _valid_parents: List[str] = []

    # props to change the name of
    _rename_props: Dict[str, str] = {}

    # custom attribute
    custom_attrs: Dict[str, Union[Var, str]] = {}

    # When to memoize this component and its children.
    _memoization_mode: MemoizationMode = MemoizationMode()

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

        # Ensure renamed props from parent classes are applied to the subclass.
        if cls._rename_props:
            inherited_rename_props = {}
            for parent in reversed(cls.mro()):
                if issubclass(parent, Component) and parent._rename_props:
                    inherited_rename_props.update(parent._rename_props)
            cls._rename_props = inherited_rename_props

    def __init__(self, *args, **kwargs):
        """Initialize the component.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.

        Raises:
            TypeError: If an invalid prop is passed.
        """
        # Set the id and children initially.
        children = kwargs.get("children", [])
        initial_kwargs = {
            "id": kwargs.get("id"),
            "children": children,
            **{
                prop: Var.create(kwargs[prop])
                for prop in self.get_initial_props()
                if prop in kwargs
            },
        }
        super().__init__(**initial_kwargs)

        self._validate_component_children(children)

        # Get the component fields, triggers, and props.
        fields = self.get_fields()
        triggers = self.get_event_triggers().keys()
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

                    expected_type = fields[key].outer_type_.__args__[0]
                    # validate literal fields.
                    types.validate_literal(
                        key, value, expected_type, type(self).__name__
                    )
                    # Get the passed type and the var type.
                    passed_type = kwargs[key]._var_type
                    expected_type = (
                        type(expected_type.__args__[0])
                        if types.is_literal(expected_type)
                        else expected_type
                    )
                except TypeError:
                    # If it is not a valid var, check the base types.
                    passed_type = type(value)
                    expected_type = fields[key].outer_type_
                if not types._issubclass(passed_type, expected_type):
                    value_name = value._var_name if isinstance(value, Var) else value
                    raise TypeError(
                        f"Invalid var passed for prop {key}, expected type {expected_type}, got value {value_name} of type {passed_type}."
                    )

            # Check if the key is an event trigger.
            if key in triggers:
                # Temporarily disable full control for event triggers.
                kwargs["event_triggers"][key] = self._create_event_chain(key, value)

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
                **self.get_fields()["style"].default,
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
    ) -> Union[EventChain, Var]:
        """Create an event chain from a variety of input types.

        Args:
            event_trigger: The event trigger to bind the chain to.
            value: The value to create the event chain from.

        Returns:
            The event chain.

        Raises:
            ValueError: If the value is not a valid event chain.
        """
        # Check if the trigger is a controlled event.
        triggers = self.get_event_triggers()

        # If it's an event chain var, return it.
        if isinstance(value, Var):
            if value._var_type is not EventChain:
                raise ValueError(f"Invalid event chain: {value}")
            return value
        elif isinstance(value, EventChain):
            # Trust that the caller knows what they're doing passing an EventChain directly
            return value

        arg_spec = triggers.get(event_trigger, lambda: [])

        # If the input is a single event handler, wrap it in a list.
        if isinstance(value, (EventHandler, EventSpec)):
            value = [value]

        # If the input is a list of event handlers, create an event chain.
        if isinstance(value, List):
            events: list[EventSpec] = []
            for v in value:
                if isinstance(v, EventHandler):
                    # Call the event handler to get the event.
                    try:
                        event = call_event_handler(v, arg_spec)  # type: ignore
                    except ValueError as err:
                        raise ValueError(
                            f" {err} defined in the `{type(self).__name__}` component"
                        ) from err

                    # Add the event to the chain.
                    events.append(event)
                elif isinstance(v, EventSpec):
                    # Add the event to the chain.
                    events.append(v)
                elif isinstance(v, Callable):
                    # Call the lambda to get the event chain.
                    events.extend(call_event_fn(v, arg_spec))  # type: ignore
                else:
                    raise ValueError(f"Invalid event: {v}")

        # If the input is a callable, create an event chain.
        elif isinstance(value, Callable):
            events = call_event_fn(value, arg_spec)  # type: ignore

        # Otherwise, raise an error.
        else:
            raise ValueError(f"Invalid event chain: {value}")

        # Add args to the event specs if necessary.
        events = [e.with_args(get_handler_args(e)) for e in events]

        # Collect event_actions from each spec
        event_actions = {}
        for e in events:
            event_actions.update(e.event_actions)

        # Return the event chain.
        if isinstance(arg_spec, Var):
            return EventChain(
                events=events,
                args_spec=None,
                event_actions=event_actions,
            )
        else:
            return EventChain(
                events=events,
                args_spec=arg_spec,  # type: ignore
                event_actions=event_actions,
            )

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return {
            EventTriggers.ON_FOCUS: lambda: [],
            EventTriggers.ON_BLUR: lambda: [],
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_CONTEXT_MENU: lambda: [],
            EventTriggers.ON_DOUBLE_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_DOWN: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
            EventTriggers.ON_MOUSE_MOVE: lambda: [],
            EventTriggers.ON_MOUSE_OUT: lambda: [],
            EventTriggers.ON_MOUSE_OVER: lambda: [],
            EventTriggers.ON_MOUSE_UP: lambda: [],
            EventTriggers.ON_SCROLL: lambda: [],
            EventTriggers.ON_MOUNT: lambda: [],
            EventTriggers.ON_UNMOUNT: lambda: [],
        }

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
        from reflex.compiler.compiler import _compile_component

        return _compile_component(self)

    def _apply_theme(self, theme: Optional[Component]):
        """Apply the theme to this component.

        Args:
            theme: The theme to apply.
        """
        pass

    def apply_theme(self, theme: Optional[Component]):
        """Apply a theme to the component and its children.

        Args:
            theme: The theme to apply.
        """
        self._apply_theme(theme)
        for child in self.children:
            if isinstance(child, Component):
                child.apply_theme(theme)

    def _exclude_props(self) -> list[str]:
        """Props to exclude when adding the component props to the Tag.

        Returns:
            A list of component props to exclude.
        """
        return []

    def _render(self, props: dict[str, Any] | None = None) -> Tag:
        """Define how to render the component in React.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag to render.
        """
        # Create the base tag.
        tag = Tag(
            name=self.tag if not self.alias else self.alias,
            special_props=self.special_props,
        )

        if props is None:
            # Add component props to the tag.
            props = {
                attr[:-1] if attr.endswith("_") else attr: getattr(self, attr)
                for attr in self.get_props()
            }

            # Add ref to element if `id` is not None.
            ref = self.get_ref()
            if ref is not None:
                props["ref"] = Var.create(ref, _var_is_local=False)
        else:
            props = props.copy()

        props.update(
            **{
                trigger: handler
                for trigger, handler in self.event_triggers.items()
                if trigger not in {EventTriggers.ON_MOUNT, EventTriggers.ON_UNMOUNT}
            },
            key=self.key,
            id=self.id,
            class_name=self.class_name,
        )
        props.update(self._get_style())
        props.update(self.custom_attrs)

        # remove excluded props from prop dict before adding to tag.
        for prop_to_exclude in self._exclude_props():
            props.pop(prop_to_exclude, None)

        return tag.add_props(**props)

    @classmethod
    @lru_cache(maxsize=None)
    def get_props(cls) -> Set[str]:
        """Get the unique fields for the component.

        Returns:
            The unique fields.
        """
        return set(cls.get_fields()) - set(Component.get_fields())

    @classmethod
    @lru_cache(maxsize=None)
    def get_initial_props(cls) -> Set[str]:
        """Get the initial props to set for the component.

        Returns:
            The initial props to set.
        """
        return set()

    @classmethod
    @lru_cache(maxsize=None)
    def get_component_props(cls) -> set[str]:
        """Get the props that expected a component as value.

        Returns:
            The components props.
        """
        return {
            name
            for name, field in cls.get_fields().items()
            if name in cls.get_props()
            and types._issubclass(field.outer_type_, Component)
        }

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

        # Translate deprecated props to new names.
        new_prop_names = [
            prop for prop in cls.get_props() if prop in ["type", "min", "max"]
        ]
        for prop in new_prop_names:
            under_prop = f"{prop}_"
            if under_prop in props:
                console.deprecate(
                    f"Underscore suffix for prop `{under_prop}`",
                    reason=f"for consistency. Use `{prop}` instead.",
                    deprecation_version="0.4.0",
                    removal_version="0.5.0",
                )
                props[prop] = props.pop(under_prop)

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
            else Bare.create(contents=Var.create(child, _var_is_string=True))
            for child in children
        ]

        return cls(children=children, **props)

    def _add_style(self, style: dict):
        """Add additional style to the component.

        Args:
            style: A style dict to apply.
        """
        self.style.update(style)

    def add_style(self, style: ComponentStyle) -> Component:
        """Add additional style to the component and its children.

        Args:
            style: A dict from component to styling.

        Returns:
            The component with the additional style.
        """
        component_style = None
        if type(self) in style:
            # Extract the style for this component.
            component_style = Style(style[type(self)])
        if self.create in style:
            component_style = Style(style[self.create])
        if component_style is not None:
            # Only add style props that are not overridden.
            component_style = {
                k: v for k, v in component_style.items() if k not in self.style
            }

            # Add the style to the component.
            self._add_style(component_style)

        # Recursively add style to the children.
        for child in self.children:
            # Skip BaseComponent and StatefulComponent children.
            if not isinstance(child, Component):
                continue
            child.add_style(style)
        return self

    def _get_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        if isinstance(self.style, Var):
            return {"css": self.style}
        return {"css": Var.create(format_as_emotion(self.style))}

    def render(self) -> Dict:
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        tag = self._render()
        rendered_dict = dict(
            tag.set(
                children=[child.render() for child in self.children],
                contents=str(tag.contents),
                props=tag.format_props(),
            ),
            autofocus=self.autofocus,
        )
        self._replace_prop_names(rendered_dict)
        return rendered_dict

    def _replace_prop_names(self, rendered_dict) -> None:
        """Replace the prop names in the render dictionary.

        Args:
            rendered_dict: The render dictionary with all the component props and event handlers.
        """
        # fast path
        if not self._rename_props:
            return

        for ix, prop in enumerate(rendered_dict["props"]):
            for old_prop, new_prop in self._rename_props.items():
                if prop.startswith(old_prop):
                    rendered_dict["props"][ix] = prop.replace(old_prop, new_prop, 1)

    def _validate_component_children(self, children: List[Component]):
        """Validate the children components.

        Args:
            children: The children of the component.

        """
        from reflex.components.base.fragment import Fragment
        from reflex.components.core.cond import Cond
        from reflex.components.core.foreach import Foreach
        from reflex.components.core.match import Match

        no_valid_parents_defined = all(child._valid_parents == [] for child in children)
        if (
            not self._invalid_children
            and not self._valid_children
            and no_valid_parents_defined
        ):
            return

        comp_name = type(self).__name__
        allowed_components = [
            comp.__name__ for comp in (Fragment, Foreach, Cond, Match)
        ]

        def validate_child(child):
            child_name = type(child).__name__

            # Iterate through the immediate children of fragment
            if isinstance(child, Fragment):
                for c in child.children:
                    validate_child(c)

            if isinstance(child, Cond):
                validate_child(child.comp1)
                validate_child(child.comp2)

            if isinstance(child, Match):
                for cases in child.match_cases:
                    validate_child(cases[-1])
                validate_child(child.default)

            if self._invalid_children and child_name in self._invalid_children:
                raise ValueError(
                    f"The component `{comp_name}` cannot have `{child_name}` as a child component"
                )

            if self._valid_children and child_name not in [
                *self._valid_children,
                *allowed_components,
            ]:
                valid_child_list = ", ".join(
                    [f"`{v_child}`" for v_child in self._valid_children]
                )
                raise ValueError(
                    f"The component `{comp_name}` only allows the components: {valid_child_list} as children. Got `{child_name}` instead."
                )

            if child._valid_parents and comp_name not in [
                *child._valid_parents,
                *allowed_components,
            ]:
                valid_parent_list = ", ".join(
                    [f"`{v_parent}`" for v_parent in child._valid_parents]
                )
                raise ValueError(
                    f"The component `{child_name}` can only be a child of the components: {valid_parent_list}. Got `{comp_name}` instead."
                )

        for child in children:
            validate_child(child)

    @staticmethod
    def _get_vars_from_event_triggers(
        event_triggers: dict[str, EventChain | Var],
    ) -> Iterator[tuple[str, list[Var]]]:
        """Get the Vars associated with each event trigger.

        Args:
            event_triggers: The event triggers from the component instance.

        Yields:
            tuple of (event_name, event_vars)
        """
        for event_trigger, event in event_triggers.items():
            if isinstance(event, Var):
                yield event_trigger, [event]
            elif isinstance(event, EventChain):
                event_args = []
                for spec in event.events:
                    for args in spec.args:
                        event_args.extend(args)
                yield event_trigger, event_args

    def _get_vars(self, include_children: bool = False) -> list[Var]:
        """Walk all Vars used in this component.

        Args:
            include_children: Whether to include Vars from children.

        Returns:
            Each var referenced by the component (props, styles, event handlers).
        """
        vars = getattr(self, "__vars", None)
        if vars is not None:
            return vars
        vars = self.__vars = []
        # Get Vars associated with event trigger arguments.
        for _, event_vars in self._get_vars_from_event_triggers(self.event_triggers):
            vars.extend(event_vars)

        # Get Vars associated with component props.
        for prop in self.get_props():
            prop_var = getattr(self, prop)
            if isinstance(prop_var, Var):
                vars.append(prop_var)

        # Style keeps track of its own VarData instance, so embed in a temp Var that is yielded.
        if isinstance(self.style, dict) and self.style or isinstance(self.style, Var):
            vars.append(
                BaseVar(
                    _var_name="style",
                    _var_type=str,
                    _var_data=self.style._var_data,
                )
            )

        # Special props are always Var instances.
        vars.extend(self.special_props)

        # Get Vars associated with common Component props.
        for comp_prop in (
            self.class_name,
            self.id,
            self.key,
            self.autofocus,
            *self.custom_attrs.values(),
        ):
            if isinstance(comp_prop, Var):
                vars.append(comp_prop)
            elif isinstance(comp_prop, str):
                # Collapse VarData encoded in f-strings.
                var = Var.create_safe(comp_prop)
                if var._var_data is not None:
                    vars.append(var)

        # Get Vars associated with children.
        if include_children:
            for child in self.children:
                if not isinstance(child, Component):
                    continue
                vars.extend(child._get_vars(include_children=include_children))

        return vars

    def _has_event_triggers(self) -> bool:
        """Check if the component or children have any event triggers.

        Returns:
            True if the component or children have any event triggers.
        """
        if self.event_triggers:
            return True
        else:
            for child in self.children:
                if isinstance(child, Component) and child._has_event_triggers():
                    return True
        return False

    def _get_custom_code(self) -> str | None:
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

    def _get_dynamic_imports(self) -> str | None:
        """Get dynamic import for the component.

        Returns:
            The dynamic import.
        """
        return None

    def get_dynamic_imports(self) -> Set[str]:
        """Get dynamic imports for the component and its children.

        Returns:
            The dynamic imports.
        """
        # Store the import in a set to avoid duplicates.
        dynamic_imports = set()

        # Get dynamic import for this component.
        dynamic_import = self._get_dynamic_imports()
        if dynamic_import:
            dynamic_imports.add(dynamic_import)

        # Get the dynamic imports from children
        for child in self.children:
            dynamic_imports |= child.get_dynamic_imports()

        for prop in self.get_component_props():
            if getattr(self, prop) is not None:
                dynamic_imports |= getattr(self, prop).get_dynamic_imports()

        # Return the dynamic imports
        return dynamic_imports

    def _get_props_imports(self) -> List[str]:
        """Get the imports needed for components props.

        Returns:
            The  imports for the components props of the component.
        """
        return [
            getattr(self, prop).get_imports()
            for prop in self.get_component_props()
            if getattr(self, prop) is not None
        ]

    def _get_dependencies_imports(self) -> imports.ImportDict:
        """Get the imports from lib_dependencies for installing.

        Returns:
            The dependencies imports of the component.
        """
        return {
            dep: [ImportVar(tag=None, render=False)] for dep in self.lib_dependencies
        }

    def _get_hooks_imports(self) -> imports.ImportDict:
        """Get the imports required by certain hooks.

        Returns:
            The imports required for all selected hooks.
        """
        _imports = {}

        if self._get_ref_hook():
            # Handle hooks needed for attaching react refs to DOM nodes.
            _imports.setdefault("react", set()).add(ImportVar(tag="useRef"))
            _imports.setdefault(f"/{Dirs.STATE_PATH}", set()).add(ImportVar(tag="refs"))

        if self._get_mount_lifecycle_hook():
            # Handle hooks for `on_mount` / `on_unmount`.
            _imports.setdefault("react", set()).add(ImportVar(tag="useEffect"))

        if self._get_special_hooks():
            # Handle additional internal hooks (autofocus, etc).
            _imports.setdefault("react", set()).update(
                {
                    ImportVar(tag="useRef"),
                    ImportVar(tag="useEffect"),
                },
            )
        return _imports

    def _get_imports(self) -> imports.ImportDict:
        """Get all the libraries and fields that are used by the component.

        Returns:
            The imports needed by the component.
        """
        _imports = {}

        # Import this component's tag from the main library.
        if self.library is not None and self.tag is not None:
            _imports[self.library] = {self.import_var}

        # Get static imports required for event processing.
        event_imports = Imports.EVENTS if self.event_triggers else {}

        # Collect imports from Vars used directly by this component.
        var_imports = [
            var._var_data.imports for var in self._get_vars() if var._var_data
        ]

        return imports.merge_imports(
            *self._get_props_imports(),
            self._get_dependencies_imports(),
            self._get_hooks_imports(),
            _imports,
            event_imports,
            *var_imports,
        )

    def get_imports(self) -> imports.ImportDict:
        """Get all the libraries and fields that are used by the component and its children.

        Returns:
            The import dict with the required imports.
        """
        return imports.merge_imports(
            self._get_imports(), *[child.get_imports() for child in self.children]
        )

    def _get_mount_lifecycle_hook(self) -> str | None:
        """Generate the component lifecycle hook.

        Returns:
            The useEffect hook for managing `on_mount` and `on_unmount` events.
        """
        # pop on_mount and on_unmount from event_triggers since these are handled by
        # hooks, not as actually props in the component
        on_mount = self.event_triggers.get(EventTriggers.ON_MOUNT, None)
        on_unmount = self.event_triggers.get(EventTriggers.ON_UNMOUNT, None)
        if on_mount is not None:
            on_mount = format.format_event_chain(on_mount)
        if on_unmount is not None:
            on_unmount = format.format_event_chain(on_unmount)
        if on_mount is not None or on_unmount is not None:
            return f"""
                useEffect(() => {{
                    {on_mount or ""}
                    return () => {{
                        {on_unmount or ""}
                    }}
                }}, []);"""

    def _get_ref_hook(self) -> str | None:
        """Generate the ref hook for the component.

        Returns:
            The useRef hook for managing refs.
        """
        ref = self.get_ref()
        if ref is not None:
            return f"const {ref} = useRef(null); {str(Var.create_safe(ref).as_ref())} = {ref};"

    def _get_vars_hooks(self) -> set[str]:
        """Get the hooks required by vars referenced in this component.

        Returns:
            The hooks for the vars.
        """
        vars_hooks = set()
        for var in self._get_vars():
            if var._var_data:
                vars_hooks.update(var._var_data.hooks)
        return vars_hooks

    def _get_events_hooks(self) -> set[str]:
        """Get the hooks required by events referenced in this component.

        Returns:
            The hooks for the events.
        """
        if self.event_triggers:
            return {Hooks.EVENTS}
        return set()

    def _get_special_hooks(self) -> set[str]:
        """Get the hooks required by special actions referenced in this component.

        Returns:
            The hooks for special actions.
        """
        if self.autofocus:
            return {
                """
                // Set focus to the specified element.
                const focusRef = useRef(null)
                useEffect(() => {
                  if (focusRef.current) {
                    focusRef.current.focus();
                  }
                })""",
            }
        return set()

    def _get_hooks_internal(self) -> Set[str]:
        """Get the React hooks for this component managed by the framework.

        Downstream components should NOT override this method to avoid breaking
        framework functionality.

        Returns:
            Set of internally managed hooks.
        """
        return (
            set(
                hook
                for hook in [self._get_mount_lifecycle_hook(), self._get_ref_hook()]
                if hook
            )
            | self._get_vars_hooks()
            | self._get_events_hooks()
            | self._get_special_hooks()
        )

    def _get_hooks(self) -> str | None:
        """Get the React hooks for this component.

        Downstream components should override this method to add their own hooks.

        Returns:
            The hooks for just this component.
        """
        return

    def get_hooks(self) -> Set[str]:
        """Get the React hooks for this component and its children.

        Returns:
            The code that should appear just before returning the rendered component.
        """
        # Store the code in a set to avoid duplicates.
        code = self._get_hooks_internal()

        # Add the hook code for this component.
        hooks = self._get_hooks()
        if hooks is not None:
            code.add(hooks)

        # Add the hook code for the children.
        for child in self.children:
            code |= child.get_hooks()

        return code

    def get_ref(self) -> str | None:
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
        self, seen: set[str] | None = None
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
            # Skip BaseComponent and StatefulComponent children.
            if not isinstance(child, Component):
                continue
            custom_components |= child.get_custom_components(seen=seen)
        return custom_components

    @property
    def import_var(self):
        """The tag to import.

        Returns:
            An import var.
        """
        # If the tag is dot-qualified, only import the left-most name.
        tag = self.tag.partition(".")[0] if self.tag else None
        alias = self.alias.partition(".")[0] if self.alias else None
        return ImportVar(tag=tag, is_default=self.is_default, alias=alias)

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        """Get the app wrap components for the component.

        Returns:
            The app wrap components.
        """
        return {}

    def get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        """Get the app wrap components for the component and its children.

        Returns:
            The app wrap components.
        """
        # Store the components in a set to avoid duplicates.
        components = self._get_app_wrap_components()

        for component in tuple(components.values()):
            components.update(component.get_app_wrap_components())

        # Add the app wrap components for the children.
        for child in self.children:
            # Skip BaseComponent and StatefulComponent children.
            if not isinstance(child, Component):
                continue
            components.update(child.get_app_wrap_components())

        # Return the components.
        return components


class CustomComponent(Component):
    """A custom user-defined component."""

    # Use the components library.
    library = f"/{Dirs.COMPONENTS_PATH}"

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
            # Skip kwargs that are not props.
            if key not in props:
                continue

            # Get the type based on the annotation.
            type_ = props[key]

            # Handle event chains.
            if types._issubclass(type_, EventChain):
                value = self._create_event_chain(key, value)
                self.props[format.to_camel_case(key)] = value
                continue

            # Convert the type to a Var, then get the type of the var.
            if not types._issubclass(type_, Var):
                type_ = Var[type_]
            type_ = types.get_args(type_)[0]

            # Handle subclasses of Base.
            if types._issubclass(type_, Base):
                try:
                    value = BaseVar(
                        _var_name=value.json(), _var_type=type_, _var_is_local=True
                    )
                except Exception:
                    value = Var.create(value)
            else:
                value = Var.create(value, _var_is_string=type(value) is str)

            # Set the prop.
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
        self, seen: set[str] | None = None
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
            custom_components |= self.get_component(self).get_custom_components(
                seen=seen
            )
        return custom_components

    def _render(self) -> Tag:
        """Define how to render the component in React.

        Returns:
            The tag to render.
        """
        return super()._render(props=self.props)

    def get_prop_vars(self) -> List[BaseVar]:
        """Get the prop vars.

        Returns:
            The prop vars.
        """
        return [
            BaseVar(
                _var_name=name,
                _var_type=prop._var_type
                if types._isinstance(prop, Var)
                else type(prop),
            )
            for name, prop in self.props.items()
        ]

    @lru_cache(maxsize=None)  # noqa
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
        # Remove the children from the props.
        props.pop("children", None)
        return CustomComponent(component_fn=component_fn, children=children, **props)

    return wrapper


# Alias memo to custom_component.
memo = custom_component


class NoSSRComponent(Component):
    """A dynamic component that is not rendered on the server."""

    def _get_imports(self) -> imports.ImportDict:
        """Get the imports for the component.

        Returns:
            The imports for dynamically importing the component at module load time.
        """
        # Next.js dynamic import mechanism.
        dynamic_import = {"next/dynamic": [ImportVar(tag="dynamic", is_default=True)]}

        # The normal imports for this component.
        _imports = super()._get_imports()

        # Do NOT import the main library/tag statically.
        if self.library is not None:
            _imports[self.library] = [imports.ImportVar(tag=None, render=False)]

        return imports.merge_imports(
            dynamic_import,
            _imports,
            self._get_dependencies_imports(),
        )

    def _get_dynamic_imports(self) -> str:
        opts_fragment = ", { ssr: false });"

        # extract the correct import name from library name
        if self.library is None:
            raise ValueError("Undefined library for NoSSRComponent")

        import_name_parts = [p for p in self.library.rpartition("@") if p != ""]
        import_name = (
            import_name_parts[0] if import_name_parts[0] != "@" else self.library
        )

        library_import = f"const {self.alias if self.alias else self.tag} = dynamic(() => import('{import_name}')"
        mod_import = (
            # https://nextjs.org/docs/pages/building-your-application/optimizing/lazy-loading#with-named-exports
            f".then((mod) => mod.{self.tag})"
            if not self.is_default
            else ""
        )
        return "".join((library_import, mod_import, opts_fragment))


@serializer
def serialize_component(comp: Component):
    """Serialize a component.

    Args:
        comp: The component to serialize.

    Returns:
        The serialized component.
    """
    return str(comp)


class StatefulComponent(BaseComponent):
    """A component that depends on state and is rendered outside of the page component.

    If a StatefulComponent is used in multiple pages, it will be rendered to a common file and
    imported into each page that uses it.

    A stateful component has a tag name that includes a hash of the code that it renders
    to. This tag name refers to the specific component with the specific props that it
    was created with.
    """

    # A lookup table to caching memoized component instances.
    tag_to_stateful_component: ClassVar[Dict[str, StatefulComponent]] = {}

    # Reference to the original component that was memoized into this component.
    component: Component

    # The rendered (memoized) code that will be emitted.
    code: str

    # How many times this component is referenced in the app.
    references: int = 0

    # Whether the component has already been rendered to a shared file.
    rendered_as_shared: bool = False

    @classmethod
    def create(cls, component: Component) -> StatefulComponent | None:
        """Create a stateful component from a component.

        Args:
            component: The component to memoize.

        Returns:
            The stateful component or None if the component should not be memoized.
        """
        from reflex.components.core.foreach import Foreach

        if component._memoization_mode.disposition == MemoizationDisposition.NEVER:
            # Never memoize this component.
            return None

        if component.tag is None:
            # Only memoize components with a tag.
            return None

        # If _var_data is found in this component, it is a candidate for auto-memoization.
        should_memoize = False

        # If the component requests to be memoized, then ignore other checks.
        if component._memoization_mode.disposition == MemoizationDisposition.ALWAYS:
            should_memoize = True

        if not should_memoize:
            # Determine if any Vars have associated data.
            for prop_var in component._get_vars():
                if prop_var._var_data:
                    should_memoize = True
                    break

        if not should_memoize:
            # Check for special-cases in child components.
            for child in component.children:
                # Skip BaseComponent and StatefulComponent children.
                if not isinstance(child, Component):
                    continue
                # Always consider Foreach something that must be memoized by the parent.
                if isinstance(child, Foreach):
                    should_memoize = True
                    break
                child = cls._child_var(child)
                if isinstance(child, Var) and child._var_data:
                    should_memoize = True
                    break

        if should_memoize or component.event_triggers:
            # Render the component to determine tag+hash based on component code.
            tag_name = cls._get_tag_name(component)
            if tag_name is None:
                return None

            # Look up the tag in the cache
            stateful_component = cls.tag_to_stateful_component.get(tag_name)
            if stateful_component is None:
                # Render the component as a string of javascript code.
                code = cls._render_stateful_code(component, tag_name=tag_name)
                # Set the stateful component in the cache for the given tag.
                stateful_component = cls.tag_to_stateful_component.setdefault(
                    tag_name,
                    cls(
                        children=component.children,
                        component=component,
                        tag=tag_name,
                        code=code,
                    ),
                )
            # Bump the reference count -- multiple pages referencing the same component
            # will result in writing it to a common file.
            stateful_component.references += 1
            return stateful_component

        # Return None to indicate this component should not be memoized.
        return None

    @staticmethod
    def _child_var(child: Component) -> Var | Component:
        """Get the Var from a child component.

        This method is used for special cases when the StatefulComponent should actually
        wrap the parent component of the child instead of recursing into the children
        and memoizing them independently.

        Args:
            child: The child component.

        Returns:
            The Var from the child component or the child itself (for regular cases).
        """
        from reflex.components.base.bare import Bare
        from reflex.components.core.cond import Cond
        from reflex.components.core.foreach import Foreach

        if isinstance(child, Bare):
            return child.contents
        if isinstance(child, Cond):
            return child.cond
        if isinstance(child, Foreach):
            return child.iterable
        return child

    @classmethod
    def _get_tag_name(cls, component: Component) -> str | None:
        """Get the tag based on rendering the given component.

        Args:
            component: The component to render.

        Returns:
            The tag for the stateful component.
        """
        # Get the render dict for the component.
        rendered_code = component.render()
        if not rendered_code:
            # Never memoize non-visual components.
            return None

        # Compute the hash based on the rendered code.
        code_hash = md5(str(rendered_code).encode("utf-8")).hexdigest()

        # Format the tag name including the hash.
        return format.format_state_name(
            f"{component.tag or 'Comp'}_{code_hash}"
        ).capitalize()

    @classmethod
    def _render_stateful_code(
        cls,
        component: Component,
        tag_name: str,
    ) -> str:
        """Render the code for a stateful component.

        Args:
            component: The component to render.
            tag_name: The tag name for the stateful component (see _get_tag_name).

        Returns:
            The rendered code.
        """
        # Memoize event triggers useCallback to avoid unnecessary re-renders.
        memo_event_triggers = tuple(cls._get_memoized_event_triggers(component).items())

        # Trigger hooks stored separately to write after the normal hooks (see stateful_component.js.jinja2)
        memo_trigger_hooks = []

        if memo_event_triggers:
            # Copy the component to avoid mutating the original.
            component = copy.copy(component)

            for event_trigger, (
                memo_trigger,
                memo_trigger_hook,
            ) in memo_event_triggers:
                # Replace the event trigger with the memoized version.
                memo_trigger_hooks.append(memo_trigger_hook)
                component.event_triggers[event_trigger] = memo_trigger

        # Render the code for this component and hooks.
        return STATEFUL_COMPONENT.render(
            tag_name=tag_name,
            memo_trigger_hooks=memo_trigger_hooks,
            component=component,
        )

    @staticmethod
    def _get_hook_deps(hook: str) -> list[str]:
        """Extract var deps from a hook.

        Args:
            hook: The hook line to extract deps from.

        Returns:
            A list of var names created by the hook declaration.
        """
        var_name = hook.partition("=")[0].strip().split(None, 1)[1].strip()
        if var_name.startswith("["):
            # Break up array destructuring.
            return [v.strip() for v in var_name.strip("[]").split(",")]
        return [var_name]

    @classmethod
    def _get_memoized_event_triggers(
        cls,
        component: Component,
    ) -> dict[str, tuple[Var, str]]:
        """Memoize event handler functions with useCallback to avoid unnecessary re-renders.

        Args:
            component: The component with events to memoize.

        Returns:
            A dict of event trigger name to a tuple of the memoized event trigger Var and
            the hook code that memoizes the event handler.
        """
        trigger_memo = {}
        for event_trigger, event_args in component._get_vars_from_event_triggers(
            component.event_triggers
        ):
            if event_trigger in {
                EventTriggers.ON_MOUNT,
                EventTriggers.ON_UNMOUNT,
                EventTriggers.ON_SUBMIT,
            }:
                # Do not memoize lifecycle or submit events.
                continue

            # Get the actual EventSpec and render it.
            event = component.event_triggers[event_trigger]
            rendered_chain = format.format_prop(event)
            if isinstance(rendered_chain, str):
                rendered_chain = rendered_chain.strip("{}")

            # Hash the rendered EventChain to get a deterministic function name.
            chain_hash = md5(str(rendered_chain).encode("utf-8")).hexdigest()
            memo_name = f"{event_trigger}_{chain_hash}"

            # Calculate Var dependencies accessed by the handler for useCallback dep array.
            var_deps = ["addEvents", "Event"]
            for arg in event_args:
                if arg._var_data is None:
                    continue
                for hook in arg._var_data.hooks:
                    var_deps.extend(cls._get_hook_deps(hook))
            memo_var_data = VarData.merge(
                *[var._var_data for var in event_args],
                VarData(  # type: ignore
                    imports={"react": {ImportVar(tag="useCallback")}},
                ),
            )

            # Store the memoized function name and hook code for this event trigger.
            trigger_memo[event_trigger] = (
                Var.create_safe(memo_name)._replace(
                    _var_type=EventChain, merge_var_data=memo_var_data
                ),
                f"const {memo_name} = useCallback({rendered_chain}, [{', '.join(var_deps)}])",
            )
        return trigger_memo

    def get_hooks(self) -> set[str]:
        """Get the React hooks for this component.

        Returns:
            The code that should appear just before returning the rendered component.
        """
        return set()

    def get_imports(self) -> imports.ImportDict:
        """Get all the libraries and fields that are used by the component.

        Returns:
            The import dict with the required imports.
        """
        if self.rendered_as_shared:
            return {
                f"/{Dirs.UTILS}/{PageNames.STATEFUL_COMPONENTS}": [
                    ImportVar(tag=self.tag)
                ]
            }
        return self.component.get_imports()

    def get_dynamic_imports(self) -> set[str]:
        """Get dynamic imports for the component.

        Returns:
            The dynamic imports.
        """
        if self.rendered_as_shared:
            return set()
        return self.component.get_dynamic_imports()

    def get_custom_code(self) -> set[str]:
        """Get custom code for the component.

        Returns:
            The custom code.
        """
        if self.rendered_as_shared:
            return set()
        return self.component.get_custom_code().union({self.code})

    def get_refs(self) -> set[str]:
        """Get the refs for the children of the component.

        Returns:
            The refs for the children.
        """
        if self.rendered_as_shared:
            return set()
        return self.component.get_refs()

    def render(self) -> dict:
        """Define how to render the component in React.

        Returns:
            The tag to render.
        """
        return dict(Tag(name=self.tag))

    @classmethod
    def compile_from(cls, component: BaseComponent) -> BaseComponent:
        """Walk through the component tree and memoize all stateful components.

        Args:
            component: The component to memoize.

        Returns:
            The memoized component tree.
        """
        if isinstance(component, Component):
            if component._memoization_mode.recursive:
                # Recursively memoize stateful children (default).
                component.children = [
                    cls.compile_from(child) for child in component.children
                ]
            # Memoize this component if it depends on state.
            stateful_component = cls.create(component)
            if stateful_component is not None:
                return stateful_component
        return component


class MemoizationLeaf(Component):
    """A component that does not separately memoize its children.

    Any component which depends on finding the exact names of children
    components within it, should be a memoization leaf so the compiler
    does not replace the provided child tags with memoized tags.

    During creation, a memoization leaf will mark itself as wanting to be
    memoized if any of its children return any hooks.
    """

    _memoization_mode = MemoizationMode(recursive=False)

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a new memoization leaf component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The memoization leaf
        """
        comp = super().create(*children, **props)
        if comp.get_hooks():
            comp._memoization_mode = cls._memoization_mode.copy(
                update={"disposition": MemoizationDisposition.ALWAYS}
            )
        return comp
