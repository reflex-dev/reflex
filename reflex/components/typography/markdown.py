"""Markdown component."""

import textwrap
from typing import Callable, Dict, List, Union

from reflex.compiler import utils
from reflex.components.component import Component
from reflex.components.datadisplay.list import ListItem, OrderedList, UnorderedList
from reflex.components.navigation import Link
from reflex.components.typography.heading import Heading
from reflex.components.typography.text import Text
from reflex.style import Style
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


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown"

    tag = "ReactMarkdown"

    is_default = True

    # Custom defined styles for the markdown elements.
    custom_styles: Dict[str, Style] = {
        k: Style(v)
        for k, v in {
            "h1": {
                "as_": "h1",
                "size": "2xl",
            },
            "h2": {
                "as_": "h2",
                "size": "xl",
            },
            "h3": {
                "as_": "h3",
                "size": "lg",
            },
            "h4": {
                "as_": "h4",
                "size": "md",
            },
            "h5": {
                "as_": "h5",
                "size": "sm",
            },
            "h6": {
                "as_": "h6",
                "size": "xs",
            },
        }.items()
    }

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a markdown component.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The markdown component.
        """
        assert len(children) == 1 and types._isinstance(
            children[0], Union[str, Var]
        ), "Markdown component must have exactly one child containing the markdown source."

        # Get the markdown source.
        src = children[0]
        if isinstance(src, str):
            src = textwrap.dedent(src)
        return super().create(src, **props)

    def _get_imports(self):
        from reflex.components.datadisplay.code import Code, CodeBlock

        imports = super()._get_imports()

        # Special markdown imports.
        imports["remark-math"] = {ImportVar(tag="remarkMath", is_default=True)}
        imports["remark-gfm"] = {ImportVar(tag="remarkGfm", is_default=True)}
        imports["rehype-katex"] = {ImportVar(tag="rehypeKatex", is_default=True)}
        imports["rehype-raw"] = {ImportVar(tag="rehypeRaw", is_default=True)}
        imports[""] = {ImportVar(tag="katex/dist/katex.min.css")}

        # Get the imports for each component.
        for component in components_by_tag.values():
            imports = utils.merge_imports(imports, component()._get_imports())

        # Get the imports for the code components.
        imports = utils.merge_imports(
            imports, CodeBlock.create(theme="light")._get_imports()
        )
        imports = utils.merge_imports(imports, Code.create()._get_imports())
        return imports

    def _render(self):
        from reflex.components.tags.tag import Tag

        components = {
            tag: f"{{({{node, ...props}}) => <{(component().tag)} {{...props}} {''.join(Tag(name='', props=Style(self.custom_styles.get(tag, {}))).format_props())} />}}"
            for tag, component in components_by_tag.items()
        }
        components[
            "code"
        ] = """{({node, inline, className, children, ...props}) =>
                    {
        const match = (className || '').match(/language-(?<lang>.*)/);
        return !inline ? (
          <Prism
            children={String(children).replace(/\n$/, '')}
            language={match ? match[1] : ''}
            theme={light}
            {...props}
          />
        ) : (
          <Code {...props}>
            {children}
          </Code>
        );
      }}""".replace(
            "\n", " "
        )

        return (
            super()
            ._render()
            .add_props(
                components=components,
                remark_plugins=BaseVar(name="[remarkMath, remarkGfm]", type_=List[str]),
                rehype_plugins=BaseVar(
                    name="[rehypeKatex, rehypeRaw]", type_=List[str]
                ),
            )
            .remove_props("custom_components")
        )
