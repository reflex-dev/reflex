"""Components that are based on Chakra-UI."""
from __future__ import annotations

from typing import List, Literal

from reflex.components.component import Component
from reflex.utils import imports
from reflex.vars import ImportVar, Var


class ChakraComponent(Component):
    """A component that wraps a Chakra component."""

    library = "@chakra-ui/react@2.6.1"
    lib_dependencies: List[str] = [
        "@chakra-ui/system@2.5.7",
        "framer-motion@10.16.4",
    ]

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            **super()._get_app_wrap_components(),
            (60, "ChakraProvider"): ChakraProvider.create(),
        }


class Global(Component):
    """The emotion/react Global styling component."""

    library = "@emotion/react@^11.11.0"
    lib_dependencies: List[str] = [
        "@emotion/styled@^11.11.0",
    ]

    tag = "Global"

    styles: Var[str]


class ChakraProvider(ChakraComponent):
    """Top level Chakra provider must be included in any app using chakra components."""

    tag = "ChakraProvider"

    theme: Var[str]

    @classmethod
    def create(cls) -> Component:
        """Create a new ChakraProvider component.

        Returns:
            A new ChakraProvider component.
        """
        return super().create(
            Global.create(styles=Var.create("GlobalStyles", _var_is_local=False)),
            theme=Var.create("extendTheme(theme)", _var_is_local=False),
        )

    def _get_imports(self) -> imports.ImportDict:
        imports = super()._get_imports()
        imports.setdefault(self.__fields__["library"].default, set()).add(
            ImportVar(tag="extendTheme", is_default=False),
        )
        imports.setdefault("/utils/theme.js", set()).add(
            ImportVar(tag="theme", is_default=True),
        )
        imports.setdefault(Global.__fields__["library"].default, set()).add(
            ImportVar(tag="css", is_default=False),
        )
        return imports

    def _get_custom_code(self) -> str | None:
        return """
import '/styles/styles.css'

const GlobalStyles = css`
  /* Hide the blue border around Chakra components. */
  .js-focus-visible :focus:not([data-focus-visible-added]) {
    outline: none;
    box-shadow: none;
  }
`;
"""

    def _get_app_wrap_components(self) -> dict[tuple[int, str], Component]:
        return {
            (50, "ChakraColorModeProvider"): ChakraColorModeProvider.create(),
        }


class ChakraColorModeProvider(Component):
    """Next-themes integration for chakra colorModeProvider."""

    library = "/components/reflex/chakra_color_mode_provider.js"
    tag = "ChakraColorModeProvider"
    is_default = True


LiteralColorScheme = Literal[
    "none",
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "teal",
    "blue",
    "cyan",
    "purple",
    "pink",
    "whiteAlpha",
    "blackAlpha",
    "linkedin",
    "facebook",
    "messenger",
    "whatsapp",
    "twitter",
    "telegram",
]


LiteralVariant = Literal["solid", "subtle", "outline"]
LiteralDividerVariant = Literal["solid", "dashed"]
LiteralTheme = Literal["light", "dark"]
LiteralCodeBlockTheme = Literal[
    "a11y-dark",
    "atom-dark",
    "cb",
    "coldark-cold",
    "coldark-dark",
    "coy",
    "coy-without-shadows",
    "darcula",
    "dark",
    "dracula",
    "duotone-dark",
    "duotone-earth",
    "duotone-forest",
    "duotone-light",
    "duotone-sea",
    "duotone-space",
    "funky",
    "ghcolors",
    "gruvbox-dark",
    "gruvbox-light",
    "holi-theme",
    "hopscotch",
    "light",  # not present in react-syntax-highlighter styles
    "lucario",
    "material-dark",
    "material-light",
    "material-oceanic",
    "night-owl",
    "nord",
    "okaidia",
    "one-dark",
    "one-light",
    "pojoaque",
    "prism",
    "shades-of-purple",
    "solarized-dark-atom",
    "solarizedlight",
    "synthwave84",
    "tomorrow",
    "twilight",
    "vs",
    "vs-dark",
    "vsc-dark-plus",
    "xonokai",
    "z-touch",
]


LiteralTagColorScheme = Literal[
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "teal",
    "blue",
    "cyan",
    "purple",
    "pink",
]
LiteralTagAlign = Literal["center", "end", "start"]
LiteralTabsVariant = Literal[
    "line",
    "enclosed",
    "enclosed-colored",
    "soft-rounded",
    "solid-rounded",
    "unstyled",
]

LiteralStatus = Literal["success", "info", "warning", "error"]
LiteralAlertVariant = Literal["subtle", "left-accent", "top-accent", "solid"]
LiteralButtonVariant = Literal["ghost", "outline", "solid", "link", "unstyled"]
LiteralSpinnerPlacement = Literal["start", "end"]
LiteralLanguage = Literal[
    "en",
    "da",
    "de",
    "es",
    "fr",
    "ja",
    "ko",
    "pt_br",
    "ru",
    "zh_cn",
    "ro",
    "pl",
    "ckb",
    "lv",
    "se",
    "ua",
    "he",
    "it",
]
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
LiteralInputVariant = Literal["outline", "filled", "flushed", "unstyled"]
LiteralInputNumberMode = [
    "text",
    "search",
    "none",
    "tel",
    "url",
    "email",
    "numeric",
    "decimal",
]
LiteralChakraDirection = Literal["ltr", "rtl"]
LiteralCardVariant = Literal["outline", "filled", "elevated", "unstyled"]
LiteralStackDirection = Literal["row", "column"]
LiteralImageLoading = Literal["eager", "lazy"]
LiteralTagSize = Literal["sm", "md", "lg"]
LiteralSpinnerSize = Literal[Literal[LiteralTagSize], "xs", "xl"]
LiteralAvatarSize = Literal[Literal[LiteralTagSize], "xl", "xs", "2xl", "full", "2xs"]
LiteralButtonSize = Literal["sm", "md", "lg", "xs"]
# Applies to AlertDialog and Modal
LiteralAlertDialogSize = Literal[
    "sm", "md", "lg", "xs", "2xl", "full", "3xl", "4xl", "5xl", "6xl"
]
LiteralDrawerSize = Literal[Literal[LiteralSpinnerSize], "xl", "full"]

LiteralMenuStrategy = Literal["fixed", "absolute"]
LiteralMenuOption = Literal["checkbox", "radio"]
LiteralPopOverTrigger = Literal["click", "hover"]

LiteralHeadingSize = Literal["lg", "md", "sm", "xs", "xl", "2xl", "3xl", "4xl"]
