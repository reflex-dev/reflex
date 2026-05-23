import pytest
from reflex_base.components.component import Component, memo
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext
from reflex_base.vars.base import Var
from reflex_components_code.code import CodeBlock
from reflex_components_code.shiki_code_block import ShikiHighLevelCodeBlock
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.core.markdown_component_map import MarkdownComponentMap
from reflex_components_markdown.markdown import Markdown
from reflex_components_radix.themes.layout.box import Box
from reflex_components_radix.themes.typography.heading import Heading

import reflex as rx
from reflex.compiler import compiler
from reflex.compiler.plugins import default_page_plugins


class CustomMarkdownComponent(Component, MarkdownComponentMap):
    """A custom markdown component."""

    tag = "CustomMarkdownComponent"
    library = "custom"

    @classmethod
    def get_fn_args(cls) -> tuple[str, ...]:
        """Return the function arguments.

        Returns:
            The function arguments.
        """
        return ("custom_node", "custom_children", "custom_props")

    @classmethod
    def get_fn_body(cls) -> Var:
        """Return the function body.

        Returns:
            The function body.
        """
        return Var(_js_expr="{return custom_node + custom_children + custom_props}")


def syntax_highlighter_memoized_component(codeblock: type[Component]):
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
    ("fn_body", "fn_args", "explicit_return", "expected"),
    [
        (
            None,
            None,
            False,
            Var(_js_expr="(({node, children, ...props}) => undefined)"),
        ),
        ("return node", ("node",), True, Var(_js_expr="(({node}) => {return node})")),
        (
            "return node + children",
            ("node", "children"),
            True,
            Var(_js_expr="(({node, children}) => {return node + children})"),
        ),
        (
            "return node + props",
            ("node", "...props"),
            True,
            Var(_js_expr="(({node, ...props}) => {return node + props})"),
        ),
        (
            "return node + children + props",
            ("node", "children", "...props"),
            True,
            Var(
                _js_expr="(({node, children, ...props}) => {return node + children + props})"
            ),
        ),
    ],
)
def test_create_map_fn_var(fn_body, fn_args, explicit_return, expected):
    result = MarkdownComponentMap.create_map_fn_var(
        fn_body=Var(_js_expr=fn_body, _var_type=str) if fn_body else None,
        fn_args=fn_args,
        explicit_return=explicit_return,
    )
    assert result._js_expr == expected._js_expr


@pytest.mark.parametrize(
    ("cls", "fn_body", "fn_args", "explicit_return", "expected"),
    [
        (
            MarkdownComponentMap,
            None,
            None,
            False,
            Var(_js_expr="(({node, children, ...props}) => undefined)"),
        ),
        (
            MarkdownComponentMap,
            "return node",
            ("node",),
            True,
            Var(_js_expr="(({node}) => {return node})"),
        ),
        (
            CustomMarkdownComponent,
            None,
            None,
            True,
            Var(
                _js_expr="(({custom_node, custom_children, custom_props}) => {return custom_node + custom_children + custom_props})"
            ),
        ),
        (
            CustomMarkdownComponent,
            "return custom_node",
            ("custom_node",),
            True,
            Var(_js_expr="(({custom_node}) => {return custom_node})"),
        ),
    ],
)
def test_create_map_fn_var_subclass(cls, fn_body, fn_args, explicit_return, expected):
    result = cls.create_map_fn_var(
        fn_body=Var(_js_expr=fn_body, _var_type=int) if fn_body else None,
        fn_args=fn_args,
        explicit_return=explicit_return,
    )
    assert result._js_expr == expected._js_expr


@pytest.mark.parametrize(
    ("key", "component_map", "expected"),
    [
        (
            "code",
            {},
            r"""(({node, children, ...props}) => (jsx(RadixThemesCode,{...props},children)))""",
        ),
        (
            "pre",
            {
                "pre": lambda value, **props: ShikiHighLevelCodeBlock.create(
                    value, **props
                )
            },
            r"""(({node, ...rest}) => { const {node: childNode, className, children: components, ...props} = rest.children.props; const children = String(Array.isArray(components) ? components.join('\n') : components).replace(/\n$/, ''); const match = (className || '').match(/language-(?<lang>.*)/); let _language = match ? match[1] : ''; ;             return jsx(RadixThemesBox,{css:({ ["pre"] : ({ ["margin"] : "0", ["padding"] : "24px", ["background"] : "transparent", ["overflowX"] : "auto", ["borderRadius"] : "6px" }) }),...props},jsx(ShikiCode,{code:children,decorations:[],language:_language,theme:((resolvedColorMode?.valueOf?.() === "light"?.valueOf?.()) ? "one-light" : "one-dark-pro"),transformers:[]},));         })""",
        ),
        (
            "h1",
            {
                "h1": lambda value: CustomMarkdownComponent.create(
                    Heading.create(value, as_="h1", size="6", margin_y="0.5em")
                )
            },
            """(({custom_node, custom_children, custom_props}) => (jsx(CustomMarkdownComponent,{...props},jsx(RadixThemesHeading,{as:"h1",css:({ ["marginTop"] : "0.5em", ["marginBottom"] : "0.5em" }),size:"6"},children))))""",
        ),
        (
            "pre",
            {"pre": syntax_highlighter_memoized_component(CodeBlock)},
            r"""(({node, ...rest}) => { const {node: childNode, className, children: components, ...props} = rest.children.props; const children = String(Array.isArray(components) ? components.join('\n') : components).replace(/\n$/, ''); const match = (className || '').match(/language-(?<lang>.*)/); let _language = match ? match[1] : ''; ;             return jsx(CodeBlock,{code:children,language:_language,...props},);         })""",
        ),
        (
            "pre",
            {"pre": syntax_highlighter_memoized_component(ShikiHighLevelCodeBlock)},
            r"""(({node, ...rest}) => { const {node: childNode, className, children: components, ...props} = rest.children.props; const children = String(Array.isArray(components) ? components.join('\n') : components).replace(/\n$/, ''); const match = (className || '').match(/language-(?<lang>.*)/); let _language = match ? match[1] : ''; ;             return jsx(CodeBlock,{code:children,language:_language,...props},);         })""",
        ),
    ],
)
def test_markdown_format_component(key, component_map, expected):
    markdown = Markdown.create("# header", component_map=component_map)
    result = markdown.format_component_map()
    print(str(result[key]))
    assert str(result[key]) == expected


def _compile_page_output(root: Component) -> str:
    """Compile ``root`` through the full page pipeline and return the JSX.

    The result includes any per-memo wrapper modules emitted alongside the
    page, so callers can match against JSX wherever the auto-memoize plugin
    chose to place it.

    Reaches into compiler internals (``CompileContext.auto_memo_components``,
    ``compiler.compile_page_from_context``, ``compiler.compile_memo_components``)
    because no public driver returns the combined page+memo JSX text. If those
    APIs are renamed, update here.

    Args:
        root: The page root component to compile.

    Returns:
        The combined page-module JSX plus each per-memo module's JSX.
    """
    page_ctx = PageContext(name="page", route="/page", root_component=root)
    hooks = CompilerHooks(plugins=default_page_plugins())
    compile_ctx = CompileContext(pages=[], hooks=hooks)

    with compile_ctx, page_ctx:
        page_ctx.root_component = hooks.compile_component(
            page_ctx.root_component,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )
        hooks.compile_page(page_ctx, compile_context=compile_ctx)
        _, page_code = compiler.compile_page_from_context(page_ctx)
        memo_files, _ = compiler.compile_memo_components(
            (), compile_ctx.auto_memo_components.values()
        )
    return "\n".join([page_code, *(code for _, code in memo_files)])


class MarkdownVarChildRegressionState(rx.State):
    """Module-scope state for the Var-child regression test.

    Defined at module scope (not inside the test function) so the state
    registry keys this class by a stable ``module.MarkdownVarChildRegressionState``
    full name, avoiding re-registration leaks under pytest-repeat or duplicate
    test collection.
    """

    some_text: str = "hello"


def test_markdown_var_child_inlined_not_wrapped():
    """``rx.markdown(State.var)`` must inline the Var as the JSX child.

    ``react-markdown`` asserts its ``children`` prop is a string. Without the
    snapshot-boundary wrapper on ``Markdown``, the auto-memoize plugin hoists
    the Bare(state-Var) child into its own ``Bare_comp_<hash>`` React element,
    which renders as ``[object Object]`` at runtime.
    """
    root = Fragment.create(Markdown.create(MarkdownVarChildRegressionState.some_text))
    output = _compile_page_output(root)

    assert "jsx(ReactMarkdown" in output
    assert "Bare_comp_" not in output, (
        "Markdown Var child was wrapped in a Bare_comp_<hash> memoized "
        f"component; ReactMarkdown requires a string child.\nOutput:\n{output}"
    )
    assert "some_text_rx_state_" in output
