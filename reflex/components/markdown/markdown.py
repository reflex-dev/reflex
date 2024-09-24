"""Markdown component."""

from __future__ import annotations

import textwrap
from functools import lru_cache
from hashlib import md5
from typing import Any, Callable, Dict, Union

from reflex.components.component import Component, CustomComponent
from reflex.components.radix.themes.layout.list import (
    ListItem,
    OrderedList,
    UnorderedList,
)
from reflex.components.radix.themes.typography.heading import Heading
from reflex.components.radix.themes.typography.link import Link
from reflex.components.radix.themes.typography.text import Text
from reflex.components.tags.tag import Tag
from reflex.utils import types
from reflex.utils.imports import ImportDict, ImportVar
from reflex.vars.base import LiteralVar, Var

# Special vars used in the component map.
_CHILDREN = Var(_js_expr="children", _var_type=str)
_PROPS = Var(_js_expr="...props")
_PROPS_IN_TAG = Var(_js_expr="{...props}")
_MOCK_ARG = Var(_js_expr="", _var_type=str)

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
    from reflex.components.radix.themes.typography.code import Code

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

        Returns:
            The markdown component.
        """
        assert (
            len(children) == 1 and types._isinstance(children[0], Union[str, Var])
        ), "Markdown component must have exactly one child containing the markdown source."

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
        from reflex.components.datadisplay.code import CodeBlock
        from reflex.components.radix.themes.typography.code import Code

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
            CodeBlock.create(theme="light")._get_imports(),  # type: ignore,
            Code.create()._get_imports(),  # type: ignore,
        ]

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
        children = [_CHILDREN]

        # For certain tags, the props from the markdown renderer are not actually valid for the component.
        if tag in NO_PROPS_TAGS:
            special_props = []

        # If the children are set as a prop, don't pass them as children.
        children_prop = props.pop("children", None)
        if children_prop is not None:
            special_props.append(Var(_js_expr=f"children={{{str(children_prop)}}}"))
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

    def format_component_map(self) -> dict[str, Var]:
        """Format the component map for rendering.

        Returns:
            The formatted component map.
        """
        components = {
            tag: Var(
                _js_expr=f"(({{node, {_CHILDREN._js_expr}, {_PROPS._js_expr}}}) => ({self.format_component(tag)}))"
            )
            for tag in self.component_map
        }

        # Separate out inline code and code blocks.
        components["code"] = Var(
            _js_expr=f"""(({{node, inline, className, {_CHILDREN._js_expr}, {_PROPS._js_expr}}}) => {{
    const match = (className || '').match(/language-(?<lang>.*)/);
    const language = match ? match[1] : '';
    if (language) {{
    (async () => {{
      try {{
        const module = await import(`react-syntax-highlighter/dist/cjs/languages/prism/${{language}}`);
        SyntaxHighlighter.registerLanguage(language, module.default);
      }} catch (error) {{
        console.error(`Error importing language module for ${{language}}:`, error);
      }}
    }})();
  }}
    return inline ? (
        {self.format_component("code")}
    ) : (
        {self.format_component("codeblock", language=Var(_js_expr="language", _var_type=str))}
    );
      }})""".replace("\n", " ")
        )

        return components

    @staticmethod
    def _component_map_hash(component_map) -> str:
        inp = str(
            {tag: component(_MOCK_ARG) for tag, component in component_map.items()}
        ).encode()
        return md5(inp).hexdigest()

    def _get_component_map_name(self) -> str:
        return f"ComponentMap_{self.component_map_hash}"

    def _get_custom_code(self) -> str | None:
        hooks = set()
        for _component in self.component_map.values():
            comp = _component(_MOCK_ARG)
            hooks.update(comp._get_all_hooks_internal())
            hooks.update(comp._get_all_hooks())
        formatted_hooks = "\n".join(hooks)
        return f"""
        function {self._get_component_map_name()} () {{
            {formatted_hooks}
            return (
                {str(LiteralVar.create(self.format_component_map()))}
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
