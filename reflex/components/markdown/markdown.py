"""Markdown component."""

from __future__ import annotations

import textwrap
from functools import lru_cache
from hashlib import md5
from typing import Any, Callable, Dict, Union

from reflex.compiler import utils
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
from reflex.style import Style
from reflex.utils import console, imports, types
from reflex.utils.imports import ImportVar
from reflex.vars import Var

# Special vars used in the component map.
_CHILDREN = Var.create_safe("children", _var_is_local=False)
_PROPS = Var.create_safe("...props", _var_is_local=False)
_MOCK_ARG = Var.create_safe("")

# Special remark plugins.
_REMARK_MATH = Var.create_safe("remarkMath", _var_is_local=False)
_REMARK_GFM = Var.create_safe("remarkGfm", _var_is_local=False)
_REMARK_UNWRAP_IMAGES = Var.create_safe("remarkUnwrapImages", _var_is_local=False)
_REMARK_PLUGINS = Var.create_safe([_REMARK_MATH, _REMARK_GFM, _REMARK_UNWRAP_IMAGES])

# Special rehype plugins.
_REHYPE_KATEX = Var.create_safe("rehypeKatex", _var_is_local=False)
_REHYPE_RAW = Var.create_safe("rehypeRaw", _var_is_local=False)
_REHYPE_PLUGINS = Var.create_safe([_REHYPE_KATEX, _REHYPE_RAW])

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
            value, margin_y="1em", **props
        ),
    }


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown@8.0.7"

    tag = "ReactMarkdown"

    is_default = True

    # The component map from a tag to a lambda that creates a component.
    component_map: Dict[str, Any] = {}

    # Custom styles for the markdown (deprecated in v0.2.9).
    custom_styles: Dict[str, Any] = {}

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
        assert len(children) == 1 and types._isinstance(
            children[0], Union[str, Var]
        ), "Markdown component must have exactly one child containing the markdown source."

        # Custom styles are deprecated.
        if "custom_styles" in props:
            console.deprecate(
                feature_name="rx.markdown custom_styles",
                reason="Use the component_map prop instead.",
                deprecation_version="0.2.9",
                removal_version="0.5.0",
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

    def get_custom_components(
        self, seen: set[str] | None = None
    ) -> set[CustomComponent]:
        """Get all the custom components used by the component.

        Args:
            seen: The tags of the components that have already been seen.

        Returns:
            The set of custom components.
        """
        custom_components = super().get_custom_components(seen=seen)

        # Get the custom components for each tag.
        for component in self.component_map.values():
            custom_components |= component(_MOCK_ARG).get_custom_components(seen=seen)

        return custom_components

    def _get_imports(self) -> imports.ImportDict:
        # Import here to avoid circular imports.
        from reflex.components.datadisplay.code import CodeBlock
        from reflex.components.radix.themes.typography.code import Code

        imports = super()._get_imports()

        # Special markdown imports.
        imports.update(
            {
                "": [ImportVar(tag="katex/dist/katex.min.css")],
                "remark-math@5.1.1": [
                    ImportVar(tag=_REMARK_MATH._var_name, is_default=True)
                ],
                "remark-gfm@3.0.1": [
                    ImportVar(tag=_REMARK_GFM._var_name, is_default=True)
                ],
                "remark-unwrap-images@4.0.0": [
                    ImportVar(tag=_REMARK_UNWRAP_IMAGES._var_name, is_default=True)
                ],
                "rehype-katex@6.0.3": [
                    ImportVar(tag=_REHYPE_KATEX._var_name, is_default=True)
                ],
                "rehype-raw@6.1.1": [
                    ImportVar(tag=_REHYPE_RAW._var_name, is_default=True)
                ],
            }
        )

        # Get the imports for each component.
        for component in self.component_map.values():
            imports = utils.merge_imports(imports, component(_MOCK_ARG).get_imports())

        # Get the imports for the code components.
        imports = utils.merge_imports(
            imports, CodeBlock.create(theme="light")._get_imports()
        )
        imports = utils.merge_imports(imports, Code.create()._get_imports())
        return imports

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

        special_props = {_PROPS}
        children = [_CHILDREN]

        # For certain tags, the props from the markdown renderer are not actually valid for the component.
        if tag in NO_PROPS_TAGS:
            special_props = set()

        # If the children are set as a prop, don't pass them as children.
        children_prop = props.pop("children", None)
        if children_prop is not None:
            special_props.add(Var.create_safe(f"children={str(children_prop)}"))
            children = []

        # Get the component.
        component = self.component_map[tag](*children, **props).set(
            special_props=special_props
        )
        component._add_style(Style(self.custom_styles.get(tag, {})))
        return component

    def format_component(self, tag: str, **props) -> str:
        """Format a component for rendering in the component map.

        Args:
            tag: The tag of the component.
            **props: Extra props to pass to the component function.

        Returns:
            The formatted component.
        """
        return str(self.get_component(tag, **props)).replace("\n", " ")

    def format_component_map(self) -> dict[str, str]:
        """Format the component map for rendering.

        Returns:
            The formatted component map.
        """
        components = {
            tag: f"{{({{node, {_CHILDREN._var_name}, {_PROPS._var_name}}}) => {self.format_component(tag)}}}"
            for tag in self.component_map
        }

        # Separate out inline code and code blocks.
        components[
            "code"
        ] = f"""{{({{node, inline, className, {_CHILDREN._var_name}, {_PROPS._var_name}}}) => {{
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
        {self.format_component("codeblock", language=Var.create_safe("language", _var_is_local=False))}
    );
      }}}}""".replace(
            "\n", " "
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
        for component in self.component_map.values():
            hooks |= component(_MOCK_ARG).get_hooks()
        formatted_hooks = "\n".join(hooks)
        return f"""
        function {self._get_component_map_name()} () {{
            {formatted_hooks}
            return (
                {str(Var.create(self.format_component_map()))}
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
            )
            .remove_props("componentMap", "componentMapHash")
        )
        tag.special_props.add(
            Var.create_safe(
                f"components={{{self._get_component_map_name()}()}}",
                _var_is_local=True,
                _var_is_string=False,
            ),
        )
        return tag
