"""The base class of the rx.ui components."""

from __future__ import annotations

import dataclasses
import functools
import json
import types
import typing
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, ClassVar, Literal

from reflex_base import breakpoints
from reflex_base.components.component import BaseComponent, Component
from reflex_base.components.dynamic import is_rendering_dynamic_component
from reflex_base.components.tags import CommonTag
from reflex_base.constants.compiler import SPECIAL_ATTRS
from reflex_base.plugins import get_plugin
from reflex_base.style import media_query
from reflex_base.utils import format
from reflex_base.utils.exceptions import ConfigError
from reflex_base.utils.imports import ImportDict, ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.sequence import LiteralStringVar

from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style import (
    LAYOUT_PROPS,
    ComponentStyles,
    Merged,
    StyleError,
    merge,
)
from reflex_components_ui.style.emit import Emitted, emit, inline
from reflex_components_ui.style.lower import EMPTY, suggest
from reflex_components_ui.style.merge import over
from reflex_components_ui.themes import color_scheme_styles

MISSING_PLUGIN_ERROR = (
    "rx.ui components need rx.plugins.UIPlugin() in rxconfig.py plugins."
)

# What starts a keyword argument that is never a style: an event trigger, or
# an attribute that is passed to the element as it is.
_NOT_A_STYLE = ("on_", *SPECIAL_ATTRS)


def _consulted(styles: Mapping[str, Any]) -> dict[str, None]:
    """Find the props a style table reads.

    Args:
        styles: The style table of a component, or of one of its parts.

    Returns:
        The names of the props, as the keys of a dict to keep their order.
    """
    props: dict[str, None] = dict.fromkeys(styles.get("variants", ()))
    for compound in styles.get("compound", ()):
        props.update(dict.fromkeys(compound["props"]))
    for part in styles.get("parts", {}).values():
        props.update(_consulted(part))
    return props


def _choices(annotation: Any) -> tuple[str, ...] | None:
    """Find the values a prop takes when its type is a literal of strings.

    Args:
        annotation: The type of the prop, such as ``Var[Responsive[Literal[...]]]``.

    Returns:
        The values, or None when the prop takes anything else too.
    """
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is Literal:
        return args if all(arg.__class__ is str for arg in args) else None
    if origin is Var:
        return _choices(args[0])
    if origin in (typing.Union, types.UnionType):
        # A value per breakpoint is a dict of the same values.
        found = None
        for arg in args:
            if typing.get_origin(arg) is breakpoints.Breakpoints:
                continue
            choices = _choices(arg)
            if choices is None:
                return None
            found = choices if found is None else (*found, *choices)
        return found
    return None


def _literal(value: Any) -> Any:
    """Read a prop that has to be known while compiling.

    Args:
        value: The value of the prop.

    Returns:
        The value a literal Var holds, or the value as given.
    """
    if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
        return value._var_value
    return value


def _join_class_names(first: Any, second: Any) -> Any:
    """Join the class names of two elements that render as one.

    Args:
        first: The class names of one, or None.
        second: The class names of the other, or None.

    Returns:
        Both, separated by a space.
    """
    if first is None:
        return second
    if second is None:
        return first
    first, second = LiteralVar.create(first), LiteralVar.create(second)
    if isinstance(first, LiteralStringVar) and isinstance(second, LiteralStringVar):
        return LiteralVar.create(f"{first._var_value} {second._var_value}".strip())
    return Var(
        f'({first!s}) + " " + ({second!s})',
        _var_type=str,
        _var_data=VarData.merge(
            first._get_all_var_data(), second._get_all_var_data()
        ),
    )


def _responsive(style: breakpoints.Breakpoints) -> dict[str, Any]:
    """Read a whole style given per breakpoint as blocks under media queries.

    Args:
        style: The styles of each breakpoint.

    Returns:
        One style: what applies everywhere, then a block per breakpoint.
    """
    names = breakpoints.breakpoint_names
    blocks: dict[str, Any] = {}
    for breakpoint, block in style.items():
        if breakpoint == "initial":
            blocks = {**block, **blocks}
        else:
            width = (
                breakpoints.breakpoints_values[names.index(breakpoint)]
                if breakpoint in names
                else breakpoint
            )
            blocks[media_query(width)] = block
    return blocks


def _combine(styles: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Write the styles of an element over each other, in the order given.

    A key replaces the same key, as it does in the ``style`` of any Reflex
    component, and moves to the end: what is written last wins over a
    shorthand or a longhand written before it.

    Args:
        styles: The styles as written, at least one.

    Returns:
        One style holding them all.
    """
    if len(styles) == 1:
        return styles[0]
    combined = dict(styles[0])
    for style in styles[1:]:
        for key, value in style.items():
            combined.pop(key, None)
            combined[key] = value
    return combined


class UIComponent(Component):
    """A component that renders a plain element styled through StyleX.

    No library is imported: the element's styles are declared in the module
    that renders it, where the StyleX compiler folds them into class names.

    A subclass declares its props as fields. A prop its style table reads
    selects a variant, and a prop named after a layout prop, such as ``gap``,
    is lowered to styles: neither reaches the element as an attribute. Any
    other keyword argument is a CSS property.

    A subclass that renders one HTML element lists the element class of
    ``reflex_components_core.el`` after this one, which gives it the
    attributes of its tag as props. Two fields change the element itself:
    ``as_`` names the tag, and ``as_child`` renders the only child in place of
    the element, with the styles and attributes of both.
    """

    tag = "div"

    _is_tag_in_global_scope: ClassVar[bool] = True

    # The component's own look.
    styles: ClassVar[ComponentStyles] = {}

    # The tags the `as_` prop renders. Any other value renders the tag of the
    # component, as Radix Themes falls back to its default.
    _as_tags: ClassVar[frozenset[str]] = frozenset()

    # How the stubs type the style: the properties and keywords of CSS.
    _pyi_overwrite_types: ClassVar[dict[str, str]] = {
        "style": (
            "Sequence[StyleProps] | StyleProps | Var[Mapping[str, Any]] "
            "| Breakpoints | None"
        ),
    }
    _pyi_imports: ClassVar[dict[str, list[str]]] = {
        "reflex_components_ui.style": ["StyleProps"],
    }

    @classmethod
    @functools.cache
    def _display_name(cls) -> str:
        """Get the name an app refers to the component by.

        Returns:
            The name, such as ``rx.ui.box``.
        """
        return f"rx.ui.{format.to_snake_case(cls.__name__)}"

    @classmethod
    @functools.cache
    def _style_props(cls) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Get the props that are read as styles rather than rendered.

        Returns:
            The fields that are layout props, and the props the style table
            selects variants by.
        """
        variants = _consulted(cls.styles)
        # A prop the style table reads is a variant whatever its name: the
        # `align` of text is not the `align` of a flex container.
        layout_props = LAYOUT_PROPS.intersection(cls.get_fields()).difference(variants)
        return tuple(sorted(layout_props)), tuple(variants)

    @classmethod
    @functools.cache
    def _literal_props(cls) -> dict[str, tuple[str, ...]]:
        """Get the props read as styles, or as the tag, that take listed values.

        Returns:
            The values of each such prop. The accent color is not one: its
            error is the one of a theme.
        """
        layout_props, variants = cls._style_props()
        fields = cls.get_fields()
        literals = {}
        for prop in (*layout_props, *variants, "as_"):
            if prop in fields and prop != "color_scheme":
                choices = _choices(fields[prop].annotated_type)
                if choices is not None:
                    literals[prop] = choices
        return literals

    def _check_literals(self, kwargs: Mapping[str, Any]) -> None:
        """Fail on a value a prop does not take, naming the ones it does.

        Args:
            kwargs: The keyword arguments the component is created with.

        Raises:
            StyleError: If a prop is given a string it does not take.
        """
        literals = self._literal_props()
        for prop in literals.keys() & kwargs.keys():
            value = _literal(kwargs[prop])
            choices = literals[prop]
            for item in value.values() if isinstance(value, Mapping) else (value,):
                if item.__class__ is str and item not in choices:
                    values = ", ".join([f'"{choice}"' for choice in choices])
                    msg = (
                        f'{self._display_name()}: unknown {prop} "{item}".'
                        f"{suggest(item, choices)} The values are {values}."
                    )
                    raise StyleError(msg)

    def _post_init(self, *args, **kwargs):
        """Initialize the component, taking its styles out of its props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.

        Raises:
            StyleError: If the style is not a dict of styles, a list of them or
                a Var, or cannot be compiled, if a prop is given a value it
                does not take, or if ``as_child`` has no single element to
                render.
            ThemeError: If the ``color_scheme`` is not an accent color.
        """
        fields = self.get_fields()
        triggers = self.get_event_triggers()
        layout_props, _ = self._style_props()
        self._check_literals(kwargs)
        written: list[Mapping[str, Any]] = []
        inline = None
        style = kwargs.pop("style", None)
        if style is not None:
            for item in style if isinstance(style, (list, tuple)) else (style,):
                if isinstance(item, Var):
                    inline = item
                elif isinstance(item, breakpoints.Breakpoints):
                    written.append(_responsive(item))
                elif isinstance(item, Mapping):
                    written.append(item)
                else:
                    msg = (
                        f"{self._display_name()}: style must be a dict of styles, "
                        f"a list of them or a Var, not {type(item).__name__}."
                    )
                    raise StyleError(msg)
        # Keyword arguments that are not props are CSS properties.
        css = [
            key
            for key in kwargs
            if key not in fields
            and key not in triggers
            and not key.startswith(_NOT_A_STYLE)
        ]
        if css:
            written.append({key: kwargs.pop(key) for key in css})
        self._styles: list[Any] = [_combine(written)] if written else []
        if inline is not None:
            self._styles.append(inline)
        self._layout = (
            {prop: kwargs.pop(prop) for prop in layout_props if prop in kwargs}
            if layout_props
            else None
        )
        # Before the props are checked against their types: the error of an
        # unknown color lists the accent colors and suggests the closest.
        color_scheme = kwargs.get("color_scheme") if "color_scheme" in fields else None
        self._accent = (
            None
            if color_scheme is None
            else color_scheme_styles(self._display_name(), color_scheme)
        )
        self._under: Merged | None = None
        super()._post_init(*args, **kwargs)
        self._as: Var | None = None
        if "as_" in fields:
            self._set_tag()
        self._slot: Component | None = None
        if "as_child" in fields:
            self._set_slot()
        self._merge_styles()

    def _set_tag(self) -> None:
        """Render the element the ``as_`` prop names."""
        as_ = _literal(getattr(self, "as_", None))
        if isinstance(as_, Var):
            # The tag is then an expression, evaluated in the browser.
            self._as = as_
        elif as_ in self._as_tags:
            self.tag = as_

    def _set_slot(self) -> None:
        """Find the child an element with ``as_child`` is rendered as.

        Raises:
            StyleError: If ``as_child`` is bound to state, or the component
                does not have exactly one child that renders an element.
        """
        as_child = _literal(getattr(self, "as_child", None))
        if not as_child:
            return
        name = self._display_name()
        if isinstance(as_child, Var):
            msg = (
                f"{name}: as_child is bound to state, but the element is "
                "chosen at compile time. Give it True or False, and choose "
                "between two components with rx.cond."
            )
            raise StyleError(msg)
        children = self.children
        if (
            len(children) != 1
            or not isinstance(children[0], Component)
            or type(children[0]).render
            not in (Component.render, UIComponent.render)
        ):
            msg = (
                f"{name}: as_child renders the only child in place of the "
                f"element, so it needs exactly one child that is an element, "
                f"not {_describe(children)}."
            )
            raise StyleError(msg)
        self._slot = children[0]

    def _get_tag_name(self) -> str:
        """Get the JS expression of the element's tag.

        Returns:
            The tag, or the expression an ``as_`` bound to state holds.
        """
        if self._as is not None:
            return str(self._as)
        return super()._get_tag_name()

    def _merge_styles(self) -> None:
        """Merge the style table with the styles of this element.

        The styles apply in this order: the table, the layout props, the
        styles of the app for the component, then the element's own.
        """
        cls = type(self)
        name = cls._display_name()
        _, variants = cls._style_props()
        styles = self._styles
        if self.style:
            styles = [self.style, *styles]
        props = None
        if variants:
            props = {prop: getattr(self, prop, None) for prop in variants}
            if self._accent is not None and "color_scheme" in props:
                # A style table reads whether the element has an accent of
                # its own, not which one: the tokens resolve against it.
                props["color_scheme"] = "true"
        merged = self._merged = merge(
            name, cls.styles, props, styles or None, self._layout
        )
        self._emitted_styles = None
        if merged.parts:
            _bind_parts(self.children, merged.parts, name)
        slot = self._slot
        if isinstance(slot, UIComponent):
            # The child renders the styles of both, its own over these.
            slot._under = merged
            slot._emitted_styles = None

    def _add_style_recursive(self, style: Any, theme: Component | None = None):
        """Add the styles of the app to the component and its children.

        Args:
            style: A dict from component to styling.
            theme: The theme to apply.

        Returns:
            The component with the additional style.
        """
        result = super()._add_style_recursive(style, theme)
        if self.style:
            self._merge_styles()
        return result

    def _emit(self) -> Emitted:
        """Get the StyleX source of the element's styles.

        Returns:
            What the module that renders the element declares for it.
        """
        emitted = self._emitted_styles
        if emitted is None:
            emitted = self._emitted_styles = emit(self._element_styles())
        return emitted

    def _element_styles(self) -> Merged:
        """Get the merged styles of the element.

        Returns:
            The style table merged with the styles of this element, over the
            styles of a parent that renders as this element. Nothing for an
            element that an rx.ui child of its own renders in its place.
        """
        if isinstance(self._slot, UIComponent):
            return _NO_STYLES
        under = self._under
        return self._merged if under is None else over(under, self._merged)

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in this component, those of its styles included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        yield from self._emit().vars
        if self._accent is not None:
            yield from self._accent.vars

    def add_imports(self) -> ImportDict:
        """Import StyleX, which the build compiles away, and the CSS of tokens.

        Returns:
            The imports, or nothing for code that never reaches the build.
        """
        if is_rendering_dynamic_component():
            return {}
        emitted = self._emit()
        imports: ImportDict = {}
        if emitted.declaration is not None:
            # The plugin installs it as a development dependency.
            imports["@stylexjs/stylex"] = ImportVar(
                tag="*", alias="stylex", is_default=True, install=False
            )
        if emitted.imports:
            # Imported for the CSS that defines the custom properties.
            imports[""] = [
                ImportVar(tag=module, install=False) for module in emitted.imports
            ]
        if self._accent is not None:
            imports.update(self._accent.import_dict())
        return imports

    def add_custom_code(self) -> list[str]:
        """Declare the element's style in the module that renders it.

        Returns:
            The ``stylex.create`` declaration, or nothing for code that never
            reaches the build.

        Raises:
            ConfigError: If the plugin that compiles the styles is not configured.
        """
        if is_rendering_dynamic_component():
            return []
        if get_plugin(UIPlugin) is None:
            raise ConfigError(MISSING_PLUGIN_ERROR)
        declaration = self._emit().declaration
        code = [] if declaration is None else [declaration]
        if self._accent is not None:
            code.extend(self._accent.declarations)
        return code

    def _get_style(self) -> dict:
        """Get the props that carry the style: none, as ``_render`` adds them.

        Returns:
            An empty dictionary: an rx.ui component never has a ``css`` prop.
        """
        return {}

    def _exclude_props(self) -> list[str]:
        """Keep the props that are read as styles off the element.

        Returns:
            The layout props, the props that select a variant, and the accent
            color of the component: an attribute of that name is nothing to
            an element.
        """
        layout_props, variants = self._style_props()
        return [*layout_props, *variants, "color_scheme", "as", "as_child"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the element with its style.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the class names of its style, or with an inline
            style in code that never reaches the build.

        Raises:
            ConfigError: If the plugin that compiles the styles is not configured.
        """
        tag = super()._render(props)
        slot = self._slot
        if slot is not None:
            # The child is the element: its props win, its class names and
            # the ones of this component stand together.
            child = slot._render()
            own_props, child_props = tag.props, child.props
            tag = child.set(
                props={
                    **own_props,
                    **child_props,
                    "className": _join_class_names(
                        own_props.get("className"), child_props.get("className")
                    ),
                },
                special_props=[*tag.special_props, *child.special_props],
            )
        accent = self._accent
        if is_rendering_dynamic_component():
            if accent is not None:
                msg = (
                    f"{self._display_name()}: color_scheme cannot be applied to "
                    "a component rendered from state: its code is evaluated in "
                    "the browser and never reaches the StyleX compiler. Render "
                    "the component in a page and show it with rx.cond."
                )
                raise StyleError(msg)
            style = inline(self._element_styles(), self._display_name())
            return tag.add_props(style=style) if style else tag
        if get_plugin(UIPlugin) is None:
            raise ConfigError(MISSING_PLUGIN_ERROR)
        emitted = self._emit()
        if accent is not None:
            # The themes of an accent only set custom properties, so their
            # class names stand beside the ones of the styles.
            emitted = dataclasses.replace(
                emitted, lookups=(*emitted.lookups, accent.classes)
            )
        return add_styles(tag, emitted)


    def render(self) -> dict:
        """Render the component, or the child that stands in its place.

        Returns:
            The dictionary for template of the component.
        """
        slot = self._slot
        if slot is None:
            return super().render()
        # The child may itself render as its own child.
        while isinstance(slot, UIComponent) and slot._slot is not None:
            slot = slot._slot
        rendered = self._render().render([child.render() for child in slot.children])
        slot._replace_prop_names(rendered)
        return rendered


def _describe(children: Sequence[BaseComponent]) -> str:
    """Say what the children of a component are, for an error message.

    Args:
        children: The children.

    Returns:
        Their number, or the kind of the only one.
    """
    if len(children) == 1:
        return f"a {type(children[0]).__name__}"
    return "none" if not children else f"{len(children)} children"


# What an element that renders nothing of its own declares.
_NO_STYLES = Merged(EMPTY)


class Part(UIComponent):
    """An inner element of a component, styled by a part of its style table.

    A component creates it as one of its children, or as a child of another
    part, and names the part: ``Part.create(part="thumb", tag="span")``.
    """

    def _post_init(self, *args, **kwargs):
        """Initialize the part, which takes its styles from its component.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.

        Raises:
            StyleError: If the part is given styles of its own.
        """
        self._part: str = kwargs.pop("part")
        super()._post_init(*args, **kwargs)
        if self._styles or self._layout:
            msg = (
                f'{self._display_name()}: the part "{self._part}" takes its '
                "styles from the style table of its component. Style it there."
            )
            raise StyleError(msg)

    def _merge_styles(self) -> None:
        """Wait for the component the part belongs to, which has its styles."""
        self._merged = getattr(self, "_merged", None)
        self._emitted_styles = None

    def _element_styles(self) -> Merged:
        """Get the styles the component of the part has for it.

        Returns:
            The merged styles of the part.

        Raises:
            StyleError: If no component has claimed the part.
        """
        if self._merged is None:
            msg = (
                f'{self._display_name()}: the part "{self._part}" is not in a '
                "component whose style table has it. Create it as a child of "
                "its component, or of another part of it."
            )
            raise StyleError(msg)
        return self._merged


def _bind_parts(
    children: Sequence[BaseComponent], parts: Mapping[str, Merged], name: str
) -> None:
    """Give the parts among the children of a component their styles.

    Args:
        children: The children of the component, or of one of its parts.
        parts: The merged styles of each part of the component.
        name: The display name of the component, for error messages.

    Raises:
        StyleError: If the style table has no such part.
    """
    for child in children:
        if isinstance(child, Part) and child._merged is None:
            merged = parts.get(child._part)
            if merged is None:
                msg = (
                    f'{name}: its style table has no part "{child._part}".'
                    f"{suggest(child._part, parts)}"
                )
                raise StyleError(msg)
            child._merged = merged
            _bind_parts(child.children, parts, name)


def add_styles(tag: CommonTag, emitted: Emitted) -> CommonTag:
    """Give a tag the class names and custom properties of its styles.

    Args:
        tag: The rendered element.
        emitted: The StyleX source of its styles.

    Returns:
        The tag with one ``className`` expression: the constants of its
        styles, beside the class names it has of its own.
    """
    if emitted.variables:
        entries = list(emitted.variables)
        if emitted.inline is not None:
            entries.append(f"...{emitted.inline!s}")
        tag = tag.add_props(style=Var(f"({{ {', '.join(entries)} }})"))
    elif emitted.inline is not None:
        tag = tag.add_props(style=emitted.inline)
    if emitted.classes is None and not emitted.lookups:
        return tag
    names = []
    literal = ""
    var_data = None
    class_name = tag.props.get("className")
    if isinstance(class_name, LiteralStringVar):
        if class_name._var_value:
            literal = f"{json.dumps(class_name._var_value + ' ')} + "
    elif class_name is not None:
        # Parenthesized: the expression may be a conditional.
        names.append(f"({class_name!s})")
        var_data = class_name._get_all_var_data()
    if emitted.classes is not None:
        names.append(emitted.classes)
    names.extend(emitted.lookups)
    return tag.add_props(
        class_name=Var(
            literal + ' + " " + '.join(names), _var_type=str, _var_data=var_data
        )
    )
