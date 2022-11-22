"""Table components."""

from typing import List

from pynecone import utils
from pynecone.components.component import Component
from pynecone.var import BaseVar, Var


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown"

    tag = "ReactMarkdown"

    src: Var[str]

    def _get_custom_code(self) -> str:
        return "import 'katex/dist/katex.min.css'"

    def _get_imports(self):
        imports = super()._get_imports()
        imports["@chakra-ui/react"] = {"Heading", "Code", "Text", "Link"}
        imports["react-syntax-highlighter"] = {"Prism"}
        imports["remark-math"] = {"remarkMath"}
        imports["remark-gfm"] = {"remarkGfm"}
        imports["rehype-katex"] = {"rehypeKatex"}
        return imports

    def _render(self):
        tag = super()._render()
        return tag.add_props(
            children=utils.wrap(str(self.src).strip(), "`"),
            components={
                "h1": "{({node, ...props}) => <Heading size='2xl' {...props} />}",
                "h2": "{({node, ...props}) => <Heading size='xl' {...props} />}",
                "h3": "{({node, ...props}) => <Heading size='lg' {...props} />}",
                "p": "{Text}",
                "a": "{Link}",
                # "code": "{Code}"
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
            rehype_plugins=BaseVar(name="[rehypeKatex]", type_=List[str]),
            src="",
        )
