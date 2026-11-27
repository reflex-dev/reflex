"""The base class of the rx.ui components."""

from __future__ import annotations

import functools
import json
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, ClassVar

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
from reflex_base.vars.base import Var
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
from reflex_components_ui.style.lower import suggest

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
    """

    tag = "div"

    _is_tag_in_global_scope: ClassVar[bool] = True

    # The component's own look.
    styles: ClassVar[ComponentStyles] = {}

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
        fields = cls.get_fields()
        return (
            tuple(sorted(LAYOUT_PROPS.intersection(fields))),
            tuple(_consulted(cls.styles)),
        )

    def _post_init(self, *args, **kwargs):
        """Initialize the component, taking its styles out of its props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.

        Raises:
            StyleError: If the style is not a dict of styles, a list of them or
                a Var, or cannot be compiled.
        """
        fields = self.get_fields()
        triggers = self.get_event_triggers()
        layout_props, _ = self._style_props()
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
        super()._post_init(*args, **kwargs)
        self._merge_styles()

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
        merged = self._merged = merge(
            name,
            cls.styles,
            {prop: getattr(self, prop, None) for prop in variants}
            if variants
            else None,
            styles or None,
            self._layout,
        )
        self._emitted_styles = None
        if merged.parts:
            _bind_parts(self.children, merged.parts, name)

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
            The style table merged with the styles of this element.
        """
        return self._merged

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
        return [] if declaration is None else [declaration]

    def _get_style(self) -> dict:
        """Get the props that carry the style: none, as ``_render`` adds them.

        Returns:
            An empty dictionary: an rx.ui component never has a ``css`` prop.
        """
        return {}

    def _exclude_props(self) -> list[str]:
        """Keep the props that are read as styles off the element.

        Returns:
            The layout props and the props that select a variant.
        """
        layout_props, variants = self._style_props()
        return [*layout_props, *variants]

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
        if is_rendering_dynamic_component():
            style = inline(self._element_styles(), self._display_name())
            return tag.add_props(style=style) if style else tag
        if get_plugin(UIPlugin) is None:
            raise ConfigError(MISSING_PLUGIN_ERROR)
        return _add_styles(tag, self._emit())


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


def _add_styles(tag: CommonTag, emitted: Emitted) -> CommonTag:
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
