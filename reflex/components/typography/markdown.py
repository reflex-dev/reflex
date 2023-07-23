"""Markdown component."""

import textwrap
from typing import Callable, Dict, List, Optional, Set, Union

from reflex.components.component import Component, CustomComponent
from reflex.components.typography.heading import Heading
from reflex.components.typography.text import Text
from reflex.components.datadisplay.list import UnorderedList, OrderedList, ListItem
from reflex.components.datadisplay.code import Code, CodeBlock
from reflex.components.navigation import Link

from reflex.compiler import utils
from reflex.utils import types
from reflex.vars import BaseVar, ImportVar, Var
from reflex.style import Style


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown"

    tag = "ReactMarkdown"

    is_default = True

    # Custom defined styles for the markdown elements.
    custom_components: Dict[str, Callable] = {
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

    # Custom defined styles for the markdown elements.
    custom_styles: Dict[str, Style] = {
        "h1": {
            "size": "2xl",
        },
        "h2": {
            "size": "xl",
        },
        "h3": {
            "size": "lg",
        },
        "h4": {
            "size": "md",
        },
        "h5": {
            "size": "sm",
        },
        "h6": {
            "size": "xs",
        },
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

    def get_custom_components(
        self, seen: Optional[Set[str]] = None
    ) -> Set[CustomComponent]:
        """Get all the custom components used by the component.

        Args:
            seen: The tags of the components that have already been seen.

        Returns:
            The set of custom components.
        """
        custom_components = super().get_custom_components(seen=seen)
        for component in self.custom_components.values():
            custom_components |= component(text="hi").get_custom_components(seen=seen)
        return custom_components

    def _get_imports(self):
        imports = super()._get_imports()
        # imports["react-syntax-highlighter"] = {ImportVar(tag="Prism", is_default=True)}
        imports["remark-math"] = {ImportVar(tag="remarkMath", is_default=True)}
        imports["remark-gfm"] = {ImportVar(tag="remarkGfm", is_default=True)}
        imports["rehype-katex"] = {ImportVar(tag="rehypeKatex", is_default=True)}
        imports["rehype-raw"] = {ImportVar(tag="rehypeRaw", is_default=True)}
        imports[""] = {ImportVar(tag="katex/dist/katex.min.css")}
        for component in self.custom_components.values():
            imports = utils.merge_imports(imports, component()._get_imports())

        imports = utils.merge_imports(imports, CodeBlock(theme="light")._get_imports())
        imports = utils.merge_imports(imports, Code()._get_imports())

        # if self.custom_components["h1"] != Heading:
        #     breakpoint()

        return imports

    def _render(self):
        from reflex.components.tags.tag import Tag
        from reflex.compiler.templates import UTILS
        return (
            super()
            ._render(ignore_props={"custom_components", "custom_styles"})
            .add_props(
                components={
                    tag: f"{{({{node, ...props}}) => <{(component().tag)} {{...props}} {''.join(Tag(name='', props={'sx': Style(self.custom_styles.get(tag, {}))}).format_props())} />}}"
                    for tag, component in self.custom_components.items()
                } | {
                    # "h1": "{({node, ...props}) => <Heading size='2xl' paddingY='0.5em' {...props} />}",
                    # "h2": "{({node, ...props}) => <Heading size='xl' paddingY='0.5em' {...props} />}",
                    # "h3": "{({node, ...props}) => <Heading size='lg' paddingY='0.5em' {...props} />}",
                    # "h4": "{({node, ...props}) => <Heading size='sm' paddingY='0.5em' {...props} />}",
                    # "h5": "{({node, ...props}) => <Heading size='xs' paddingY='0.5em' {...props} />}",
                    # "ul": "{UnorderedList}",
                    # "ol": "{OrderedList}",
                    # "li": "{ListItem}",
                    # "p": "{({node, ...props}) => <Text paddingY='0.5em' {...props} />}",
                    # "a": "{Link}",
                    "code": """{({node, inline, className, children, ...props}) =>
                    {
        const match = (className || '').match(/language-(?<lang>.*)/);
        return !inline ? (
          <Prism
            children={String(children).replace(/\n$/, '')}
            language={match ? match[1] : 'python'}
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
                    ),
                },
                remark_plugins=BaseVar(name="[remarkMath, remarkGfm]", type_=List[str]),
                rehype_plugins=BaseVar(
                    name="[rehypeKatex, rehypeRaw]", type_=List[str]
                ),
            ).remove_props("custom_components")
        )
