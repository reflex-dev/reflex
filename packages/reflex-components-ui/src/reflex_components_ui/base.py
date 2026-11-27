"""The base class of the rx.ui components."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar, TypedDict

from reflex_base.components.component import Component
from reflex_base.components.dynamic import is_rendering_dynamic_component
from reflex_base.components.tags import CommonTag
from reflex_base.plugins import get_plugin
from reflex_base.utils import format
from reflex_base.utils.exceptions import ConfigError
from reflex_base.utils.imports import ImportDict, ImportVar
from reflex_base.vars.base import Var
from reflex_base.vars.number import LiteralNumberVar
from reflex_base.vars.sequence import LiteralStringVar

from reflex_components_ui.plugin import UIPlugin
from reflex_components_ui.style.emit import (
    LoweredStyle,
    StyleXStyle,
    UnsupportedStyleError,
    emit,
    inline,
    props_call,
)

MISSING_PLUGIN_ERROR = (
    "rx.ui components need rx.plugins.UIPlugin() in rxconfig.py plugins."
)

# The styles of an element. The generated TypedDict of step 8a replaces it.
StyleProps = Mapping[str, Any]


class CompoundStyle(TypedDict):
    """Styles for a combination of props.

    Attributes:
        when: The value each prop must have, by prop name.
        style: The styles applied when every prop matches.
    """

    when: dict[str, Any]
    style: StyleProps


class ComponentStyles(TypedDict, total=False):
    """The look of a component.

    Attributes:
        base: The styles of every instance.
        variants: The styles of a prop value: prop name, then prop value.
        compound: The styles of a combination of props.
        parts: The look of inner elements, such as a switch thumb, by name.
    """

    base: StyleProps
    variants: dict[str, dict[str, StyleProps]]
    compound: list[CompoundStyle]
    parts: dict[str, ComponentStyles]


def _lower_literal_styles(component: UIComponent) -> LoweredStyle:
    """Merge the base styles of a component with its literal ``style``.

    A stand-in: the ``lower`` and ``merge`` of the style package replace it,
    and bring variants, nested blocks, responsive values and shorthands.

    Args:
        component: The component to style.

    Returns:
        The lowered style of the component's element, the user's style last.

    Raises:
        UnsupportedStyleError: If the component or its style needs what only
            the real lowering provides.
    """
    name = component._display_name()
    styles = component.styles
    if "variants" in styles or "compound" in styles:
        msg = f"{name}: variant and compound styles are not compiled yet."
        raise UnsupportedStyleError(msg)
    lowered = dict(styles.get("base", {}))
    for prop, value in component.style.items():
        if isinstance(value, (LiteralStringVar, LiteralNumberVar)):
            value = value._var_value
        elif not isinstance(value, Var):
            msg = (
                f'{name}: the style "{prop}" is a nested block or a list, which '
                "rx.ui components cannot compile yet. Use flat properties with "
                "literal values."
            )
            raise UnsupportedStyleError(msg)
        lowered[prop] = value
    return lowered


class UIComponent(Component):
    """A component that renders a plain element styled through StyleX.

    No library is imported: the element's styles are declared in the module
    that renders it, where the StyleX compiler folds them into class names.
    """

    tag = "div"

    _is_tag_in_global_scope: ClassVar[bool] = True

    # The component's own look.
    styles: ClassVar[ComponentStyles] = {}

    @classmethod
    def _display_name(cls) -> str:
        """Get the name an app refers to the component by.

        Returns:
            The name, such as ``rx.ui.box``.
        """
        return f"rx.ui.{format.to_snake_case(cls.__name__)}"

    def _stylex(self) -> StyleXStyle | None:
        """Get the StyleX source of the element's style.

        Returns:
            The declaration of the style, or None when the element has none.

        Raises:
            ConfigError: If the plugin that compiles the styles is not configured.
        """
        if get_plugin(UIPlugin) is None:
            raise ConfigError(MISSING_PLUGIN_ERROR)
        return emit(_lower_literal_styles(self), self._display_name())

    def add_imports(self) -> ImportDict:
        """Import StyleX, which the build compiles away.

        Returns:
            The import, or nothing for code that never reaches the build.
        """
        if is_rendering_dynamic_component():
            return {}
        # The plugin installs it as a development dependency.
        return {
            "@stylexjs/stylex": ImportVar(
                tag="*", alias="stylex", is_default=True, install=False
            )
        }

    def add_custom_code(self) -> list[str]:
        """Declare the element's style in the module that renders it.

        Returns:
            The ``stylex.create`` declaration, or nothing for code that never
            reaches the build.
        """
        if is_rendering_dynamic_component():
            return []
        style = self._stylex()
        return [] if style is None else [style.declaration]

    def _get_style(self) -> dict:
        """Get the props that carry the style: none, as ``_render`` adds them.

        Returns:
            An empty dictionary: an rx.ui component never has a ``css`` prop.
        """
        return {}

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the element with its style.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with a ``stylex.props`` spread, or with an inline style in
            code that never reaches the build.
        """
        tag = super()._render(props)
        if is_rendering_dynamic_component():
            style = inline(_lower_literal_styles(self), self._display_name())
            return tag.add_props(style=style) if style else tag
        style = self._stylex()
        if style is None:
            return tag
        return _add_stylex_props(tag, style.ref)


def _add_stylex_props(tag: CommonTag, ref: str) -> CommonTag:
    """Give a tag the class names of a style, beside its own.

    Args:
        tag: The rendered element.
        ref: The expression naming the style.

    Returns:
        The tag with a ``stylex.props`` spread, or with one ``className``
        expression when its own class names come from state.
    """
    class_name = tag.props.get("className")
    if class_name is None:
        return tag.set(special_props=[*tag.special_props, Var(props_call((ref,)))])
    if isinstance(class_name, LiteralStringVar):
        # A spread would replace the attribute, so both fold into one string.
        return tag.remove_props("className").set(
            special_props=[
                *tag.special_props,
                Var(props_call((ref,), class_name._var_value)),
            ]
        )
    return tag.add_props(
        class_name=Var(
            # Parenthesized: the expression may be a conditional.
            f'({class_name!s}) + " " + {props_call((ref,))}.className',
            _var_type=str,
            _var_data=class_name._get_all_var_data(),
        )
    )
