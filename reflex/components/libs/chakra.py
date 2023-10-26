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
    "colddark-cold",
    "coldark-dark",
    "coy",
    "coy-without-shadow",
    "darcula",
    "dark",
    "dracula",
    "duotone",
    "duotone-earth",
    "duotone-forest",
    "duotone-light",
    "duotone-sea",
    "duotone-space",
    "funky",
    "ghcolors",
    "gruvbox-dark",
    "holi-theme",
    "hopscotch",
    "light",
    "lucario",
    "material-dark",
    "material-light",
    "material-oceanic",
    "night-owl",
    "nord",
    "okaidia",
    "prism",
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
    "io",
    "ebnf",
    "javadoclike",
    "iecst",
    "gdscript",
    "bash",
    "mongodb",
    "rest",
    "batch",
    "xml-doc",
    "haml",
    "typoscript",
    "vhdl",
    "systemd",
    "bsl",
    "markup-templating",
    "robotframework",
    "prolog",
    "jsx",
    "cfscript",
    "powershell",
    "moonscript",
    "liquid",
    "warpscript",
    "perl",
    "typescript",
    "mermaid",
    "cshtml",
    "cmake",
    "aspnet",
    "hoon",
    "pure",
    "smalltalk",
    "cpp",
    "docker",
    "stan",
    "lilypond",
    "verilog",
    "markup",
    "shell-session",
    "smarty",
    "visual-basic",
    "bicep",
    "js-templates",
    "n4js",
    "erb",
    "pug",
    "supported-languages",
    "renpy",
    "al",
    "csp",
    "dart",
    "excel-formula",
    "d",
    "flow",
    "sass",
    "matlab",
    "jsstacktrace",
    "ruby",
    "core",
    "chaiscript",
    "dhall",
    "fsharp",
    "abnf",
    "livescript",
    "graphql",
    "git",
    "sml",
    "crystal",
    "apex",
    "firestore-security-rules",
    "css-extras",
    "web-idl",
    "avro-idl",
    "sas",
    "solution-file",
    "gherkin",
    "uorazor",
    "sparql",
    "java",
    "objectivec",
    "squirrel",
    "glsl",
    "javadoc",
    "applescript",
    "ada",
    "icon",
    "kumir",
    "wolfram",
    "arff",
    "qsharp",
    "asmatmel",
    "lua",
    "xeora",
    "django",
    "rip",
    "lisp",
    "xquery",
    "properties",
    "j",
    "log",
    "solidity",
    "tsx",
    "cobol",
    "index",
    "r",
    "ejs",
    "tt2",
    "gml",
    "psl",
    "antlr4",
    "wren",
    "nix",
    "handlebars",
    "neon",
    "maxscript",
    "avisynth",
    "t4-vb",
    "erlang",
    "v",
    "hsts",
    "mizar",
    "ocaml",
    "hcl",
    "powerquery",
    "abap",
    "fortran",
    "racket",
    "elm",
    "tremor",
    "haskell",
    "splunk-spl",
    "bnf",
    "latex",
    "julia",
    "ichigojam",
    "javascript",
    "q",
    "nevod",
    "n1ql",
    "keepalived",
    "textile",
    "latte",
    "nsis",
    "phpdoc",
    "qml",
    "protobuf",
    "xojo",
    "pcaxis",
    "dot",
    "jexl",
    "php-extras",
    "less",
    "json5",
    "bison",
    "processing",
    "asciidoc",
    "oz",
    "php",
    "ini",
    "sql",
    "promql",
    "vbnet",
    "gap",
    "ftl",
    "dns-zone-file",
    "toml",
    "hpkp",
    "editorconfig",
    "nand2tetris-hdl",
    "scala",
    "qore",
    "purebasic",
    "rust",
    "groovy",
    "peoplecode",
    "etlua",
    "arduino",
    "t4-templating",
    "gcode",
    "purescript",
    "scheme",
    "magma",
    "autoit",
    "autohotkey",
    "yang",
    "haxe",
    "clojure",
    "cypher",
    "regex",
    "brainfuck",
    "naniscript",
    "agda",
    "zig",
    "plsql",
    "wiki",
    "concurnas",
    "js-extras",
    "velocity",
    "json",
    "icu-message-format",
    "csharp",
    "c",
    "tcl",
    "jolie",
    "birb",
    "tap",
    "eiffel",
    "stylus",
    "clike",
    "basic",
    "pascaligo",
    "wasm",
    "elixir",
    "nginx",
    "idris",
    "twig",
    "ignore",
    "t4-cs",
    "nim",
    "inform7",
    "roboconf",
    "cil",
    "css",
    "smali",
    "brightscript",
    "kusto",
    "jsonp",
    "yaml",
    "go-module",
    "pascal",
    "sqf",
    "turtle",
    "vala",
    "nasm",
    "llvm",
    "false",
    "jsdoc",
    "coffeescript",
    "parser",
    "reason",
    "jq",
    "coq",
    "gn",
    "hlsl",
    "dataweave",
    "keyman",
    "kotlin",
    "javastacktrace",
    "apacheconf",
    "soy",
    "diff",
    "factor",
    "unrealscript",
    "bbcode",
    "makefile",
    "monkey",
    "python",
    "vim",
    "go",
    "apl",
    "asm6502",
    "http",
    "csv",
    "actionscript",
    "swift",
    "rego",
    "opencl",
    "lolcode",
    "puppet",
    "openqasm",
    "markdown",
    "gedcom",
    "dax",
    "scss",
    "aql",
    "mel",
    "parigp",
    "uri",
    "bro",
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
