"""Table components."""

from typing import List

from pynecone import utils
from pynecone.components.component import Component
from pynecone.var import BaseVar, Var


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown"

    tag = "ReactMarkdown"

    # The source of the markdown.
    src: Var[str]

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
        tag = super()._render()
        return tag.add_props(
            children=utils.wrap(str(self.src).strip(), "`"),
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
            rehype_plugins=BaseVar(name="[rehypeKatex, rehypeRaw]", type_=List[str]),
            src="",
        )
