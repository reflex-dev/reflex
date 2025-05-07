"""A code component."""

from __future__ import annotations

import dataclasses
import typing
from typing import ClassVar, Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.cond import color_mode_cond
from reflex.components.lucide.icon import Icon
from reflex.components.markdown.markdown import _LANGUAGE, MarkdownComponentMap
from reflex.components.radix.themes.components.button import Button
from reflex.components.radix.themes.layout.box import Box
from reflex.constants.colors import Color
from reflex.event import set_clipboard
from reflex.style import Style
from reflex.utils import format
from reflex.utils.imports import ImportVar
from reflex.vars.base import LiteralVar, Var, VarData

LiteralCodeLanguage = Literal[
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


def construct_theme_var(theme: str) -> Var[Theme]:
    """Construct a theme var.

    Args:
        theme: The theme to construct.

    Returns:
        The constructed theme var.
    """
    return Var(
        theme,
        _var_data=VarData(
            imports={
                f"react-syntax-highlighter/dist/cjs/styles/prism/{format.to_kebab_case(theme)}": [
                    ImportVar(tag=theme, is_default=True, install=False)
                ]
            }
        ),
    )


@dataclasses.dataclass(init=False)
class Theme:
    """Themes for the CodeBlock component."""

    a11y_dark: ClassVar[Var[Theme]] = construct_theme_var("a11yDark")
    atom_dark: ClassVar[Var[Theme]] = construct_theme_var("atomDark")
    cb: ClassVar[Var[Theme]] = construct_theme_var("cb")
    coldark_cold: ClassVar[Var[Theme]] = construct_theme_var("coldarkCold")
    coldark_dark: ClassVar[Var[Theme]] = construct_theme_var("coldarkDark")
    coy: ClassVar[Var[Theme]] = construct_theme_var("coy")
    coy_without_shadows: ClassVar[Var[Theme]] = construct_theme_var("coyWithoutShadows")
    darcula: ClassVar[Var[Theme]] = construct_theme_var("darcula")
    dark: ClassVar[Var[Theme]] = construct_theme_var("oneDark")
    dracula: ClassVar[Var[Theme]] = construct_theme_var("dracula")
    duotone_dark: ClassVar[Var[Theme]] = construct_theme_var("duotoneDark")
    duotone_earth: ClassVar[Var[Theme]] = construct_theme_var("duotoneEarth")
    duotone_forest: ClassVar[Var[Theme]] = construct_theme_var("duotoneForest")
    duotone_light: ClassVar[Var[Theme]] = construct_theme_var("duotoneLight")
    duotone_sea: ClassVar[Var[Theme]] = construct_theme_var("duotoneSea")
    duotone_space: ClassVar[Var[Theme]] = construct_theme_var("duotoneSpace")
    funky: ClassVar[Var[Theme]] = construct_theme_var("funky")
    ghcolors: ClassVar[Var[Theme]] = construct_theme_var("ghcolors")
    gruvbox_dark: ClassVar[Var[Theme]] = construct_theme_var("gruvboxDark")
    gruvbox_light: ClassVar[Var[Theme]] = construct_theme_var("gruvboxLight")
    holi_theme: ClassVar[Var[Theme]] = construct_theme_var("holiTheme")
    hopscotch: ClassVar[Var[Theme]] = construct_theme_var("hopscotch")
    light: ClassVar[Var[Theme]] = construct_theme_var("oneLight")
    lucario: ClassVar[Var[Theme]] = construct_theme_var("lucario")
    material_dark: ClassVar[Var[Theme]] = construct_theme_var("materialDark")
    material_light: ClassVar[Var[Theme]] = construct_theme_var("materialLight")
    material_oceanic: ClassVar[Var[Theme]] = construct_theme_var("materialOceanic")
    night_owl: ClassVar[Var[Theme]] = construct_theme_var("nightOwl")
    nord: ClassVar[Var[Theme]] = construct_theme_var("nord")
    okaidia: ClassVar[Var[Theme]] = construct_theme_var("okaidia")
    one_dark: ClassVar[Var[Theme]] = construct_theme_var("oneDark")
    one_light: ClassVar[Var[Theme]] = construct_theme_var("oneLight")
    pojoaque: ClassVar[Var[Theme]] = construct_theme_var("pojoaque")
    prism: ClassVar[Var[Theme]] = construct_theme_var("prism")
    shades_of_purple: ClassVar[Var[Theme]] = construct_theme_var("shadesOfPurple")
    solarized_dark_atom: ClassVar[Var[Theme]] = construct_theme_var("solarizedDarkAtom")
    solarizedlight: ClassVar[Var[Theme]] = construct_theme_var("solarizedlight")
    synthwave84: ClassVar[Var[Theme]] = construct_theme_var("synthwave84")
    tomorrow: ClassVar[Var[Theme]] = construct_theme_var("tomorrow")
    twilight: ClassVar[Var[Theme]] = construct_theme_var("twilight")
    vs: ClassVar[Var[Theme]] = construct_theme_var("vs")
    vs_dark: ClassVar[Var[Theme]] = construct_theme_var("vsDark")
    vsc_dark_plus: ClassVar[Var[Theme]] = construct_theme_var("vscDarkPlus")
    xonokai: ClassVar[Var[Theme]] = construct_theme_var("xonokai")
    z_touch: ClassVar[Var[Theme]] = construct_theme_var("zTouch")


for theme_name in dir(Theme):
    if theme_name.startswith("_"):
        continue
    setattr(Theme, theme_name, getattr(Theme, theme_name)._replace(_var_type=Theme))


class CodeBlock(Component, MarkdownComponentMap):
    """A code block."""

    library = "react-syntax-highlighter@15.6.1"

    tag = "PrismAsyncLight"

    alias = "SyntaxHighlighter"

    # The theme to use ("light" or "dark").
    theme: Var[Theme | str] = Theme.one_light

    # The language to use.
    language: Var[LiteralCodeLanguage] = Var.create("python")

    # The code to display.
    code: Var[str]

    # If this is enabled line numbers will be shown next to the code block.
    show_line_numbers: Var[bool]

    # The starting line number to use.
    starting_line_number: Var[int]

    # Whether to wrap long lines.
    wrap_long_lines: Var[bool]

    # A custom style for the code block.
    custom_style: dict[str, str | Var | Color] = {}

    # Props passed down to the code tag.
    code_tag_props: Var[dict[str, str]]

    # Whether a copy button should appear.
    can_copy: bool | None = False

    # A custom copy button to override the default one.
    copy_button: bool | Component | None = None

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ):
        """Create a text component.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The text component.
        """
        # This component handles style in a special prop.
        custom_style = props.pop("custom_style", {})
        can_copy = props.pop("can_copy", False)
        copy_button = props.pop("copy_button", None)

        # react-syntax-highlighter doesn't have an explicit "light" or "dark" theme so we use one-light and one-dark
        # themes respectively to ensure code compatibility.
        if "theme" not in props:
            # Default color scheme responds to global color mode.
            props["theme"] = color_mode_cond(
                light=Theme.one_light,
                dark=Theme.one_dark,
            )

        if can_copy:
            code = children[0]
            copy_button = (
                copy_button
                if copy_button is not None
                else Button.create(
                    Icon.create(tag="copy"),
                    on_click=set_clipboard(code),
                    style=Style({"position": "absolute", "top": "0.5em", "right": "0"}),
                )
            )
            custom_style.update({"padding": "1em 3.2em 1em 1em"})
        else:
            copy_button = None

        # Transfer style props to the custom style prop.
        for key, value in props.items():
            if key not in cls.get_fields():
                custom_style[key] = value

        # Carry the children (code) via props
        if children:
            props["code"] = children[0]
            if not isinstance(props["code"], Var):
                props["code"] = LiteralVar.create(props["code"])

        # Create the component.
        code_block = super().create(
            **props,
            custom_style=Style(custom_style),
        )

        if copy_button:
            return Box.create(code_block, copy_button, position="relative")
        else:
            return code_block

    def add_style(self):
        """Add style to the component."""
        self.custom_style.update(self.style)

    def _render(self):
        out = super()._render()

        theme = self.theme

        out.add_props(style=theme).remove_props("theme", "code").add_props(
            children=self.code,
        )

        return out

    def _exclude_props(self) -> list[str]:
        return ["can_copy", "copy_button"]

    @classmethod
    def _get_language_registration_hook(cls, language_var: Var = _LANGUAGE) -> Var:
        """Get the hook to register the language.

        Args:
            language_var: The const/literal Var of the language module to import.
                For markdown, uses the default placeholder _LANGUAGE. For direct use,
                a LiteralStringVar should be passed via the language prop.

        Returns:
            The hook to register the language.
        """
        language_in_there = Var.create(typing.get_args(LiteralCodeLanguage)).contains(
            language_var
        )
        async_load = f"""
(async () => {{
    try {{
        const module = await import(`react-syntax-highlighter/dist/cjs/languages/prism/${{{language_var!s}}}`);
        SyntaxHighlighter.registerLanguage({language_var!s}, module.default);
    }} catch (error) {{
        console.error(`Language ${{{language_var!s}}} is not supported for code blocks inside of markdown: `, error);
    }}
}})();
"""
        return Var(
            f"""
 if ({language_var!s}) {{
    if (!{language_in_there!s}) {{
        console.warn(`Language \\`${{{language_var!s}}}\\` is not supported for code blocks inside of markdown.`);
        {language_var!s} = '';
    }} else {{
        {async_load!s}
    }}
  }}
"""
            if not isinstance(language_var, LiteralVar)
            else f"""
if ({language_var!s}) {{
    {async_load!s}
}}""",
            _var_data=VarData(
                imports={
                    cls.__fields__["library"].default: [
                        ImportVar(tag="PrismAsyncLight", alias="SyntaxHighlighter")
                    ]
                },
            ),
        )

    @classmethod
    def get_component_map_custom_code(cls) -> Var:
        """Get the custom code for the component.

        Returns:
            The custom code for the component.
        """
        return cls._get_language_registration_hook()

    def add_hooks(self) -> list[str | Var]:
        """Add hooks for the component.

        Returns:
            The hooks for the component.
        """
        return [
            self._get_language_registration_hook(language_var=self.language),
        ]


class CodeblockNamespace(ComponentNamespace):
    """Namespace for the CodeBlock component."""

    themes = Theme

    __call__ = CodeBlock.create


code_block = CodeblockNamespace()
