from typing import Type

import pytest

from reflex.components.component import Component, memo
from reflex.components.datadisplay.code import CodeBlock
from reflex.components.datadisplay.shiki_code_block import ShikiHighLevelCodeBlock
from reflex.components.markdown.markdown import Markdown, MarkdownComponentMap
from reflex.components.radix.themes.layout.box import Box
from reflex.components.radix.themes.typography.heading import Heading
from reflex.vars.base import Var


class CustomMarkdownComponent(Component, MarkdownComponentMap):
    """A custom markdown component."""

    tag = "CustomMarkdownComponent"
    library = "custom"

    @classmethod
    def get_fn_args(cls) -> list[str]:
        """Return the function arguments.

        Returns:
            The function arguments.
        """
        return ["custom_node", "custom_children", "custom_props"]

    @classmethod
    def get_fn_body(cls) -> str:
        """Return the function body.

        Returns:
            The function body.
        """
        return "{return custom_node + custom_children + custom_props;}"


def syntax_highlighter_memoized_component(codeblock: Type[Component]):
    @memo
    def code_block(code: str, language: str):
        return Box.create(
            codeblock.create(
                code,
                language=language,
                class_name="code-block",
                can_copy=True,
            ),
            class_name="relative mb-4",
        )

    def code_block_markdown(*children, **props):
        return code_block(
            code=children[0], language=props.pop("language", "plain"), **props
        )

    return code_block_markdown


@pytest.mark.parametrize(
    "fn_body, fn_args, expected",
    [
        (None, None, Var(_js_expr="(({node, children, ...props}) => ())")),
        ("{return node;}", ["node"], Var(_js_expr="(({node}) => {return node;})")),
        (
            "{return node + children;}",
            ["node", "children"],
            Var(_js_expr="(({node, children}) => {return node + children;})"),
        ),
        (
            "{return node + props;}",
            ["node", "...props"],
            Var(_js_expr="(({node, ...props}) => {return node + props;})"),
        ),
        (
            "{return node + children + props;}",
            ["node", "children", "...props"],
            Var(
                _js_expr="(({node, children, ...props}) => {return node + children + props;})"
            ),
        ),
    ],
)
def test_create_map_fn_var(fn_body, fn_args, expected):
    result = MarkdownComponentMap.create_map_fn_var(fn_body, fn_args)
    assert result._js_expr == expected._js_expr


@pytest.mark.parametrize(
    "cls, fn_body, fn_args, expected",
    [
        (
            MarkdownComponentMap,
            None,
            None,
            Var(_js_expr="(({node, children, ...props}) => ())"),
        ),
        (
            MarkdownComponentMap,
            "{return node};",
            ["node"],
            Var(_js_expr="(({node}) => {return node};)"),
        ),
        (
            CustomMarkdownComponent,
            None,
            None,
            Var(
                _js_expr="(({custom_node, custom_children, custom_props}) => {return custom_node + custom_children + custom_props;})"
            ),
        ),
        (
            CustomMarkdownComponent,
            "{return custom_node;}",
            ["custom_node"],
            Var(_js_expr="(({custom_node}) => {return custom_node;})"),
        ),
    ],
)
def test_create_map_fn_var_subclass(cls, fn_body, fn_args, expected):
    result = cls.create_map_fn_var(fn_body, fn_args)
    assert result._js_expr == expected._js_expr


@pytest.mark.parametrize(
    "key,component_map, expected",
    [
        (
            "code",
            {},
            """(({node, inline, className, children, ...props}) => { const match = (className || '').match(/language-(?<lang>.*)/); const _language = match ? match[1] : '';   if (_language) {     (async () => {       try {         const module = await import(`react-syntax-highlighter/dist/cjs/languages/prism/${_language}`);         SyntaxHighlighter.registerLanguage(_language, module.default);       } catch (error) {         console.error(`Error importing language module for ${_language}:`, error);       }     })();   }   ;             return inline ? (                 <RadixThemesCode {...props}>{children}</RadixThemesCode>             ) : (                 <SyntaxHighlighter children={((Array.isArray(children)) ? children.join("\\n") : children)} css={({ ["marginTop"] : "1em", ["marginBottom"] : "1em" })} customStyle={({ ["marginTop"] : "1em", ["marginBottom"] : "1em" })} language={_language} style={((resolvedColorMode === "light") ? oneLight : oneDark)} wrapLongLines={true} {...props}/>             );         })""",
        ),
        (
            "code",
            {
                "codeblock": lambda value, **props: ShikiHighLevelCodeBlock.create(
                    value, **props
                )
            },
            """(({node, inline, className, children, ...props}) => {;             return inline ? (                 <RadixThemesCode {...props}>{children}</RadixThemesCode>             ) : (                 <RadixThemesBox css={({ ["pre"] : ({ ["margin"] : "0", ["padding"] : "24px", ["background"] : "transparent", ["overflow-x"] : "auto", ["border-radius"] : "6px" }) })} {...props}><ShikiCode code={((Array.isArray(children)) ? children.join("\\n") : children)} decorations={[]} language={_language} theme={((resolvedColorMode === "light") ? "one-light" : "one-dark-pro")} transformers={[]}/></RadixThemesBox>             );         })""",
        ),
        (
            "h1",
            {
                "h1": lambda value: CustomMarkdownComponent.create(
                    Heading.create(value, as_="h1", size="6", margin_y="0.5em")
                )
            },
            """(({custom_node, custom_children, custom_props}) => (<CustomMarkdownComponent {...props}><RadixThemesHeading as={"h1"} css={({ ["marginTop"] : "0.5em", ["marginBottom"] : "0.5em" })} size={"6"}>{children}</RadixThemesHeading></CustomMarkdownComponent>))""",
        ),
        (
            "code",
            {"codeblock": syntax_highlighter_memoized_component(CodeBlock)},
            """(({node, inline, className, children, ...props}) => { const match = (className || '').match(/language-(?<lang>.*)/); const _language = match ? match[1] : '';   if (_language) {     (async () => {       try {         const module = await import(`react-syntax-highlighter/dist/cjs/languages/prism/${_language}`);         SyntaxHighlighter.registerLanguage(_language, module.default);       } catch (error) {         console.error(`Error importing language module for ${_language}:`, error);       }     })();   }   ;             return inline ? (                 <RadixThemesCode {...props}>{children}</RadixThemesCode>             ) : (                 <CodeBlock code={((Array.isArray(children)) ? children.join("\\n") : children)} language={_language} {...props}/>             );         })""",
        ),
        (
            "code",
            {
                "codeblock": syntax_highlighter_memoized_component(
                    ShikiHighLevelCodeBlock
                )
            },
            """(({node, inline, className, children, ...props}) => {;             return inline ? (                 <RadixThemesCode {...props}>{children}</RadixThemesCode>             ) : (                 <CodeBlock code={((Array.isArray(children)) ? children.join("\\n") : children)} language={_language} {...props}/>             );         })""",
        ),
    ],
)
def test_markdown_format_component(key, component_map, expected):
    markdown = Markdown.create("# header", component_map=component_map)
    result = markdown.format_component_map()
    assert str(result[key]) == expected
