"""Base component definitions."""

from __future__ import annotations

import copy
import dataclasses
import inspect
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
    Sequence,
    Set,
    Type,
    Union,
    get_args,
    get_origin,
)

from typing_extensions import Self

import reflex.state
from reflex.base import Base
from reflex.compiler.templates import STATEFUL_COMPONENT
from reflex.components.core.breakpoints import Breakpoints
from reflex.components.dynamic import load_dynamic_serializer
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
from reflex.constants.compiler import SpecialAttributes
from reflex.constants.state import FRONTEND_EVENT_STATE
from reflex.event import (
    EventActionsMixin,
    EventCallback,
    EventChain,
    EventHandler,
    EventSpec,
    no_args_event_spec,
)
from reflex.style import Style, format_as_emotion
from reflex.utils import format, imports, types
from reflex.utils.imports import ImportDict, ImportVar, ParsedImportDict, parse_imports
from reflex.vars import VarData
from reflex.vars.base import (
    CachedVarOperation,
    LiteralVar,
    Var,
    cached_property_no_lock,
)
from reflex.vars.function import ArgsFunctionOperation, FunctionStringVar
from reflex.vars.number import ternary_operation
from reflex.vars.object import ObjectVar
from reflex.vars.sequence import LiteralArrayVar


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

    # List here the dependencies that need to be transpiled by Next.js
    transpile_packages: List[str] = []

    # The tag to use when rendering the component.
    tag: Optional[str] = None

    @abstractmethod
    def render(self) -> dict:
        """Render the component.

        Returns:
            The dictionary for template of the component.
        """

    @abstractmethod
    def _get_all_hooks_internal(self) -> dict[str, VarData | None]:
        """Get the reflex internal hooks for the component and its children.

        Returns:
            The code that should appear just before user-defined hooks.
        """

    @abstractmethod
    def _get_all_hooks(self) -> dict[str, VarData | None]:
        """Get the React hooks for this component.

        Returns:
            The code that should appear just before returning the rendered component.
        """

    @abstractmethod
    def _get_all_imports(self) -> ParsedImportDict:
        """Get all the libraries and fields that are used by the component.

        Returns:
            The import dict with the required imports.
        """

    @abstractmethod
    def _get_all_dynamic_imports(self) -> set[str]:
        """Get dynamic imports for the component.

        Returns:
            The dynamic imports.
        """

    @abstractmethod
    def _get_all_custom_code(self) -> set[str]:
        """Get custom code for the component.

        Returns:
            The custom code.
        """

    @abstractmethod
    def _get_all_refs(self) -> set[str]:
        """Get the refs for the children of the component.

        Returns:
            The refs for the children.
        """


class ComponentNamespace(SimpleNamespace):
    """A namespace to manage components with subcomponents."""

    def __hash__(self) -> int:  # pyright: ignore [reportIncompatibleVariableOverride]
        """Get the hash of the namespace.

        Returns:
            The hash of the namespace.
        """
        return hash(type(self).__name__)


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
ComponentChildTypes = (*types.PrimitiveTypes, Var, BaseComponent)


def satisfies_type_hint(obj: Any, type_hint: Any) -> bool:
    """Check if an object satisfies a type hint.

    Args:
        obj: The object to check.
        type_hint: The type hint to check against.

    Returns:
        Whether the object satisfies the type hint.
    """
    return types._isinstance(obj, type_hint, nested=1)


def _components_from(
    component_or_var: Union[BaseComponent, Var],
) -> tuple[BaseComponent, ...]:
    """Get the components from a component or Var.

    Args:
        component_or_var: The component or Var to get the components from.

    Returns:
        The components.
    """
    if isinstance(component_or_var, Var):
        var_data = component_or_var._get_all_var_data()
        return var_data.components if var_data else ()
    if isinstance(component_or_var, BaseComponent):
        return (component_or_var,)
    return ()


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
    special_props: List[Var] = []

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
    custom_attrs: Dict[str, Union[Var, Any]] = {}

    # When to memoize this component and its children.
    _memoization_mode: MemoizationMode = MemoizationMode()

    # State class associated with this component instance
    State: Optional[Type[reflex.state.State]] = None

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the component.

        This method should be implemented by subclasses to add new imports for the component.

        Implementations do NOT need to call super(). The result of calling
        add_imports in each parent class will be merged internally.

        Returns:
            The additional imports for this component subclass.

        The format of the return value is a dictionary where the keys are the
        library names (with optional npm-style version specifications) mapping
        to a single name to be imported, or a list names to be imported.

        For advanced use cases, the values can be ImportVar instances (for
        example, to provide an alias or mark that an import is the default
        export from the given library).

        ```python
        return {
            "react": "useEffect",
            "react-draggable": ["DraggableCore", rx.ImportVar(tag="Draggable", is_default=True)],
        }
        ```
        """
        return {}

    def add_hooks(self) -> list[str | Var]:
        """Add hooks inside the component function.

        Hooks are pieces of literal Javascript code that is inserted inside the
        React component function.

        Each logical hook should be a separate string in the list.

        Common strings will be deduplicated and inserted into the component
        function only once, so define const variables and other identical code
        in their own strings to avoid defining the same const or hook multiple
        times.

        If a hook depends on specific data from the component instance, be sure
        to use unique values inside the string to _avoid_ deduplication.

        Implementations do NOT need to call super(). The result of calling
        add_hooks in each parent class will be merged and deduplicated internally.

        Returns:
            The additional hooks for this component subclass.

        ```python
        return [
            "const [count, setCount] = useState(0);",
            "useEffect(() => { setCount((prev) => prev + 1); console.log(`mounted ${count} times`); }, []);",
        ]
        ```
        """
        return []

    def add_custom_code(self) -> list[str]:
        """Add custom Javascript code into the page that contains this component.

        Custom code is inserted at module level, after any imports.

        Each string of custom code is deduplicated per-page, so take care to
        avoid defining the same const or function differently from different
        component instances.

        Custom code is useful for defining global functions or constants which
        can then be referenced inside hooks or used by component vars.

        Implementations do NOT need to call super(). The result of calling
        add_custom_code in each parent class will be merged and deduplicated internally.

        Returns:
            The additional custom code for this component subclass.

        ```python
        return [
            "const translatePoints = (event) => { return { x: event.clientX, y: event.clientY }; };",
        ]
        ```
        """
        return []

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
                if field.default is not None:
                    field.default = LiteralVar.create(field.default)
            elif types._issubclass(field.type_, EventHandler):
                field.required = False

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
            ValueError: If an event trigger passed is not valid.
        """
        # Set the id and children initially.
        children = kwargs.get("children", [])
        initial_kwargs = {
            "id": kwargs.get("id"),
            "children": children,
            **{
                prop: LiteralVar.create(kwargs[prop])
                for prop in self.get_initial_props()
                if prop in kwargs
            },
        }
        super().__init__(**initial_kwargs)

        self._validate_component_children(children)

        # Get the component fields, triggers, and props.
        fields = self.get_fields()
        component_specific_triggers = self.get_event_triggers()
        props = self.get_props()

        # Add any events triggers.
        if "event_triggers" not in kwargs:
            kwargs["event_triggers"] = {}
        kwargs["event_triggers"] = kwargs["event_triggers"].copy()

        # Iterate through the kwargs and set the props.
        for key, value in kwargs.items():
            if (
                key.startswith("on_")
                and key not in component_specific_triggers
                and key not in props
            ):
                raise ValueError(
                    f"The {(comp_name := type(self).__name__)} does not take in an `{key}` event trigger. If {comp_name}"
                    f" is a third party component make sure to add `{key}` to the component's event triggers. "
                    f"visit https://reflex.dev/docs/wrapping-react/guide/#event-triggers for more info."
                )
            if key in component_specific_triggers:
                # Event triggers are bound to event chains.
                field_type = EventChain
            elif key in props:
                # Set the field type.
                field_type = fields[key].type_

            else:
                continue

            def determine_key(value: Any):
                # Try to create a var from the value
                key = value if isinstance(value, Var) else LiteralVar.create(value)

                # Check that the var type is not None.
                if key is None:
                    raise TypeError

                return key

            # Check whether the key is a component prop.
            if types._issubclass(field_type, Var):
                # Used to store the passed types if var type is a union.
                passed_types = None
                try:
                    kwargs[key] = determine_key(value)

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
                if types.is_union(passed_type):
                    # We need to check all possible types in the union.
                    passed_types = (
                        arg for arg in passed_type.__args__ if arg is not type(None)
                    )
                if (
                    # If the passed var is a union, check if all possible types are valid.
                    passed_types
                    and not all(
                        types._issubclass(pt, expected_type) for pt in passed_types
                    )
                ) or (
                    # Else just check if the passed var type is valid.
                    not passed_types and not satisfies_type_hint(value, expected_type)
                ):
                    value_name = value._js_expr if isinstance(value, Var) else value

                    additional_info = (
                        " You can call `.bool()` on the value to convert it to a boolean."
                        if expected_type is bool and isinstance(value, Var)
                        else ""
                    )

                    raise TypeError(
                        f"Invalid var passed for prop {type(self).__name__}.{key}, expected type {expected_type}, got value {value_name} of type {passed_type}."
                        + additional_info
                    )
            # Check if the key is an event trigger.
            if key in component_specific_triggers:
                kwargs["event_triggers"][key] = EventChain.create(
                    value=value,
                    args_spec=component_specific_triggers[key],
                    key=key,
                )

        # Remove any keys that were added as events.
        for key in kwargs["event_triggers"]:
            kwargs.pop(key, None)

        # Place data_ and aria_ attributes into custom_attrs
        special_attributes = tuple(
            key
            for key in kwargs
            if key not in fields and SpecialAttributes.is_special(key)
        )
        if special_attributes:
            custom_attrs = kwargs.setdefault("custom_attrs", {})
            for key in special_attributes:
                custom_attrs[format.to_kebab_case(key)] = kwargs.pop(key)

        # Add style props to the component.
        style = kwargs.get("style", {})
        if isinstance(style, List):
            # Merge styles, the later ones overriding keys in the earlier ones.
            style = {k: v for style_dict in style for k, v in style_dict.items()}

        if isinstance(style, (Breakpoints, Var)):
            style = {
                # Assign the Breakpoints to the self-referential selector to avoid squashing down to a regular dict.
                "&": style,
            }

        kwargs["style"] = Style(
            {
                **self.get_fields()["style"].default,
                **style,
                **{attr: value for attr, value in kwargs.items() if attr not in fields},
            }
        )

        # Convert class_name to str if it's list
        class_name = kwargs.get("class_name", "")
        if isinstance(class_name, (List, tuple)):
            if any(isinstance(c, Var) for c in class_name):
                kwargs["class_name"] = LiteralArrayVar.create(
                    class_name, _var_type=List[str]
                ).join(" ")
            else:
                kwargs["class_name"] = " ".join(class_name)

        # Construct the component.
        super().__init__(*args, **kwargs)

    def get_event_triggers(
        self,
    ) -> Dict[str, types.ArgsSpec | Sequence[types.ArgsSpec]]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        default_triggers: Dict[str, types.ArgsSpec | Sequence[types.ArgsSpec]] = {
            EventTriggers.ON_FOCUS: no_args_event_spec,
            EventTriggers.ON_BLUR: no_args_event_spec,
            EventTriggers.ON_CLICK: no_args_event_spec,
            EventTriggers.ON_CONTEXT_MENU: no_args_event_spec,
            EventTriggers.ON_DOUBLE_CLICK: no_args_event_spec,
            EventTriggers.ON_MOUSE_DOWN: no_args_event_spec,
            EventTriggers.ON_MOUSE_ENTER: no_args_event_spec,
            EventTriggers.ON_MOUSE_LEAVE: no_args_event_spec,
            EventTriggers.ON_MOUSE_MOVE: no_args_event_spec,
            EventTriggers.ON_MOUSE_OUT: no_args_event_spec,
            EventTriggers.ON_MOUSE_OVER: no_args_event_spec,
            EventTriggers.ON_MOUSE_UP: no_args_event_spec,
            EventTriggers.ON_SCROLL: no_args_event_spec,
            EventTriggers.ON_MOUNT: no_args_event_spec,
            EventTriggers.ON_UNMOUNT: no_args_event_spec,
        }

        # Look for component specific triggers,
        # e.g. variable declared as EventHandler types.
        for field in self.get_fields().values():
            if types._issubclass(field.outer_type_, EventHandler):
                args_spec = None
                annotation = field.annotation
                if (metadata := getattr(annotation, "__metadata__", None)) is not None:
                    args_spec = metadata[0]
                default_triggers[field.name] = args_spec or (no_args_event_spec)
        return default_triggers

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
            name=(self.tag if not self.alias else self.alias) or "",
            special_props=self.special_props,
        )

        if props is None:
            # Add component props to the tag.
            props = {
                attr.removesuffix("_"): getattr(self, attr) for attr in self.get_props()
            }

            # Add ref to element if `id` is not None.
            ref = self.get_ref()
            if ref is not None:
                props["ref"] = Var(_js_expr=ref)
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
    def _are_fields_known(cls) -> bool:
        """Check if all fields are known at compile time. True for most components.

        Returns:
            Whether all fields are known at compile time.
        """
        return True

    @classmethod
    @lru_cache(maxsize=None)
    def _get_component_prop_names(cls) -> Set[str]:
        """Get the names of the component props. NOTE: This assumes all fields are known.

        Returns:
            The names of the component props.
        """
        return {
            name
            for name, field in cls.get_fields().items()
            if name in cls.get_props()
            and types._issubclass(field.outer_type_, Component)
        }

    def _get_components_in_props(self) -> Sequence[BaseComponent]:
        """Get the components in the props.

        Returns:
            The components in the props
        """
        if self._are_fields_known():
            return [
                component
                for name in self._get_component_prop_names()
                for component in _components_from(getattr(self, name))
            ]
        return [
            component
            for prop in self.get_props()
            if (value := getattr(self, prop)) is not None
            and isinstance(value, (BaseComponent, Var))
            for component in _components_from(value)
        ]

    @classmethod
    def create(cls, *children, **props) -> Self:
        """Create the component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.
        """
        # Import here to avoid circular imports.
        from reflex.components.base.bare import Bare
        from reflex.components.base.fragment import Fragment
        from reflex.utils.exceptions import ChildrenTypeError

        # Filter out None props
        props = {key: value for key, value in props.items() if value is not None}

        def validate_children(children: tuple | list):
            for child in children:
                if isinstance(child, (tuple, list)):
                    validate_children(child)

                # Make sure the child is a valid type.
                if isinstance(child, dict) or not isinstance(
                    child, ComponentChildTypes
                ):
                    raise ChildrenTypeError(component=cls.__name__, child=child)

        # Validate all the children.
        validate_children(children)

        children = [
            (
                child
                if isinstance(child, Component)
                else (
                    Fragment.create(*child)
                    if isinstance(child, tuple)
                    else Bare.create(contents=LiteralVar.create(child))
                )
            )
            for child in children
        ]

        return cls(children=children, **props)

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Downstream components can override this method to return a style dict
        that will be applied to the component.

        Returns:
            The style to add.
        """
        return None

    def _add_style(self) -> Style:
        """Call add_style for all bases in the MRO.

        Downstream components should NOT override. Use add_style instead.

        Returns:
            The style to add.
        """
        styles = []

        # Walk the MRO to call all `add_style` methods.
        for base in self._iter_parent_classes_with_method("add_style"):
            s = base.add_style(self)
            if s is not None:
                styles.append(s)

        _style = Style()
        for s in reversed(styles):
            _style.update(s)
        return _style

    def _get_component_style(self, styles: ComponentStyle) -> Style | None:
        """Get the style to the component from `App.style`.

        Args:
            styles: The style to apply.

        Returns:
            The style of the component.
        """
        component_style = None
        if type(self) in styles:
            component_style = Style(styles[type(self)])
        if self.create in styles:
            component_style = Style(styles[self.create])
        return component_style

    def _add_style_recursive(
        self, style: ComponentStyle, theme: Optional[Component] = None
    ) -> Component:
        """Add additional style to the component and its children.

        Apply order is as follows (with the latest overriding the earliest):
        1. Default style from `_add_style`/`add_style`.
        2. User-defined style from `App.style`.
        3. User-defined style from `Component.style`.
        4. style dict and css props passed to the component instance.

        Args:
            style: A dict from component to styling.
            theme: The theme to apply. (for retro-compatibility with deprecated _apply_theme API)

        Raises:
            UserWarning: If `_add_style` has been overridden.

        Returns:
            The component with the additional style.
        """
        # 1. Default style from `_add_style`/`add_style`.
        if type(self)._add_style != Component._add_style:
            raise UserWarning(
                "Do not override _add_style directly. Use add_style instead."
            )
        new_style = self._add_style()
        style_vars = [new_style._var_data]

        # 2. User-defined style from `App.style`.
        component_style = self._get_component_style(style)
        if component_style:
            new_style.update(component_style)
            style_vars.append(component_style._var_data)

        # 4. style dict and css props passed to the component instance.
        new_style.update(self.style)
        style_vars.append(self.style._var_data)

        new_style._var_data = VarData.merge(*style_vars)

        # Assign the new style
        self.style = new_style

        # Recursively add style to the children.
        for child in self.children:
            # Skip BaseComponent and StatefulComponent children.
            if not isinstance(child, Component):
                continue
            child._add_style_recursive(style, theme)
        return self

    def _get_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        if isinstance(self.style, Var):
            return {"css": self.style}
        emotion_style = format_as_emotion(self.style)
        return (
            {"css": LiteralVar.create(emotion_style)}
            if emotion_style is not None
            else {}
        )

    def render(self) -> dict:
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

    def _replace_prop_names(self, rendered_dict: dict) -> None:
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

        def validate_child(child: Any):
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

            if child._valid_parents and all(
                clz_name not in [*child._valid_parents, *allowed_components]
                for clz_name in self._iter_parent_classes_names()
            ):
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
                    if isinstance(spec, EventSpec):
                        for args in spec.args:
                            event_args.extend(args)
                    else:
                        event_args.append(spec)
                yield event_trigger, event_args

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in this component.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component (props, styles, event handlers).
        """
        ignore_ids = ignore_ids or set()
        vars: List[Var] | None = getattr(self, "__vars", None)
        if vars is not None:
            yield from vars
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
        if (isinstance(self.style, dict) and self.style) or isinstance(self.style, Var):
            vars.append(
                Var(
                    _js_expr="style",
                    _var_type=str,
                    _var_data=VarData.merge(self.style._var_data),
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
                var = LiteralVar.create(comp_prop)
                if var._get_all_var_data() is not None:
                    vars.append(var)

        # Get Vars associated with children.
        if include_children:
            for child in self.children:
                if not isinstance(child, Component) or id(child) in ignore_ids:
                    continue
                ignore_ids.add(id(child))
                child_vars = child._get_vars(
                    include_children=include_children, ignore_ids=ignore_ids
                )
                vars.extend(child_vars)

        yield from vars

    def _event_trigger_values_use_state(self) -> bool:
        """Check if the values of a component's event trigger use state.

        Returns:
            True if any of the component's event trigger values uses State.
        """
        for trigger in self.event_triggers.values():
            if isinstance(trigger, EventChain):
                for event in trigger.events:
                    if isinstance(event, EventCallback):
                        continue
                    if isinstance(event, EventSpec):
                        if (
                            event.handler.state_full_name
                            and event.handler.state_full_name != FRONTEND_EVENT_STATE
                        ):
                            return True
                    else:
                        if event._var_state:
                            return True
            elif isinstance(trigger, Var) and trigger._var_state:
                return True
        return False

    def _has_stateful_event_triggers(self):
        """Check if component or children have any event triggers that use state.

        Returns:
            True if the component or children have any event triggers that uses state.
        """
        if self.event_triggers and self._event_trigger_values_use_state():
            return True
        else:
            for child in self.children:
                if (
                    isinstance(child, Component)
                    and child._has_stateful_event_triggers()
                ):
                    return True
        return False

    @classmethod
    def _iter_parent_classes_names(cls) -> Iterator[str]:
        for clz in cls.mro():
            if clz is Component:
                break
            yield clz.__name__

    @classmethod
    def _iter_parent_classes_with_method(cls, method: str) -> Iterator[Type[Component]]:
        """Iterate through parent classes that define a given method.

        Used for handling the `add_*` API functions that internally simulate a super() call chain.

        Args:
            method: The method to look for.

        Yields:
            The parent classes that define the method (differently than the base).
        """
        seen_methods = {getattr(Component, method)}
        for clz in cls.mro():
            if clz is Component:
                break
            if not issubclass(clz, Component):
                continue
            method_func = getattr(clz, method, None)
            if not callable(method_func) or method_func in seen_methods:
                continue
            seen_methods.add(method_func)
            yield clz

    def _get_custom_code(self) -> str | None:
        """Get custom code for the component.

        Returns:
            The custom code.
        """
        return None

    def _get_all_custom_code(self) -> set[str]:
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

        for component in self._get_components_in_props():
            code |= component._get_all_custom_code()

        # Add the custom code from add_custom_code method.
        for clz in self._iter_parent_classes_with_method("add_custom_code"):
            for item in clz.add_custom_code(self):
                code.add(item)

        # Add the custom code for the children.
        for child in self.children:
            code |= child._get_all_custom_code()

        # Return the code.
        return code

    def _get_dynamic_imports(self) -> str | None:
        """Get dynamic import for the component.

        Returns:
            The dynamic import.
        """
        return None

    def _get_all_dynamic_imports(self) -> Set[str]:
        """Get dynamic imports for the component and its children.

        Returns:
            The dynamic imports.
        """
        # Store the import in a set to avoid duplicates.
        dynamic_imports: set[str] = set()

        # Get dynamic import for this component.
        dynamic_import = self._get_dynamic_imports()
        if dynamic_import:
            dynamic_imports.add(dynamic_import)

        # Get the dynamic imports from children
        for child in self.children:
            dynamic_imports |= child._get_all_dynamic_imports()

        for component in self._get_components_in_props():
            dynamic_imports |= component._get_all_dynamic_imports()

        # Return the dynamic imports
        return dynamic_imports

    def _should_transpile(self, dep: str | None) -> bool:
        """Check if a dependency should be transpiled.

        Args:
            dep: The dependency to check.

        Returns:
            True if the dependency should be transpiled.
        """
        return bool(self.transpile_packages) and (
            dep in self.transpile_packages
            or format.format_library_name(dep or "") in self.transpile_packages
        )

    def _get_dependencies_imports(self) -> ParsedImportDict:
        """Get the imports from lib_dependencies for installing.

        Returns:
            The dependencies imports of the component.
        """
        return {
            dep: [
                ImportVar(
                    tag=None,
                    render=False,
                    transpile=self._should_transpile(dep),
                )
            ]
            for dep in self.lib_dependencies
        }

    def _get_hooks_imports(self) -> ParsedImportDict:
        """Get the imports required by certain hooks.

        Returns:
            The imports required for all selected hooks.
        """
        _imports = {}

        if self._get_ref_hook() is not None:
            # Handle hooks needed for attaching react refs to DOM nodes.
            _imports.setdefault("react", set()).add(ImportVar(tag="useRef"))
            _imports.setdefault(f"$/{Dirs.STATE_PATH}", set()).add(
                ImportVar(tag="refs")
            )

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

        other_imports = []
        user_hooks = self._get_hooks()
        user_hooks_data = (
            VarData.merge(user_hooks._get_all_var_data())
            if user_hooks is not None and isinstance(user_hooks, Var)
            else None
        )
        if user_hooks_data is not None:
            other_imports.append(user_hooks_data.imports)
        other_imports.extend(
            hook_vardata.imports
            for hook_vardata in self._get_added_hooks().values()
            if hook_vardata is not None
        )

        return imports.merge_imports(_imports, *other_imports)

    def _get_imports(self) -> ParsedImportDict:
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
            var_data.imports
            for var in self._get_vars()
            if (var_data := var._get_all_var_data()) is not None
        ]

        added_import_dicts: list[ParsedImportDict] = []
        for clz in self._iter_parent_classes_with_method("add_imports"):
            list_of_import_dict = clz.add_imports(self)

            if not isinstance(list_of_import_dict, list):
                list_of_import_dict = [list_of_import_dict]

            added_import_dicts.extend(
                [parse_imports(import_dict) for import_dict in list_of_import_dict]
            )

        return imports.merge_imports(
            self._get_dependencies_imports(),
            self._get_hooks_imports(),
            _imports,
            event_imports,
            *var_imports,
            *added_import_dicts,
        )

    def _get_all_imports(self, collapse: bool = False) -> ParsedImportDict:
        """Get all the libraries and fields that are used by the component and its children.

        Args:
            collapse: Whether to collapse the imports by removing duplicates.

        Returns:
            The import dict with the required imports.
        """
        _imports = imports.merge_imports(
            self._get_imports(), *[child._get_all_imports() for child in self.children]
        )
        return imports.collapse_imports(_imports) if collapse else _imports

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
            on_mount = str(LiteralVar.create(on_mount)) + "()"
        if on_unmount is not None:
            on_unmount = str(LiteralVar.create(on_unmount)) + "()"
        if on_mount is not None or on_unmount is not None:
            return f"""
                useEffect(() => {{
                    {on_mount or ""}
                    return () => {{
                        {on_unmount or ""}
                    }}
                }}, []);"""

    def _get_ref_hook(self) -> Var | None:
        """Generate the ref hook for the component.

        Returns:
            The useRef hook for managing refs.
        """
        ref = self.get_ref()
        if ref is not None:
            return Var(
                f"const {ref} = useRef(null); {Var(_js_expr=ref)._as_ref()!s} = {ref};",
                _var_data=VarData(position=Hooks.HookPosition.INTERNAL),
            )

    def _get_vars_hooks(self) -> dict[str, VarData | None]:
        """Get the hooks required by vars referenced in this component.

        Returns:
            The hooks for the vars.
        """
        vars_hooks = {}
        for var in self._get_vars():
            var_data = var._get_all_var_data()
            if var_data is not None:
                vars_hooks.update(
                    var_data.hooks
                    if isinstance(var_data.hooks, dict)
                    else {
                        k: VarData(position=Hooks.HookPosition.INTERNAL)
                        for k in var_data.hooks
                    }
                )
                for component in var_data.components:
                    vars_hooks.update(component._get_all_hooks())
        return vars_hooks

    def _get_events_hooks(self) -> dict[str, VarData | None]:
        """Get the hooks required by events referenced in this component.

        Returns:
            The hooks for the events.
        """
        return (
            {Hooks.EVENTS: VarData(position=Hooks.HookPosition.INTERNAL)}
            if self.event_triggers
            else {}
        )

    def _get_special_hooks(self) -> dict[str, VarData | None]:
        """Get the hooks required by special actions referenced in this component.

        Returns:
            The hooks for special actions.
        """
        return (
            {Hooks.AUTOFOCUS: VarData(position=Hooks.HookPosition.INTERNAL)}
            if self.autofocus
            else {}
        )

    def _get_hooks_internal(self) -> dict[str, VarData | None]:
        """Get the React hooks for this component managed by the framework.

        Downstream components should NOT override this method to avoid breaking
        framework functionality.

        Returns:
            The internally managed hooks.
        """
        return {
            **{
                str(hook): VarData(position=Hooks.HookPosition.INTERNAL)
                for hook in [self._get_ref_hook(), self._get_mount_lifecycle_hook()]
                if hook is not None
            },
            **self._get_vars_hooks(),
            **self._get_events_hooks(),
            **self._get_special_hooks(),
        }

    def _get_added_hooks(self) -> dict[str, VarData | None]:
        """Get the hooks added via `add_hooks` method.

        Returns:
            The deduplicated hooks and imports added by the component and parent components.
        """
        code = {}

        def extract_var_hooks(hook: Var):
            var_data = VarData.merge(hook._get_all_var_data())
            if var_data is not None:
                for sub_hook in var_data.hooks:
                    code[sub_hook] = None

            if str(hook) in code:
                code[str(hook)] = VarData.merge(var_data, code[str(hook)])
            else:
                code[str(hook)] = var_data

        # Add the hook code from add_hooks for each parent class (this is reversed to preserve
        # the order of the hooks in the final output)
        for clz in reversed(tuple(self._iter_parent_classes_with_method("add_hooks"))):
            for hook in clz.add_hooks(self):
                if isinstance(hook, Var):
                    extract_var_hooks(hook)
                else:
                    code[hook] = None

        return code

    def _get_hooks(self) -> str | None:
        """Get the React hooks for this component.

        Downstream components should override this method to add their own hooks.

        Returns:
            The hooks for just this component.
        """
        return

    def _get_all_hooks_internal(self) -> dict[str, VarData | None]:
        """Get the reflex internal hooks for the component and its children.

        Returns:
            The code that should appear just before user-defined hooks.
        """
        # Store the code in a set to avoid duplicates.
        code = self._get_hooks_internal()

        # Add the hook code for the children.
        for child in self.children:
            code = {**code, **child._get_all_hooks_internal()}

        return code

    def _get_all_hooks(self) -> dict[str, VarData | None]:
        """Get the React hooks for this component and its children.

        Returns:
            The code that should appear just before returning the rendered component.
        """
        code = {}

        # Add the internal hooks for this component.
        code.update(self._get_hooks_internal())

        # Add the hook code for this component.
        hooks = self._get_hooks()
        if hooks is not None:
            code[hooks] = None

        code.update(self._get_added_hooks())

        # Add the hook code for the children.
        for child in self.children:
            code = {**code, **child._get_all_hooks()}

        return code

    def get_ref(self) -> str | None:
        """Get the name of the ref for the component.

        Returns:
            The ref name.
        """
        # do not create a ref if the id is dynamic or unspecified
        if self.id is None or isinstance(self.id, Var):
            return None
        return format.format_ref(self.id)

    def _get_all_refs(self) -> set[str]:
        """Get the refs for the children of the component.

        Returns:
            The refs for the children.
        """
        refs = set()
        ref = self.get_ref()
        if ref is not None:
            refs.add(ref)
        for child in self.children:
            refs |= child._get_all_refs()
        for component in self._get_components_in_props():
            refs |= component._get_all_refs()

        return refs

    def _get_all_custom_components(
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
            custom_components |= child._get_all_custom_components(seen=seen)
        for component in self._get_components_in_props():
            if isinstance(component, Component) and component.tag is not None:
                custom_components |= component._get_all_custom_components(seen=seen)
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
        return ImportVar(
            tag=tag,
            is_default=self.is_default,
            alias=alias,
            transpile=self._should_transpile(self.library),
        )

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        """Get the app wrap components for the component.

        Returns:
            The app wrap components.
        """
        return {}

    def _get_all_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        """Get the app wrap components for the component and its children.

        Returns:
            The app wrap components.
        """
        # Store the components in a set to avoid duplicates.
        components = self._get_app_wrap_components()

        for component in tuple(components.values()):
            components.update(component._get_all_app_wrap_components())

        # Add the app wrap components for the children.
        for child in self.children:
            # Skip BaseComponent and StatefulComponent children.
            if not isinstance(child, Component):
                continue
            components.update(child._get_all_app_wrap_components())

        # Return the components.
        return components


class CustomComponent(Component):
    """A custom user-defined component."""

    # Use the components library.
    library = f"$/{Dirs.COMPONENTS_PATH}"

    # The function that creates the component.
    component_fn: Callable[..., Component] = Component.create

    # The props of the component.
    props: Dict[str, Any] = {}

    def __init__(self, **kwargs):
        """Initialize the custom component.

        Args:
            **kwargs: The kwargs to pass to the component.
        """
        component_fn = kwargs.get("component_fn")

        # Set the props.
        props_types = typing.get_type_hints(component_fn) if component_fn else {}
        props = {key: value for key, value in kwargs.items() if key in props_types}
        kwargs = {key: value for key, value in kwargs.items() if key not in props_types}

        event_types = {
            key
            for key in props
            if (
                (get_origin((annotation := props_types.get(key))) or annotation)
                == EventHandler
            )
        }

        def get_args_spec(key: str) -> types.ArgsSpec | Sequence[types.ArgsSpec]:
            type_ = props_types[key]

            return (
                args[0]
                if (args := get_args(type_))
                else (
                    annotation_args[1]
                    if get_origin(
                        (
                            annotation := inspect.getfullargspec(
                                component_fn
                            ).annotations[key]
                        )
                    )
                    is typing.Annotated
                    and (annotation_args := get_args(annotation))
                    else no_args_event_spec
                )
            )

        super().__init__(
            event_triggers={
                key: EventChain.create(
                    value=props[key],
                    args_spec=get_args_spec(key),
                    key=key,
                )
                for key in event_types
            },
            **kwargs,
        )

        to_camel_cased_props = {
            format.to_camel_case(key) for key in props if key not in event_types
        }
        self.get_props = lambda: to_camel_cased_props  # pyright: ignore [reportIncompatibleVariableOverride]

        # Unset the style.
        self.style = Style()

        # Set the tag to the name of the function.
        self.tag = format.to_title_case(self.component_fn.__name__)

        for key, value in props.items():
            # Skip kwargs that are not props.
            if key not in props_types:
                continue

            camel_cased_key = format.to_camel_case(key)

            # Get the type based on the annotation.
            type_ = props_types[key]

            # Handle event chains.
            if types._issubclass(type_, EventActionsMixin):
                inspect.getfullargspec(component_fn).annotations[key]
                self.props[camel_cased_key] = EventChain.create(
                    value=value, args_spec=get_args_spec(key), key=key
                )
                continue

            value = LiteralVar.create(value)
            self.props[camel_cased_key] = value
            setattr(self, camel_cased_key, value)

    @classmethod
    def _are_fields_known(cls) -> bool:
        """Check if the fields are known.

        Returns:
            Whether the fields are known.
        """
        return False

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

    def _get_all_custom_components(
        self, seen: set[str] | None = None
    ) -> Set[CustomComponent]:
        """Get all the custom components used by the component.

        Args:
            seen: The tags of the components that have already been seen.

        Raises:
            ValueError: If the tag is not set.

        Returns:
            The set of custom components.
        """
        if self.tag is None:
            raise ValueError("The tag must be set.")

        # Store the seen components in a set to avoid infinite recursion.
        if seen is None:
            seen = set()
        custom_components = {self} | super()._get_all_custom_components(seen=seen)

        # Avoid adding the same component twice.
        if self.tag not in seen:
            seen.add(self.tag)
            custom_components |= self.get_component(self)._get_all_custom_components(
                seen=seen
            )

        return custom_components

    def get_prop_vars(self) -> List[Var]:
        """Get the prop vars.

        Returns:
            The prop vars.
        """
        return [
            Var(
                _js_expr=name,
                _var_type=(
                    prop._var_type
                    if isinstance(prop, Var)
                    else (
                        type(prop)
                        if not isinstance(prop, EventActionsMixin)
                        else EventChain
                    )
                ),
            ).guess_type()
            for name, prop in self.props.items()
        ]

    @lru_cache(maxsize=None)  # noqa: B019
    def get_component(self) -> Component:
        """Render the component.

        Returns:
            The code to render the component.
        """
        return self.component_fn(*self.get_prop_vars())


def custom_component(
    component_fn: Callable[..., Component],
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

    def _get_import_name(self) -> None | str:
        if not self.library:
            return None
        return f"${self.library}" if self.library.startswith("/") else self.library

    def _get_imports(self) -> ParsedImportDict:
        """Get the imports for the component.

        Returns:
            The imports for dynamically importing the component at module load time.
        """
        # Next.js dynamic import mechanism.
        dynamic_import = {"next/dynamic": [ImportVar(tag="dynamic", is_default=True)]}

        # The normal imports for this component.
        _imports = super()._get_imports()

        # Do NOT import the main library/tag statically.
        import_name = self._get_import_name()
        if import_name is not None:
            _imports[import_name] = [
                imports.ImportVar(
                    tag=None,
                    render=False,
                    transpile=self._should_transpile(self.library),
                ),
            ]

        return imports.merge_imports(
            dynamic_import,
            _imports,
            self._get_dependencies_imports(),
        )

    def _get_dynamic_imports(self) -> str:
        opts_fragment = ", { ssr: false });"

        # extract the correct import name from library name
        base_import_name = self._get_import_name()
        if base_import_name is None:
            raise ValueError("Undefined library for NoSSRComponent")
        import_name = format.format_library_name(base_import_name)

        library_import = f"const {self.alias if self.alias else self.tag} = dynamic(() => import('{import_name}')"
        mod_import = (
            # https://nextjs.org/docs/pages/building-your-application/optimizing/lazy-loading#with-named-exports
            f".then((mod) => mod.{self.tag})" if not self.is_default else ""
        )
        return "".join((library_import, mod_import, opts_fragment))


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
            for prop_var in component._get_vars(include_children=True):
                if prop_var._get_all_var_data():
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
                if isinstance(child, Var) and child._get_all_var_data():
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
        from reflex.components.core.match import Match

        if isinstance(child, Bare):
            return child.contents
        if isinstance(child, Cond):
            return child.cond
        if isinstance(child, Foreach):
            return child.iterable
        if isinstance(child, Match):
            return child.cond
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
        # Ensure that the hook is a var declaration.
        var_decl = hook.partition("=")[0].strip()
        if not any(var_decl.startswith(kw) for kw in ["const ", "let ", "var "]):
            return []

        # Extract the var name from the declaration.
        _, _, var_name = var_decl.partition(" ")
        var_name = var_name.strip()

        # Break up array and object destructuring if used.
        if var_name.startswith("[") or var_name.startswith("{"):
            return [
                v.strip().replace("...", "") for v in var_name.strip("[]{}").split(",")
            ]
        return [var_name]

    @staticmethod
    def _get_deps_from_event_trigger(event: EventChain | EventSpec | Var) -> set[str]:
        """Get the dependencies accessed by event triggers.

        Args:
            event: The event trigger to extract deps from.

        Returns:
            The dependencies accessed by the event triggers.
        """
        events: list = [event]
        deps = set()

        if isinstance(event, EventChain):
            events.extend(event.events)

        for ev in events:
            if isinstance(ev, EventSpec):
                for arg in ev.args:
                    for a in arg:
                        var_datas = VarData.merge(a._get_all_var_data())
                        if var_datas and var_datas.deps is not None:
                            deps |= {str(dep) for dep in var_datas.deps}
        return deps

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
            rendered_chain = str(LiteralVar.create(event))

            # Hash the rendered EventChain to get a deterministic function name.
            chain_hash = md5(str(rendered_chain).encode("utf-8")).hexdigest()
            memo_name = f"{event_trigger}_{chain_hash}"

            # Calculate Var dependencies accessed by the handler for useCallback dep array.
            var_deps = ["addEvents", "Event"]

            # Get deps from event trigger var data.
            var_deps.extend(cls._get_deps_from_event_trigger(event))

            # Get deps from hooks.
            for arg in event_args:
                var_data = arg._get_all_var_data()
                if var_data is None:
                    continue
                for hook in var_data.hooks:
                    var_deps.extend(cls._get_hook_deps(hook))
            memo_var_data = VarData.merge(
                *[var._get_all_var_data() for var in event_args],
                VarData(
                    imports={"react": [ImportVar(tag="useCallback")]},
                ),
            )

            # Store the memoized function name and hook code for this event trigger.
            trigger_memo[event_trigger] = (
                Var(_js_expr=memo_name)._replace(
                    _var_type=EventChain, merge_var_data=memo_var_data
                ),
                f"const {memo_name} = useCallback({rendered_chain}, [{', '.join(var_deps)}])",
            )
        return trigger_memo

    def _get_all_hooks_internal(self) -> dict[str, VarData | None]:
        """Get the reflex internal hooks for the component and its children.

        Returns:
            The code that should appear just before user-defined hooks.
        """
        return {}

    def _get_all_hooks(self) -> dict[str, VarData | None]:
        """Get the React hooks for this component.

        Returns:
            The code that should appear just before returning the rendered component.
        """
        return {}

    def _get_all_imports(self) -> ParsedImportDict:
        """Get all the libraries and fields that are used by the component.

        Returns:
            The import dict with the required imports.
        """
        if self.rendered_as_shared:
            return {
                f"$/{Dirs.UTILS}/{PageNames.STATEFUL_COMPONENTS}": [
                    ImportVar(tag=self.tag)
                ]
            }
        return self.component._get_all_imports()

    def _get_all_dynamic_imports(self) -> set[str]:
        """Get dynamic imports for the component.

        Returns:
            The dynamic imports.
        """
        if self.rendered_as_shared:
            return set()
        return self.component._get_all_dynamic_imports()

    def _get_all_custom_code(self) -> set[str]:
        """Get custom code for the component.

        Returns:
            The custom code.
        """
        if self.rendered_as_shared:
            return set()
        return self.component._get_all_custom_code().union({self.code})

    def _get_all_refs(self) -> set[str]:
        """Get the refs for the children of the component.

        Returns:
            The refs for the children.
        """
        if self.rendered_as_shared:
            return set()
        return self.component._get_all_refs()

    def render(self) -> dict:
        """Define how to render the component in React.

        Returns:
            The tag to render.
        """
        return dict(Tag(name=self.tag or ""))

    def __str__(self) -> str:
        """Represent the component in React.

        Returns:
            The code to render the component.
        """
        from reflex.compiler.compiler import _compile_component

        return _compile_component(self)

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
        if comp._get_all_hooks():
            comp._memoization_mode = dataclasses.replace(
                comp._memoization_mode, disposition=MemoizationDisposition.ALWAYS
            )
        return comp


load_dynamic_serializer()


class ComponentVar(Var[Component], python_types=BaseComponent):
    """A Var that represents a Component."""


def empty_component() -> Component:
    """Create an empty component.

    Returns:
        An empty component.
    """
    from reflex.components.base.bare import Bare

    return Bare.create("")


def render_dict_to_var(tag: dict | Component | str, imported_names: set[str]) -> Var:
    """Convert a render dict to a Var.

    Args:
        tag: The render dict.
        imported_names: The names of the imported components.

    Returns:
        The Var.
    """
    if not isinstance(tag, dict):
        if isinstance(tag, Component):
            return render_dict_to_var(tag.render(), imported_names)
        return Var.create(tag)

    if "iterable" in tag:
        function_return = Var.create(
            [
                render_dict_to_var(child.render(), imported_names)
                for child in tag["children"]
            ]
        )

        func = ArgsFunctionOperation.create(
            (tag["arg_var_name"], tag["index_var_name"]),
            function_return,
        )

        return FunctionStringVar.create("Array.prototype.map.call").call(
            tag["iterable"]
            if not isinstance(tag["iterable"], ObjectVar)
            else tag["iterable"].items(),
            func,
        )

    if tag["name"] == "match":
        element = tag["cond"]

        conditionals = render_dict_to_var(tag["default"], imported_names)

        for case in tag["match_cases"][::-1]:
            condition = case[0].to_string() == element.to_string()
            for pattern in case[1:-1]:
                condition = condition | (pattern.to_string() == element.to_string())

            conditionals = ternary_operation(
                condition,
                render_dict_to_var(case[-1], imported_names),
                conditionals,
            )

        return conditionals

    if "cond" in tag:
        return ternary_operation(
            tag["cond"],
            render_dict_to_var(tag["true_value"], imported_names),
            render_dict_to_var(tag["false_value"], imported_names)
            if tag["false_value"] is not None
            else Var.create(None),
        )

    props = {}

    special_props = []

    for prop_str in tag["props"]:
        if "=" not in prop_str:
            special_props.append(Var(prop_str).to(ObjectVar))
            continue
        prop = prop_str.index("=")
        key = prop_str[:prop]
        value = prop_str[prop + 2 : -1]
        props[key] = value

    props = Var.create({Var.create(k): Var(v) for k, v in props.items()})

    for prop in special_props:
        props = props.merge(prop)

    contents = tag["contents"][1:-1] if tag["contents"] else None

    raw_tag_name = tag.get("name")
    tag_name = Var(raw_tag_name or "Fragment")

    tag_name = (
        Var.create(raw_tag_name)
        if raw_tag_name
        and raw_tag_name.split(".")[0] not in imported_names
        and raw_tag_name.lower() == raw_tag_name
        else tag_name
    )

    return FunctionStringVar.create(
        "jsx",
    ).call(
        tag_name,
        props,
        *([Var(contents)] if contents is not None else []),
        *[render_dict_to_var(child, imported_names) for child in tag["children"]],
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralComponentVar(CachedVarOperation, LiteralVar, ComponentVar):
    """A Var that represents a Component."""

    _var_value: BaseComponent = dataclasses.field(default_factory=empty_component)

    @cached_property_no_lock
    def _cached_var_name(self) -> str:
        """Get the name of the var.

        Returns:
            The name of the var.
        """
        var_data = self._get_all_var_data()
        if var_data is not None:
            # flatten imports
            imported_names = {j.alias or j.name for i in var_data.imports for j in i[1]}
        else:
            imported_names = set()
        return str(render_dict_to_var(self._var_value.render(), imported_names))

    @cached_property_no_lock
    def _cached_get_all_var_data(self) -> VarData | None:
        """Get the VarData for the var.

        Returns:
            The VarData for the var.
        """
        return VarData.merge(
            self._var_data,
            VarData(
                imports={
                    "@emotion/react": [
                        ImportVar(tag="jsx"),
                    ],
                }
            ),
            VarData(
                imports=self._var_value._get_all_imports(),
            ),
            VarData(
                imports={
                    "react": [
                        ImportVar(tag="Fragment"),
                    ],
                }
            ),
        )

    def __hash__(self) -> int:
        """Get the hash of the var.

        Returns:
            The hash of the var.
        """
        return hash((type(self).__name__, self._js_expr))

    @classmethod
    def create(
        cls,
        value: Component,
        _var_data: VarData | None = None,
    ):
        """Create a var from a value.

        Args:
            value: The value of the var.
            _var_data: Additional hooks and imports associated with the Var.

        Returns:
            The var.
        """
        var_datas = [
            var_data
            for var in value._get_vars(include_children=True)
            if (var_data := var._get_all_var_data())
        ]

        return LiteralComponentVar(
            _js_expr="",
            _var_type=type(value),
            _var_data=VarData.merge(
                _var_data,
                *var_datas,
                VarData(
                    components=(value,),
                ),
            ),
            _var_value=value,
        )
