"""Markdown component."""

from __future__ import annotations

import dataclasses
import textwrap
from functools import lru_cache
from hashlib import md5
from typing import Any, Callable, Dict, Sequence, Union

from reflex.components.component import Component, CustomComponent
from reflex.components.tags.tag import Tag
from reflex.utils import types
from reflex.utils.imports import ImportDict, ImportVar
from reflex.vars.base import LiteralVar, Var
from reflex.vars.function import ARRAY_ISARRAY, ArgsFunctionOperation, DestructuredArg
from reflex.vars.number import ternary_operation

# Special vars used in the component map.
_CHILDREN = Var(_js_expr="children", _var_type=str)
_PROPS = Var(_js_expr="...props")
_PROPS_IN_TAG = Var(_js_expr="{...props}")
_MOCK_ARG = Var(_js_expr="", _var_type=str)
_LANGUAGE = Var(_js_expr="_language", _var_type=str)

# Special remark plugins.
_REMARK_MATH = Var(_js_expr="remarkMath")
_REMARK_GFM = Var(_js_expr="remarkGfm")
_REMARK_UNWRAP_IMAGES = Var(_js_expr="remarkUnwrapImages")
_REMARK_PLUGINS = LiteralVar.create([_REMARK_MATH, _REMARK_GFM, _REMARK_UNWRAP_IMAGES])

# Special rehype plugins.
_REHYPE_KATEX = Var(_js_expr="rehypeKatex")
_REHYPE_RAW = Var(_js_expr="rehypeRaw")
_REHYPE_PLUGINS = LiteralVar.create([_REHYPE_KATEX, _REHYPE_RAW])

# These tags do NOT get props passed to them
NO_PROPS_TAGS = ("ul", "ol", "li")


# Component Mapping
@lru_cache
def get_base_component_map() -> dict[str, Callable]:
    """Get the base component map.

    Returns:
        The base component map.
    """
    from reflex.components.datadisplay.code import CodeBlock
    from reflex.components.radix.themes.layout.list import (
        ListItem,
        OrderedList,
        UnorderedList,
    )
    from reflex.components.radix.themes.typography.code import Code
    from reflex.components.radix.themes.typography.heading import Heading
    from reflex.components.radix.themes.typography.link import Link
    from reflex.components.radix.themes.typography.text import Text

    return {
        "h1": lambda value: Heading.create(value, as_="h1", size="6", margin_y="0.5em"),
        "h2": lambda value: Heading.create(value, as_="h2", size="5", margin_y="0.5em"),
        "h3": lambda value: Heading.create(value, as_="h3", size="4", margin_y="0.5em"),
        "h4": lambda value: Heading.create(value, as_="h4", size="3", margin_y="0.5em"),
        "h5": lambda value: Heading.create(value, as_="h5", size="2", margin_y="0.5em"),
        "h6": lambda value: Heading.create(value, as_="h6", size="1", margin_y="0.5em"),
        "p": lambda value: Text.create(value, margin_y="1em"),
        "ul": lambda value: UnorderedList.create(value, margin_y="1em"),  # type: ignore
        "ol": lambda value: OrderedList.create(value, margin_y="1em"),  # type: ignore
        "li": lambda value: ListItem.create(value, margin_y="0.5em"),
        "a": lambda value: Link.create(value),
        "code": lambda value: Code.create(value),
        "codeblock": lambda value, **props: CodeBlock.create(
            value, margin_y="1em", wrap_long_lines=True, **props
        ),
    }


@dataclasses.dataclass()
class MarkdownComponentMap:
    """Mixin class for handling custom component maps in Markdown components."""

    _explicit_return: bool = dataclasses.field(default=False)

    @classmethod
    def get_component_map_custom_code(cls) -> str:
        """Get the custom code for the component map.

        Returns:
            The custom code for the component map.
        """
        return ""

    @classmethod
    def create_map_fn_var(
        cls,
        fn_body: Var | None = None,
        fn_args: Sequence[str] | None = None,
        explicit_return: bool | None = None,
    ) -> Var:
        """Create a function Var for the component map.

        Args:
            fn_body: The formatted component as a string.
            fn_args: The function arguments.
            explicit_return: Whether to use explicit return syntax.

        Returns:
            The function Var for the component map.
        """
        fn_args = fn_args or cls.get_fn_args()
        fn_body = fn_body if fn_body is not None else cls.get_fn_body()
        explicit_return = explicit_return or cls._explicit_return

        return ArgsFunctionOperation.create(
            args_names=(DestructuredArg(fields=tuple(fn_args)),),
            return_expr=fn_body,
            explicit_return=explicit_return,
        )

    @classmethod
    def get_fn_args(cls) -> Sequence[str]:
        """Get the function arguments for the component map.

        Returns:
            The function arguments as a list of strings.
        """
        return ["node", _CHILDREN._js_expr, _PROPS._js_expr]

    @classmethod
    def get_fn_body(cls) -> Var:
        """Get the function body for the component map.

        Returns:
            The function body as a string.
        """
        return Var(_js_expr="undefined", _var_type=None)


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown@8.0.7"

    tag = "ReactMarkdown"

    is_default = True

    # The component map from a tag to a lambda that creates a component.
    component_map: Dict[str, Any] = {}

    # The hash of the component map, generated at create() time.
    component_map_hash: str = ""

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a markdown component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Raises:
            ValueError: If the children are not valid.

        Returns:
            The markdown component.
        """
        if len(children) != 1 or not types._isinstance(children[0], Union[str, Var]):
            raise ValueError(
                "Markdown component must have exactly one child containing the markdown source."
            )

        # Update the base component map with the custom component map.
        component_map = {**get_base_component_map(), **props.pop("component_map", {})}

        # Get the markdown source.
        src = children[0]

        # Dedent the source.
        if isinstance(src, str):
            src = textwrap.dedent(src)

        # Create the component.
        return super().create(
            src,
            component_map=component_map,
            component_map_hash=cls._component_map_hash(component_map),
            **props,
        )

    def _get_all_custom_components(
        self, seen: set[str] | None = None
    ) -> set[CustomComponent]:
        """Get all the custom components used by the component.

        Args:
            seen: The tags of the components that have already been seen.

        Returns:
            The set of custom components.
        """
        custom_components = super()._get_all_custom_components(seen=seen)

        # Get the custom components for each tag.
        for component in self.component_map.values():
            custom_components |= component(_MOCK_ARG)._get_all_custom_components(
                seen=seen
            )

        return custom_components

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the markdown component.

        Returns:
            The imports for the markdown component.
        """
        return [
            {
                "": "katex/dist/katex.min.css",
                "remark-math@5.1.1": ImportVar(
                    tag=_REMARK_MATH._js_expr, is_default=True
                ),
                "remark-gfm@3.0.1": ImportVar(
                    tag=_REMARK_GFM._js_expr, is_default=True
                ),
                "remark-unwrap-images@4.0.0": ImportVar(
                    tag=_REMARK_UNWRAP_IMAGES._js_expr, is_default=True
                ),
                "rehype-katex@6.0.3": ImportVar(
                    tag=_REHYPE_KATEX._js_expr, is_default=True
                ),
                "rehype-raw@6.1.1": ImportVar(
                    tag=_REHYPE_RAW._js_expr, is_default=True
                ),
            },
            *[
                component(_MOCK_ARG)._get_all_imports()  # type: ignore
                for component in self.component_map.values()
            ],
        ]

    def _get_tag_map_fn_var(self, tag: str) -> Var:
        return self._get_map_fn_var_from_children(self.get_component(tag), tag)

    def format_component_map(self) -> dict[str, Var]:
        """Format the component map for rendering.

        Returns:
            The formatted component map.
        """
        components = {
            tag: self._get_tag_map_fn_var(tag)
            for tag in self.component_map
            if tag not in ("code", "codeblock")
        }

        # Separate out inline code and code blocks.
        components["code"] = self._get_inline_code_fn_var()

        return components

    def _get_inline_code_fn_var(self) -> Var:
        """Get the function variable for inline code.

        This function creates a Var that represents a function to handle
        both inline code and code blocks in markdown.

        Returns:
            The Var for inline code.
        """
        # Get any custom code from the codeblock and code components.
        custom_code_list = self._get_map_fn_custom_code_from_children(
            self.get_component("codeblock")
        )
        custom_code_list.extend(
            self._get_map_fn_custom_code_from_children(self.get_component("code"))
        )

        codeblock_custom_code = "\n".join(custom_code_list)

        # Format the code to handle inline and block code.
        formatted_code = f"""
const match = (className || '').match(/language-(?<lang>.*)/);
const {_LANGUAGE!s} = match ? match[1] : '';
{codeblock_custom_code};
            return inline ? (
                {self.format_component("code")}
            ) : (
                {self.format_component("codeblock", language=_LANGUAGE)}
            );
        """.replace("\n", " ")

        return MarkdownComponentMap.create_map_fn_var(
            fn_args=(
                "node",
                "inline",
                "className",
                _CHILDREN._js_expr,
                _PROPS._js_expr,
            ),
            fn_body=Var(_js_expr=formatted_code),
            explicit_return=True,
        )

    def get_component(self, tag: str, **props) -> Component:
        """Get the component for a tag and props.

        Args:
            tag: The tag of the component.
            **props: The props of the component.

        Returns:
            The component.

        Raises:
            ValueError: If the tag is invalid.
        """
        # Check the tag is valid.
        if tag not in self.component_map:
            raise ValueError(f"No markdown component found for tag: {tag}.")

        special_props = [_PROPS_IN_TAG]
        children = [
            _CHILDREN
            if tag != "codeblock"
            # For codeblock, the mapping for some cases returns an array of elements. Let's join them into a string.
            else ternary_operation(
                ARRAY_ISARRAY.call(_CHILDREN),  # type: ignore
                _CHILDREN.to(list).join("\n"),
                _CHILDREN,
            ).to(str)
        ]

        # For certain tags, the props from the markdown renderer are not actually valid for the component.
        if tag in NO_PROPS_TAGS:
            special_props = []

        # If the children are set as a prop, don't pass them as children.
        children_prop = props.pop("children", None)
        if children_prop is not None:
            special_props.append(Var(_js_expr=f"children={{{children_prop!s}}}"))
            children = []
        # Get the component.
        component = self.component_map[tag](*children, **props).set(
            special_props=special_props
        )
        return component

    def format_component(self, tag: str, **props) -> str:
        """Format a component for rendering in the component map.

        Args:
            tag: The tag of the component.
            **props: Extra props to pass to the component function.

        Returns:
            The formatted component.
        """
        return str(self.get_component(tag, **props)).replace("\n", "")

    def _get_map_fn_var_from_children(self, component: Component, tag: str) -> Var:
        """Create a function Var for the component map for the specified tag.

        Args:
            component: The component to check for custom code.
            tag: The tag of the component.

        Returns:
            The function Var for the component map.
        """
        formatted_component = Var(
            _js_expr=f"({self.format_component(tag)})", _var_type=str
        )
        if isinstance(component, MarkdownComponentMap):
            return component.create_map_fn_var(fn_body=formatted_component)

        # fallback to the default fn Var creation if the component is not a MarkdownComponentMap.
        return MarkdownComponentMap.create_map_fn_var(fn_body=formatted_component)

    def _get_map_fn_custom_code_from_children(self, component) -> list[str]:
        """Recursively get markdown custom code from children components.

        Args:
            component: The component to check for custom code.

        Returns:
            A list of markdown custom code strings.
        """
        custom_code_list = []
        if isinstance(component, MarkdownComponentMap):
            custom_code_list.append(component.get_component_map_custom_code())

        # If the component is a custom component(rx.memo), obtain the underlining
        # component and get the custom code from the children.
        if isinstance(component, CustomComponent):
            custom_code_list.extend(
                self._get_map_fn_custom_code_from_children(
                    component.component_fn(*component.get_prop_vars())
                )
            )
        elif isinstance(component, Component):
            for child in component.children:
                custom_code_list.extend(
                    self._get_map_fn_custom_code_from_children(child)
                )

        return custom_code_list

    @staticmethod
    def _component_map_hash(component_map) -> str:
        inp = str(
            {tag: component(_MOCK_ARG) for tag, component in component_map.items()}
        ).encode()
        return md5(inp).hexdigest()

    def _get_component_map_name(self) -> str:
        return f"ComponentMap_{self.component_map_hash}"

    def _get_custom_code(self) -> str | None:
        hooks = {}
        for _component in self.component_map.values():
            comp = _component(_MOCK_ARG)
            hooks.update(comp._get_all_hooks_internal())
            hooks.update(comp._get_all_hooks())
        formatted_hooks = "\n".join(hooks.keys())
        return f"""
        function {self._get_component_map_name()} () {{
            {formatted_hooks}
            return (
                {LiteralVar.create(self.format_component_map())!s}
            )
        }}
        """

    def _render(self) -> Tag:
        tag = (
            super()
            ._render()
            .add_props(
                remark_plugins=_REMARK_PLUGINS,
                rehype_plugins=_REHYPE_PLUGINS,
                components=Var(_js_expr=f"{self._get_component_map_name()}()"),
            )
            .remove_props("componentMap", "componentMapHash")
        )
        return tag
