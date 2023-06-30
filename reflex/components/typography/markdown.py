"""Markdown component."""

import textwrap
from typing import List, Union

from reflex.components.component import Component
from reflex.utils import types
from reflex.vars import BaseVar, ImportVar, Var


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown"

    tag = "ReactMarkdown"

    is_default = True

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
        imports = super()._get_imports()
        imports["@chakra-ui/react"] = {
            ImportVar(tag="Heading"),
            ImportVar(tag="Code"),
            ImportVar(tag="Text"),
            ImportVar(tag="Link"),
            ImportVar(tag="UnorderedList"),
            ImportVar(tag="OrderedList"),
            ImportVar(tag="ListItem"),
        }
        imports["react-syntax-highlighter"] = {ImportVar(tag="Prism", is_default=True)}
        imports["remark-math"] = {ImportVar(tag="remarkMath", is_default=True)}
        imports["remark-gfm"] = {ImportVar(tag="remarkGfm", is_default=True)}
        imports["rehype-katex"] = {ImportVar(tag="rehypeKatex", is_default=True)}
        imports["rehype-raw"] = {ImportVar(tag="rehypeRaw", is_default=True)}
        imports[""] = {ImportVar(tag="katex/dist/katex.min.css")}
        return imports

    def _render(self):
        return (
            super()
            ._render()
            .add_props(
                components={
                    "h1": "{({node, ...props}) => <Heading size='2xl' paddingY='0.5em' {...props} />}",
                    "h2": "{({node, ...props}) => <Heading size='xl' paddingY='0.5em' {...props} />}",
                    "h3": "{({node, ...props}) => <Heading size='lg' paddingY='0.5em' {...props} />}",
                    "h4": "{({node, ...props}) => <Heading size='sm' paddingY='0.5em' {...props} />}",
                    "h5": "{({node, ...props}) => <Heading size='xs' paddingY='0.5em' {...props} />}",
                    "ul": "{UnorderedList}",
                    "ol": "{OrderedList}",
                    "li": "{ListItem}",
                    "p": "{({node, ...props}) => <Text paddingY='0.5em' {...props} />}",
                    "a": "{Link}",
                    "code": """{({node, inline, className, children, ...props}) =>
                    {
        const match = (className || '').match(/language-(?<lang>.*)/);
        return !inline ? (
          <Prism
            children={String(children).replace(/\n$/, '')}
            language={match ? match[1] : ''}
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
            )
        )
