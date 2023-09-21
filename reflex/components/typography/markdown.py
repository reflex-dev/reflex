"""Markdown component."""

import textwrap
from typing import Any, Callable, Dict, List, Union

from reflex.compiler import utils
from reflex.components.component import Component
from reflex.components.datadisplay.list import ListItem, OrderedList, UnorderedList
from reflex.components.navigation import Link
from reflex.components.typography.heading import Heading
from reflex.components.typography.text import Text
from reflex.utils import types
from reflex.vars import BaseVar, ImportVar, Var

# Mapping from markdown tags to components.
components_by_tag: Dict[str, Callable] = {
    "h1": Heading,
    "h2": Heading,
    "h3": Heading,
    "h4": Heading,
    "h5": Heading,
    "h6": Heading,
    "p": Text,
    "ul": UnorderedList,
    "ol": OrderedList,
    "li": ListItem,
    "a": Link,
}

# Component Mapping
base_component_map: dict[str, Callable] = {
    "h1": lambda value: Heading.create(value, as_="h1"),
    "h2": lambda value: Heading.create(value, as_="h2"),
    "h3": lambda value: Heading.create(value, as_="h3"),
    "h4": lambda value: Heading.create(value, as_="h4"),
    "h5": lambda value: Heading.create(value, as_="h5"),
    "h6": lambda value: Heading.create(value, as_="h6"),
    "p": lambda value: Text.create(value),
    "ul": lambda value: UnorderedList.create(value),  # type: ignore
    "ol": lambda value: OrderedList.create(value),  # type: ignore
    "li": lambda value: ListItem.create(value),
    "a": lambda value: Link.create(value),
}


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown@^8.0.7"

    tag = "ReactMarkdown"

    is_default = True

    # The component map
    component_map: Any = base_component_map

    @classmethod
    def create(
        cls, *children, component_map: dict[str, Callable] | None = None, **props
    ) -> Component:
        """Create a markdown component.

        Args:
            *children: The children of the component.
            component_map: A mapping from markdown tags to components.
            **props: The properties of the component.

        Returns:
            The markdown component.
        """
        assert len(children) == 1 and types._isinstance(
            children[0], Union[str, Var]
        ), "Markdown component must have exactly one child containing the markdown source."

        component_map = component_map or {}
        component_map = {**base_component_map, **component_map}

        # Get the markdown source.
        src = children[0]
        if isinstance(src, str):
            src = textwrap.dedent(src)
        return super().create(src, component_map=component_map, **props)

    def _get_imports(self):
        # Import here to avoid circular imports.
        from reflex.components.datadisplay.code import Code, CodeBlock

        imports = super()._get_imports()

        # Special markdown imports.
        imports.update(
            {
                "": {ImportVar(tag="katex/dist/katex.min.css")},
                "rehype-katex@^6.0.3": {ImportVar(tag="rehypeKatex", is_default=True)},
                "remark-math@^5.1.1": {ImportVar(tag="remarkMath", is_default=True)},
                "rehype-raw@^6.1.1": {ImportVar(tag="rehypeRaw", is_default=True)},
                "remark-gfm@^3.0.1": {ImportVar(tag="remarkGfm", is_default=True)},
            }
        )

        # Get the imports for each component.
        for component in self.component_map.values():
            imports = utils.merge_imports(
                imports, component(Var.create("")).get_imports()
            )

        # Get the imports for the code components.
        imports = utils.merge_imports(
            imports, CodeBlock.create(theme="light")._get_imports()
        )
        imports = utils.merge_imports(imports, Code.create()._get_imports())
        return imports

    def _render(self):
        # Import here to avoid circular imports.
        from reflex.components.datadisplay.code import Code, CodeBlock

        def format_comp(comp):
            return str(
                comp(Var.create("children", is_local=False)).set(
                    special_props={Var.create("...props", is_local=False)}
                )
            ).replace("\n", " ")

        components = {
            tag: f"{{({{node, children, ...props}}) => {format_comp(component)}}}"
            for tag, component in self.component_map.items()
        }
        components[
            "code"
        ] = f"""{{({{node, inline, className, children, ...props}}) => {{
    const match = (className || '').match(/language-(?<lang>.*)/);
    return !inline ? (
        <{CodeBlock().tag}
        children={{String(children).replace(/\n$/, '')}}
        language={{match ? match[1] : ''}}
        style={{light}}
        {{...props}}
        />
    ) : (
        <{Code.create().tag} {{...props}}>
        {{children}}
        </{Code.create().tag}>
    );
      }}}}""".replace(
            "\n", " "
        )

        o = (
            super()
            ._render()
            .add_props(
                components=components,
                remark_plugins=BaseVar(name="[remarkMath, remarkGfm]", type_=List[str]),
                rehype_plugins=BaseVar(
                    name="[rehypeKatex, rehypeRaw]", type_=List[str]
                ),
            )
            .remove_props("customComponents", "componentMap")
        )
        return o
