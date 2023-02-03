"""Markdown component."""

import textwrap
from typing import List, Union

from pynecone import utils
from pynecone.components.component import Component
from pynecone.var import BaseVar, Var


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown"

    tag = "ReactMarkdown"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a markdown component.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The markdown component.
        """
        assert len(children) == 1 and utils._isinstance(
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
            "Heading",
            "Code",
            "Text",
            "Link",
            "UnorderedList",
            "OrderedList",
            "ListItem",
        }
        imports["react-syntax-highlighter"] = {"Prism"}
        imports["remark-math"] = {"remarkMath"}
        imports["remark-gfm"] = {"remarkGfm"}
        imports["rehype-katex"] = {"rehypeKatex"}
        imports["rehype-raw"] = {"rehypeRaw"}
        imports[""] = {"katex/dist/katex.min.css"}
        return imports

    def _render(self):
        return (
            super()
            ._render()
            .add_props(
                components={
                    "h1": "{({node, ...props}) => <Heading size='2xl' {...props} />}",
                    "h2": "{({node, ...props}) => <Heading size='xl' {...props} />}",
                    "h3": "{({node, ...props}) => <Heading size='lg' {...props} />}",
                    "ul": "{UnorderedList}",
                    "ol": "{OrderedList}",
                    "li": "{ListItem}",
                    "p": "{Text}",
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
