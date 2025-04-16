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
    "fn_body, fn_args, explicit_return, expected",
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
    "key,component_map, expected",
    [
        (
            "code",
            {},
            r"""(({node, inline, className, children, ...props}) => { const match = (className || '').match(/language-(?<lang>.*)/); let _language = match ? match[1] : '';   if (_language) {     if (!["abap", "abnf", "actionscript", "ada", "agda", "al", "antlr4", "apacheconf", "apex", "apl", "applescript", "aql", "arduino", "arff", "asciidoc", "asm6502", "asmatmel", "aspnet", "autohotkey", "autoit", "avisynth", "avro-idl", "bash", "basic", "batch", "bbcode", "bicep", "birb", "bison", "bnf", "brainfuck", "brightscript", "bro", "bsl", "c", "cfscript", "chaiscript", "cil", "clike", "clojure", "cmake", "cobol", "coffeescript", "concurnas", "coq", "core", "cpp", "crystal", "csharp", "cshtml", "csp", "css", "css-extras", "csv", "cypher", "d", "dart", "dataweave", "dax", "dhall", "diff", "django", "dns-zone-file", "docker", "dot", "ebnf", "editorconfig", "eiffel", "ejs", "elixir", "elm", "erb", "erlang", "etlua", "excel-formula", "factor", "false", "firestore-security-rules", "flow", "fortran", "fsharp", "ftl", "gap", "gcode", "gdscript", "gedcom", "gherkin", "git", "glsl", "gml", "gn", "go", "go-module", "graphql", "groovy", "haml", "handlebars", "haskell", "haxe", "hcl", "hlsl", "hoon", "hpkp", "hsts", "http", "ichigojam", "icon", "icu-message-format", "idris", "iecst", "ignore", "index", "inform7", "ini", "io", "j", "java", "javadoc", "javadoclike", "javascript", "javastacktrace", "jexl", "jolie", "jq", "js-extras", "js-templates", "jsdoc", "json", "json5", "jsonp", "jsstacktrace", "jsx", "julia", "keepalived", "keyman", "kotlin", "kumir", "kusto", "latex", "latte", "less", "lilypond", "liquid", "lisp", "livescript", "llvm", "log", "lolcode", "lua", "magma", "makefile", "markdown", "markup", "markup-templating", "matlab", "maxscript", "mel", "mermaid", "mizar", "mongodb", "monkey", "moonscript", "n1ql", "n4js", "nand2tetris-hdl", "naniscript", "nasm", "neon", "nevod", "nginx", "nim", "nix", "nsis", "objectivec", "ocaml", "opencl", "openqasm", "oz", "parigp", "parser", "pascal", "pascaligo", "pcaxis", "peoplecode", "perl", "php", "php-extras", "phpdoc", "plsql", "powerquery", "powershell", "processing", "prolog", "promql", "properties", "protobuf", "psl", "pug", "puppet", "pure", "purebasic", "purescript", "python", "q", "qml", "qore", "qsharp", "r", "racket", "reason", "regex", "rego", "renpy", "rest", "rip", "roboconf", "robotframework", "ruby", "rust", "sas", "sass", "scala", "scheme", "scss", "shell-session", "smali", "smalltalk", "smarty", "sml", "solidity", "solution-file", "soy", "sparql", "splunk-spl", "sqf", "sql", "squirrel", "stan", "stylus", "swift", "systemd", "t4-cs", "t4-templating", "t4-vb", "tap", "tcl", "textile", "toml", "tremor", "tsx", "tt2", "turtle", "twig", "typescript", "typoscript", "unrealscript", "uorazor", "uri", "v", "vala", "vbnet", "velocity", "verilog", "vhdl", "vim", "visual-basic", "warpscript", "wasm", "web-idl", "wiki", "wolfram", "wren", "xeora", "xml-doc", "xojo", "xquery", "yaml", "yang", "zig"].includes(_language)) {         console.warn(`Language \`${_language}\` is not supported for code blocks inside of markdown.`);         _language = '';     } else {          (async () => {     try {         const module = await import(`react-syntax-highlighter/dist/cjs/languages/prism/${_language}`);         SyntaxHighlighter.registerLanguage(_language, module.default);     } catch (error) {         console.error(`Language ${_language} is not supported for code blocks inside of markdown: `, error);     } })();      }   }  ;             return inline ? (                 <RadixThemesCode {...props}>{children}</RadixThemesCode>             ) : (                 <SyntaxHighlighter children={((Array.isArray(children)) ? children.join("\n") : children)} css={({ ["marginTop"] : "1em", ["marginBottom"] : "1em" })} customStyle={({ ["marginTop"] : "1em", ["marginBottom"] : "1em" })} language={_language} style={((resolvedColorMode === "light") ? oneLight : oneDark)} wrapLongLines={true} {...props}/>             );         })""",
        ),
        (
            "code",
            {
                "codeblock": lambda value, **props: ShikiHighLevelCodeBlock.create(
                    value, **props
                )
            },
            r"""(({node, inline, className, children, ...props}) => { const match = (className || '').match(/language-(?<lang>.*)/); let _language = match ? match[1] : '';  ;             return inline ? (                 <RadixThemesCode {...props}>{children}</RadixThemesCode>             ) : (                 <RadixThemesBox css={({ ["pre"] : ({ ["margin"] : "0", ["padding"] : "24px", ["background"] : "transparent", ["overflowX"] : "auto", ["borderRadius"] : "6px" }) })} {...props}><ShikiCode code={((Array.isArray(children)) ? children.join("\n") : children)} decorations={[]} language={_language} theme={((resolvedColorMode === "light") ? "one-light" : "one-dark-pro")} transformers={[]}/></RadixThemesBox>             );         })""",
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
            r"""(({node, inline, className, children, ...props}) => { const match = (className || '').match(/language-(?<lang>.*)/); let _language = match ? match[1] : '';   if (_language) {     if (!["abap", "abnf", "actionscript", "ada", "agda", "al", "antlr4", "apacheconf", "apex", "apl", "applescript", "aql", "arduino", "arff", "asciidoc", "asm6502", "asmatmel", "aspnet", "autohotkey", "autoit", "avisynth", "avro-idl", "bash", "basic", "batch", "bbcode", "bicep", "birb", "bison", "bnf", "brainfuck", "brightscript", "bro", "bsl", "c", "cfscript", "chaiscript", "cil", "clike", "clojure", "cmake", "cobol", "coffeescript", "concurnas", "coq", "core", "cpp", "crystal", "csharp", "cshtml", "csp", "css", "css-extras", "csv", "cypher", "d", "dart", "dataweave", "dax", "dhall", "diff", "django", "dns-zone-file", "docker", "dot", "ebnf", "editorconfig", "eiffel", "ejs", "elixir", "elm", "erb", "erlang", "etlua", "excel-formula", "factor", "false", "firestore-security-rules", "flow", "fortran", "fsharp", "ftl", "gap", "gcode", "gdscript", "gedcom", "gherkin", "git", "glsl", "gml", "gn", "go", "go-module", "graphql", "groovy", "haml", "handlebars", "haskell", "haxe", "hcl", "hlsl", "hoon", "hpkp", "hsts", "http", "ichigojam", "icon", "icu-message-format", "idris", "iecst", "ignore", "index", "inform7", "ini", "io", "j", "java", "javadoc", "javadoclike", "javascript", "javastacktrace", "jexl", "jolie", "jq", "js-extras", "js-templates", "jsdoc", "json", "json5", "jsonp", "jsstacktrace", "jsx", "julia", "keepalived", "keyman", "kotlin", "kumir", "kusto", "latex", "latte", "less", "lilypond", "liquid", "lisp", "livescript", "llvm", "log", "lolcode", "lua", "magma", "makefile", "markdown", "markup", "markup-templating", "matlab", "maxscript", "mel", "mermaid", "mizar", "mongodb", "monkey", "moonscript", "n1ql", "n4js", "nand2tetris-hdl", "naniscript", "nasm", "neon", "nevod", "nginx", "nim", "nix", "nsis", "objectivec", "ocaml", "opencl", "openqasm", "oz", "parigp", "parser", "pascal", "pascaligo", "pcaxis", "peoplecode", "perl", "php", "php-extras", "phpdoc", "plsql", "powerquery", "powershell", "processing", "prolog", "promql", "properties", "protobuf", "psl", "pug", "puppet", "pure", "purebasic", "purescript", "python", "q", "qml", "qore", "qsharp", "r", "racket", "reason", "regex", "rego", "renpy", "rest", "rip", "roboconf", "robotframework", "ruby", "rust", "sas", "sass", "scala", "scheme", "scss", "shell-session", "smali", "smalltalk", "smarty", "sml", "solidity", "solution-file", "soy", "sparql", "splunk-spl", "sqf", "sql", "squirrel", "stan", "stylus", "swift", "systemd", "t4-cs", "t4-templating", "t4-vb", "tap", "tcl", "textile", "toml", "tremor", "tsx", "tt2", "turtle", "twig", "typescript", "typoscript", "unrealscript", "uorazor", "uri", "v", "vala", "vbnet", "velocity", "verilog", "vhdl", "vim", "visual-basic", "warpscript", "wasm", "web-idl", "wiki", "wolfram", "wren", "xeora", "xml-doc", "xojo", "xquery", "yaml", "yang", "zig"].includes(_language)) {         console.warn(`Language \`${_language}\` is not supported for code blocks inside of markdown.`);         _language = '';     } else {          (async () => {     try {         const module = await import(`react-syntax-highlighter/dist/cjs/languages/prism/${_language}`);         SyntaxHighlighter.registerLanguage(_language, module.default);     } catch (error) {         console.error(`Language ${_language} is not supported for code blocks inside of markdown: `, error);     } })();      }   }  ;             return inline ? (                 <RadixThemesCode {...props}>{children}</RadixThemesCode>             ) : (                 <CodeBlock code={((Array.isArray(children)) ? children.join("\n") : children)} language={_language} {...props}/>             );         })""",
        ),
        (
            "code",
            {
                "codeblock": syntax_highlighter_memoized_component(
                    ShikiHighLevelCodeBlock
                )
            },
            r"""(({node, inline, className, children, ...props}) => { const match = (className || '').match(/language-(?<lang>.*)/); let _language = match ? match[1] : '';  ;             return inline ? (                 <RadixThemesCode {...props}>{children}</RadixThemesCode>             ) : (                 <CodeBlock code={((Array.isArray(children)) ? children.join("\n") : children)} language={_language} {...props}/>             );         })""",
        ),
    ],
)
def test_markdown_format_component(key, component_map, expected):
    markdown = Markdown.create("# header", component_map=component_map)
    result = markdown.format_component_map()
    print(str(result[key]))
    assert str(result[key]) == expected
