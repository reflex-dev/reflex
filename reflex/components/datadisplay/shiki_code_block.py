"""Shiki syntax hghlighter component."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from reflex.base import Base
from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.cond import color_mode_cond
from reflex.components.lucide.icon import Icon
from reflex.components.radix.themes.components.button import Button
from reflex.components.radix.themes.layout.box import Box
from reflex.event import set_clipboard
from reflex.style import Style
from reflex.utils.imports import ImportDict, ImportVar
from reflex.vars.base import LiteralVar, Var
from reflex.vars.function import FunctionStringVar

SHIKIJS_TRANSFORMER_FNS = {
    "transformerNotationDiff",
    "transformerNotationHighlight",
    "transformerNotationWordHighlight",
    "transformerNotationFocus",
    "transformerNotationErrorLevel",
    "transformerRenderWhitespace",
    "transformerMetaHighlight",
    "transformerMetaWordHighlight",
    "transformerCompactLineOptions",
    # TODO: this transformer when included adds a weird behavior which removes other code lines. Need to figure out why.
    # "transformerRemoveLineBreak",
    "transformerRemoveNotationEscape",
}
LINE_NUMBER_STYLING = {
    "code": {"counter-reset": "step", "counter-increment": "step 0"},
    "code .line::before": {
        "content": "counter(step)",
        "counter-increment": "step",
        "width": "1rem",
        "margin-right": "1.5rem",
        "display": "inline-block",
        "text-align": "right",
        "color": "rgba(115,138,148,.4)",
    },
}

THEME_MAPPING = {"light": "one-light", "dark": "one-dark-pro"}
LiteralCodeLanguage = Literal[
    "abap",
    "actionscript-3",
    "ada",
    "angular-html",
    "angular-ts",
    "apache",
    "apex",
    "apl",
    "applescript",
    "ara",
    "asciidoc",
    "asm",
    "astro",
    "awk",
    "ballerina",
    "bat",
    "beancount",
    "berry",
    "bibtex",
    "bicep",
    "blade",
    "c",
    "cadence",
    "clarity",
    "clojure",
    "cmake",
    "cobol",
    "codeowners",
    "codeql",
    "coffee",
    "common-lisp",
    "coq",
    "cpp",
    "crystal",
    "csharp",
    "css",
    "csv",
    "cue",
    "cypher",
    "d",
    "dart",
    "dax",
    "desktop",
    "diff",
    "docker",
    "dotenv",
    "dream-maker",
    "edge",
    "elixir",
    "elm",
    "emacs-lisp",
    "erb",
    "erlang",
    "fennel",
    "fish",
    "fluent",
    "fortran-fixed-form",
    "fortran-free-form",
    "fsharp",
    "gdresource",
    "gdscript",
    "gdshader",
    "genie",
    "gherkin",
    "git-commit",
    "git-rebase",
    "gleam",
    "glimmer-js",
    "glimmer-ts",
    "glsl",
    "gnuplot",
    "go",
    "graphql",
    "groovy",
    "hack",
    "haml",
    "handlebars",
    "haskell",
    "haxe",
    "hcl",
    "hjson",
    "hlsl",
    "html",
    "html-derivative",
    "http",
    "hxml",
    "hy",
    "imba",
    "ini",
    "java",
    "javascript",
    "jinja",
    "jison",
    "json",
    "json5",
    "jsonc",
    "jsonl",
    "jsonnet",
    "jssm",
    "jsx",
    "julia",
    "kotlin",
    "kusto",
    "latex",
    "lean",
    "less",
    "liquid",
    "log",
    "logo",
    "lua",
    "luau",
    "make",
    "markdown",
    "marko",
    "matlab",
    "mdc",
    "mdx",
    "mermaid",
    "mojo",
    "move",
    "narrat",
    "nextflow",
    "nginx",
    "nim",
    "nix",
    "nushell",
    "objective-c",
    "objective-cpp",
    "ocaml",
    "pascal",
    "perl",
    "php",
    "plsql",
    "po",
    "postcss",
    "powerquery",
    "powershell",
    "prisma",
    "prolog",
    "proto",
    "pug",
    "puppet",
    "purescript",
    "python",
    "qml",
    "qmldir",
    "qss",
    "r",
    "racket",
    "raku",
    "razor",
    "reg",
    "regexp",
    "rel",
    "riscv",
    "rst",
    "ruby",
    "rust",
    "sas",
    "sass",
    "scala",
    "scheme",
    "scss",
    "shaderlab",
    "shellscript",
    "shellsession",
    "smalltalk",
    "solidity",
    "soy",
    "sparql",
    "splunk",
    "sql",
    "ssh-config",
    "stata",
    "stylus",
    "svelte",
    "swift",
    "system-verilog",
    "systemd",
    "tasl",
    "tcl",
    "templ",
    "terraform",
    "tex",
    "toml",
    "ts-tags",
    "tsv",
    "tsx",
    "turtle",
    "twig",
    "typescript",
    "typespec",
    "typst",
    "v",
    "vala",
    "vb",
    "verilog",
    "vhdl",
    "viml",
    "vue",
    "vue-html",
    "vyper",
    "wasm",
    "wenyan",
    "wgsl",
    "wikitext",
    "wolfram",
    "xml",
    "xsl",
    "yaml",
    "zenscript",
    "zig",
]
LiteralCodeTheme = Literal[
    "andromeeda",
    "aurora-x",
    "ayu-dark",
    "catppuccin-frappe",
    "catppuccin-latte",
    "catppuccin-macchiato",
    "catppuccin-mocha",
    "dark-plus",
    "dracula",
    "dracula-soft",
    "everforest-dark",
    "everforest-light",
    "github-dark",
    "github-dark-default",
    "github-dark-dimmed",
    "github-dark-high-contrast",
    "github-light",
    "github-light-default",
    "github-light-high-contrast",
    "houston",
    "laserwave",
    "light-plus",
    "material-theme",
    "material-theme-darker",
    "material-theme-lighter",
    "material-theme-ocean",
    "material-theme-palenight",
    "min-dark",
    "min-light",
    "monokai",
    "night-owl",
    "nord",
    "one-dark-pro",
    "one-light",
    "plastic",
    "poimandres",
    "red",
    "rose-pine",
    "rose-pine-dawn",
    "rose-pine-moon",
    "slack-dark",
    "slack-ochin",
    "snazzy-light",
    "solarized-dark",
    "solarized-light",
    "synthwave-84",
    "tokyo-night",
    "vesper",
    "vitesse-black",
    "vitesse-dark",
    "vitesse-light",
]


class ShikiBaseTransformers(Base):
    """Base for creating transformers."""

    library: str
    fns: list[FunctionStringVar]
    style: Style | None


class ShikiJsTransformer(ShikiBaseTransformers):
    """A Wrapped shikijs transformer."""

    library: str = "@shikijs/transformers"
    fns: list[FunctionStringVar] = [
        FunctionStringVar.create(fn) for fn in SHIKIJS_TRANSFORMER_FNS
    ]
    style: Style | None = Style(
        {
            ".line": {"display": "inline", "padding-bottom": "0"},
            ".diff": {
                "display": "inline-block",
                "width": "100vw",
                "margin": "0 -12px",
                "padding": "0 12px",
            },
            ".diff.add": {"background-color": "#0505"},
            ".diff.remove": {"background-color": "#8005"},
            ".diff:before": {"position": "absolute", "left": "40px"},
            ".has-focused .line": {"filter": "blur(0.095rem)"},
            ".has-focused .focused": {"filter": "blur(0)"},
        }
    )

    def __init__(self, **kwargs):
        """Initialize the transformer.

        Args:
            kwargs: Kwargs to initialize the props.

        """
        fns = kwargs.pop("fns", None)
        style = kwargs.pop("style", None)
        if fns:
            kwargs["fns"] = [
                FunctionStringVar.create(x)
                if not isinstance(x, FunctionStringVar)
                else x
                for x in fns
            ]

        if style:
            kwargs["style"] = Style(style)
        super().__init__(**kwargs)


class ShikiCodeBlock(Component):
    """A Code block."""

    library = "/components/shiki/code"
    tag = "Code"
    alias = "ShikiCode"

    # The language to use.
    language: Var[LiteralCodeLanguage] = Var.create("python")

    # The theme to use ("light" or "dark").
    theme: Var[LiteralCodeTheme] = Var.create("one-light")

    # The set of themes to use for different modes.
    themes: Var[list[dict[str, Any]] | dict[str, str]]

    # The code to display.
    code: Var[str]

    # The transformers to use for the syntax highlighter.
    transformers: Var[list[ShikiBaseTransformers | dict[str, Any]]] = []

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
        """Create a code block component using [shiki syntax highlighter](https://shiki.matsu.io/).

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The code block component.
        """
        # Separate props for the code block and the wrapper
        code_block_props = {}
        code_wrapper_props = {}

        class_props = cls.get_props()

        # Distribute props between the code block and wrapper
        for key, value in props.items():
            (code_block_props if key in class_props else code_wrapper_props)[key] = (
                value
            )

        code_block_props["code"] = children[0]
        code_block = super().create(**code_block_props)

        transformer_styles = {}
        # Collect styles from transformers and wrapper
        for transformer in code_block.transformers._var_value:
            if isinstance(transformer, ShikiBaseTransformers) and transformer.style:
                transformer_styles.update(transformer.style)
        transformer_styles.update(code_wrapper_props.pop("style", {}))

        return Box.create(
            code_block,
            *children[1:],
            style=Style(transformer_styles),
            **code_wrapper_props,
        )

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add the necessary imports.
        We add all referenced transformer functions as imports from their corresponding
        libraries.

        Returns:
            Imports for the component.
        """
        imports = defaultdict(list)
        for transformer in self.transformers._var_value:
            if isinstance(transformer, ShikiBaseTransformers):
                imports[transformer.library].extend(
                    [ImportVar(tag=str(fn)) for fn in transformer.fns]
                )
                self.lib_dependencies.append(
                    transformer.library
                ) if transformer.library not in self.lib_dependencies else None
        return imports

    @classmethod
    def create_transformer(cls, library: str, fns: list[str]) -> ShikiBaseTransformers:
        """Create a transformer from a third party library.

        Args:
            library: The name of the library.
            fns: The str names of the functions/callables to invoke from the library.

        Returns:
            A transformer for the specified library.

        Raises:
            ValueError: If a supplied function name is not valid str.
        """
        if any(not isinstance(fn_name, str) for fn_name in fns):
            raise ValueError(
                f"the function names should be str names of functions in the specified transformer: {library!r}"
            )
        return ShikiBaseTransformers(
            library=library, fns=[FunctionStringVar.create(fn) for fn in fns]
        )

    def _render(self, props: dict[str, Any] | None = None):
        """Renders the component with the given properties, processing transformers if present.

        Args:
            props: Optional properties to pass to the render function.

        Returns:
            Rendered component output.
        """
        # Ensure props is initialized from class attributes if not provided
        props = props or {
            attr.rstrip("_"): getattr(self, attr) for attr in self.get_props()
        }

        # Extract transformers and apply transformations
        transformers = props.get("transformers")
        if transformers is not None:
            transformed_values = self._process_transformers(transformers._var_value)
            props["transformers"] = LiteralVar.create(transformed_values)

        return super()._render(props)

    def _process_transformers(self, transformer_list: list) -> list:
        """Processes a list of transformers, applying transformations where necessary.

        Args:
            transformer_list: List of transformer objects or values.

        Returns:
            list: A list of transformed values.
        """
        processed = []

        for transformer in transformer_list:
            if isinstance(transformer, ShikiBaseTransformers):
                processed.extend(fn.call() for fn in transformer.fns)
            else:
                processed.append(transformer)

        return processed


class ShikiHighLevelCodeBlock(ShikiCodeBlock):
    """High level component for the shiki syntax highlighter."""

    # If this is enabled, the default transformer(shikijs transformer) will be used.
    use_transformer: Var[bool] = False

    # If this is enabled line numbers will be shown next to the code block.
    show_line_numbers: Var[bool]

    @classmethod
    def create(
        cls,
        *children,
        can_copy: bool | None = False,
        copy_button: bool | Component | None = None,
        **props,
    ) -> Component:
        """Create a code block component using [shiki syntax highlighter](https://shiki.matsu.io/).

        Args:
            *children: The children of the component.
            can_copy: Whether a copy button should appear.
            copy_button: A custom copy button to override the default one.
            **props: The props to pass to the component.

        Returns:
            The code block component.
        """
        use_transformer = props.pop("use_transformer", False)
        show_line_numbers = props.pop("show_line_numbers", False)

        if use_transformer:
            props["transformers"] = [ShikiJsTransformer()]

        if show_line_numbers:
            line_style = LINE_NUMBER_STYLING.copy()
            line_style.update(props.get("style", {}))
            props["style"] = line_style

        theme = props.pop("theme", None)
        props["theme"] = props["theme"] = (
            cls._map_themes(theme)
            if theme
            else color_mode_cond(  # Default color scheme responds to global color mode.
                light="one-light",
                dark="one-dark-pro",
            )
        )

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

        if copy_button:
            return ShikiCodeBlock.create(
                children[0], copy_button, position="relative", **props
            )
        else:
            return ShikiCodeBlock.create(children[0], **props)

    @staticmethod
    def _map_themes(theme: str) -> str:
        if isinstance(theme, str) and theme in THEME_MAPPING:
            return THEME_MAPPING[theme]
        return theme


class TransformerNamespace(ComponentNamespace):
    """Namespace for the Transformers."""

    shikijs = ShikiJsTransformer


class CodeblockNamespace(ComponentNamespace):
    """Namespace for the CodeBlock component."""

    root = staticmethod(ShikiCodeBlock.create)
    create_transformer = staticmethod(ShikiCodeBlock.create_transformer)
    transformers = TransformerNamespace()
    __call__ = staticmethod(ShikiHighLevelCodeBlock.create)


code_block = CodeblockNamespace()
