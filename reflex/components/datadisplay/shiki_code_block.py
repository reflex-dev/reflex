from collections import defaultdict
from typing import Any, Literal, Optional, Union

from reflex.components.component import Component
from reflex.components.lucide.icon import Icon
from reflex.components.radix.themes.components.button import Button
from reflex.components.radix.themes.layout.box import Box
from reflex.event import set_clipboard
from reflex.style import Style
from reflex.utils.imports import ImportDict, ImportVar
from reflex.vars.base import Var
from reflex.vars.function import FunctionStringVar

COMMON_TRANSFORMERS = {
    "transformerNotationDiff",
    "transformerNotationHighlight",
    "transformerNotationWordHighlight",
    "transformerNotationFocus",
    "transformerNotationErrorLevel",
    "transformerRenderWhitespace",
    "transformerMetaHighlight",
    "transformerMetaWordHighlight",
    "transformerCompactLineOptions",
    "transformerRemoveLineBreak",
    "transformerRemoveNotationEscape",
}
LiteralCodeLanguage = Literal[
    "ts",
    "abap",
    "abnf",
    "actionscript",
    "ada",
    "agda",
    "al",
    "antlr4",
    "apacheconf",
    "apex",
    "apl",
    "applescript",
    "aql",
    "arduino",
    "arff",
    "asciidoc",
    "asm6502",
    "asmatmel",
    "aspnet",
    "autohotkey",
    "autoit",
    "avisynth",
    "avro-idl",
    "bash",
    "basic",
    "batch",
    "bbcode",
    "bicep",
    "birb",
    "bison",
    "bnf",
    "brainfuck",
    "brightscript",
    "bro",
    "bsl",
    "c",
    "cfscript",
    "chaiscript",
    "cil",
    "clike",
    "clojure",
    "cmake",
    "cobol",
    "coffeescript",
    "concurnas",
    "coq",
    "core",
    "cpp",
    "crystal",
    "csharp",
    "cshtml",
    "csp",
    "css",
    "css-extras",
    "csv",
    "cypher",
    "d",
    "dart",
    "dataweave",
    "dax",
    "dhall",
    "diff",
    "django",
    "dns-zone-file",
    "docker",
    "dot",
    "ebnf",
    "editorconfig",
    "eiffel",
    "ejs",
    "elixir",
    "elm",
    "erb",
    "erlang",
    "etlua",
    "excel-formula",
    "factor",
    "false",
    "firestore-security-rules",
    "flow",
    "fortran",
    "fsharp",
    "ftl",
    "gap",
    "gcode",
    "gdscript",
    "gedcom",
    "gherkin",
    "git",
    "glsl",
    "gml",
    "gn",
    "go",
    "go-module",
    "graphql",
    "groovy",
    "haml",
    "handlebars",
    "haskell",
    "haxe",
    "hcl",
    "hlsl",
    "hoon",
    "hpkp",
    "hsts",
    "http",
    "ichigojam",
    "icon",
    "icu-message-format",
    "idris",
    "iecst",
    "ignore",
    "index",
    "inform7",
    "ini",
    "io",
    "j",
    "java",
    "javadoc",
    "javadoclike",
    "javascript",
    "javastacktrace",
    "jexl",
    "jolie",
    "jq",
    "js-extras",
    "js-templates",
    "jsdoc",
    "json",
    "json5",
    "jsonp",
    "jsstacktrace",
    "jsx",
    "julia",
    "keepalived",
    "keyman",
    "kotlin",
    "kumir",
    "kusto",
    "latex",
    "latte",
    "less",
    "lilypond",
    "liquid",
    "lisp",
    "livescript",
    "llvm",
    "log",
    "lolcode",
    "lua",
    "magma",
    "makefile",
    "markdown",
    "markup",
    "markup-templating",
    "matlab",
    "maxscript",
    "mel",
    "mermaid",
    "mizar",
    "mongodb",
    "monkey",
    "moonscript",
    "n1ql",
    "n4js",
    "nand2tetris-hdl",
    "naniscript",
    "nasm",
    "neon",
    "nevod",
    "nginx",
    "nim",
    "nix",
    "nsis",
    "objectivec",
    "ocaml",
    "opencl",
    "openqasm",
    "oz",
    "parigp",
    "parser",
    "pascal",
    "pascaligo",
    "pcaxis",
    "peoplecode",
    "perl",
    "php",
    "php-extras",
    "phpdoc",
    "plsql",
    "powerquery",
    "powershell",
    "processing",
    "prolog",
    "promql",
    "properties",
    "protobuf",
    "psl",
    "pug",
    "puppet",
    "pure",
    "purebasic",
    "purescript",
    "python",
    "q",
    "qml",
    "qore",
    "qsharp",
    "r",
    "racket",
    "reason",
    "regex",
    "rego",
    "renpy",
    "rest",
    "rip",
    "roboconf",
    "robotframework",
    "ruby",
    "rust",
    "sas",
    "sass",
    "scala",
    "scheme",
    "scss",
    "shell-session",
    "smali",
    "smalltalk",
    "smarty",
    "sml",
    "solidity",
    "solution-file",
    "soy",
    "sparql",
    "splunk-spl",
    "sqf",
    "sql",
    "squirrel",
    "stan",
    "stylus",
    "swift",
    "systemd",
    "t4-cs",
    "t4-templating",
    "t4-vb",
    "tap",
    "tcl",
    "textile",
    "toml",
    "tremor",
    "tsx",
    "tt2",
    "turtle",
    "twig",
    "typescript",
    "typoscript",
    "unrealscript",
    "uorazor",
    "uri",
    "v",
    "vala",
    "vbnet",
    "velocity",
    "verilog",
    "vhdl",
    "vim",
    "visual-basic",
    "warpscript",
    "wasm",
    "web-idl",
    "wiki",
    "wolfram",
    "wren",
    "xeora",
    "xml-doc",
    "xojo",
    "xquery",
    "yaml",
    "yang",
    "zig",
]


class ShikiCodeBlock(Component):
    library = "/utils/code"
    tag = "Code"
    alias = "ShikiCode"
    language: Var[LiteralCodeLanguage] = "python"
    theme: Var[str] = "min-dark"
    themes: Var[list[dict[str, Any]] | dict[str, str]]
    code: Var[str]
    transformers: Var[list] = []

    @classmethod
    def create(
        cls,
        *children,
        can_copy: Optional[bool] = False,
        copy_button: Optional[Union[bool, Component]] = None,
        **props,
    ) -> Component:
        props["code"] = children[0]

        if can_copy:
            code = children[0]
            copy_button = (  # type: ignore
                copy_button
                if copy_button is not None
                else Button.create(
                    Icon.create(tag="copy"),
                    on_click=set_clipboard(code),
                    style=Style({"position": "absolute", "top": "0.5em", "right": "0"}),
                )
            )
        else:
            copy_button = None

        transformers = props.pop("transformers", [])
        trans_final = []
        for transformer in transformers:
            if transformer in COMMON_TRANSFORMERS:
                trans_final.append(FunctionStringVar(f"{transformer}()"))
            else:
                trans_final.append(transformer)

        if trans_final:
            props["transformers"] = trans_final

        code_block = super().create(**props)

        if copy_button:
            return Box.create(code_block, copy_button, position="relative")
        else:
            return code_block

    def add_imports(self) -> ImportDict | list[ImportDict]:
        imports = defaultdict(list)
        for transformer in self.transformers._var_value:
            if (
                isinstance(transformer, FunctionStringVar)
                and (transformer_import_str := str(transformer).strip("()"))
                in COMMON_TRANSFORMERS
            ):
                imports["@shikijs/transformers"].append(
                    ImportVar(tag=transformer_import_str)
                )
                self.lib_dependencies.append(
                    "@shikijs/transformers"
                ) if "@shikijs/transformers" not in self.lib_dependencies else None

        return imports


code_block = ShikiCodeBlock.create
