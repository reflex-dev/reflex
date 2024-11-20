"""Shiki syntax hghlighter component."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Literal, Optional, Union

from reflex.base import Base
from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.colors import color
from reflex.components.core.cond import color_mode_cond
from reflex.components.el.elements.forms import Button
from reflex.components.lucide.icon import Icon
from reflex.components.markdown.markdown import MarkdownComponentMap
from reflex.components.props import NoExtrasAllowedProps
from reflex.components.radix.themes.layout.box import Box
from reflex.event import run_script, set_clipboard
from reflex.style import Style
from reflex.utils.exceptions import VarTypeError
from reflex.utils.imports import ImportVar
from reflex.vars.base import LiteralVar, Var
from reflex.vars.function import FunctionStringVar
from reflex.vars.sequence import StringVar, string_replace_operation


def copy_script() -> Any:
    """Copy script for the code block and modify the child SVG element.

    Returns:
        Any: The result of calling the script.
    """
    return run_script(
        """
// Event listener for the parent click
document.addEventListener('click', function(event) {
    // Find the closest button (parent element)
    const parent = event.target.closest('button');
    // If the parent is found
    if (parent) {
        // Find the SVG element within the parent
        const svgIcon = parent.querySelector('svg');
        // If the SVG exists, proceed with the script
        if (svgIcon) {
            const originalPath = svgIcon.innerHTML;
            const checkmarkPath = '<polyline points="20 6 9 17 4 12"></polyline>';  // Checkmark SVG path
            function transition(element, scale, opacity) {
                element.style.transform = `scale(${scale})`;
                element.style.opacity = opacity;
            }
            // Animate the SVG
            transition(svgIcon, 0, '0');
            setTimeout(() => {
                svgIcon.innerHTML = checkmarkPath;  // Replace content with checkmark
                svgIcon.setAttribute('viewBox', '0 0 24 24');  // Adjust viewBox if necessary
                transition(svgIcon, 1, '1');
                setTimeout(() => {
                    transition(svgIcon, 0, '0');
                    setTimeout(() => {
                        svgIcon.innerHTML = originalPath;  // Restore original SVG content
                        transition(svgIcon, 1, '1');
                    }, 125);
                }, 600);
            }, 125);
        } else {
            // console.error('SVG element not found within the parent.');
        }
    } else {
        // console.error('Parent element not found.');
    }
})
"""
    )


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
    "code": {
        "counter-reset": "step",
        "counter-increment": "step 0",
        "display": "grid",
        "line-height": "1.7",
        "font-size": "0.875em",
    },
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
BOX_PARENT_STYLING = {
    "pre": {
        "margin": "0",
        "padding": "24px",
        "background": "transparent",
        "overflow-x": "auto",
        "border-radius": "6px",
    },
}

THEME_MAPPING = {
    "light": "one-light",
    "dark": "one-dark-pro",
    "a11y-dark": "github-dark",
}
LANGUAGE_MAPPING = {"bash": "shellscript"}
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
    "plain",
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
    # rose-pine themes dont work with the current version of shikijs transformers
    # https://github.com/shikijs/shiki/issues/730
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


class Position(NoExtrasAllowedProps):
    """Position of the decoration."""

    line: int
    character: int


class ShikiDecorations(NoExtrasAllowedProps):
    """Decorations for the code block."""

    start: Union[int, Position]
    end: Union[int, Position]
    tag_name: str = "span"
    properties: dict[str, Any] = {}
    always_wrap: bool = False


class ShikiBaseTransformers(Base):
    """Base for creating transformers."""

    library: str
    fns: list[FunctionStringVar]
    style: Optional[Style]


class ShikiJsTransformer(ShikiBaseTransformers):
    """A Wrapped shikijs transformer."""

    library: str = "@shikijs/transformers"
    fns: list[FunctionStringVar] = [
        FunctionStringVar.create(fn) for fn in SHIKIJS_TRANSFORMER_FNS
    ]
    style: Optional[Style] = Style(
        {
            "code": {"line-height": "1.7", "font-size": "0.875em", "display": "grid"},
            # Diffs
            ".diff": {
                "margin": "0 -24px",
                "padding": "0 24px",
                "width": "calc(100% + 48px)",
                "display": "inline-block",
            },
            ".diff.add": {
                "background-color": "rgba(16, 185, 129, .14)",
                "position": "relative",
            },
            ".diff.remove": {
                "background-color": "rgba(244, 63, 94, .14)",
                "opacity": "0.7",
                "position": "relative",
            },
            ".diff.remove:after": {
                "position": "absolute",
                "left": "10px",
                "content": "'-'",
                "color": "#b34e52",
            },
            ".diff.add:after": {
                "position": "absolute",
                "left": "10px",
                "content": "'+'",
                "color": "#18794e",
            },
            # Highlight
            ".highlighted": {
                "background-color": "rgba(142, 150, 170, .14)",
                "margin": "0 -24px",
                "padding": "0 24px",
                "width": "calc(100% + 48px)",
                "display": "inline-block",
            },
            ".highlighted.error": {
                "background-color": "rgba(244, 63, 94, .14)",
            },
            ".highlighted.warning": {
                "background-color": "rgba(234, 179, 8, .14)",
            },
            # Highlighted Word
            ".highlighted-word": {
                "background-color": color("gray", 2),
                "border": f"1px solid {color('gray', 5)}",
                "padding": "1px 3px",
                "margin": "-1px -3px",
                "border-radius": "4px",
            },
            # Focused Lines
            ".has-focused .line:not(.focused)": {
                "opacity": "0.7",
                "filter": "blur(0.095rem)",
                "transition": "filter .35s, opacity .35s",
            },
            ".has-focused:hover .line:not(.focused)": {
                "opacity": "1",
                "filter": "none",
            },
            # White Space
            # ".tab, .space": {
            #     "position": "relative",
            # },
            # ".tab::before": {
            #     "content": "'⇥'",
            #     "position": "absolute",
            #     "opacity": "0.3",
            # },
            # ".space::before": {
            #     "content": "'·'",
            #     "position": "absolute",
            #     "opacity": "0.3",
            # },
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
                (
                    FunctionStringVar.create(x)
                    if not isinstance(x, FunctionStringVar)
                    else x
                )
                for x in fns
            ]

        if style:
            kwargs["style"] = Style(style)
        super().__init__(**kwargs)


class ShikiCodeBlock(Component, MarkdownComponentMap):
    """A Code block."""

    library = "/components/shiki/code"

    tag = "Code"

    alias = "ShikiCode"

    lib_dependencies: list[str] = ["shiki"]

    # The language to use.
    language: Var[LiteralCodeLanguage] = Var.create("python")

    # The theme to use ("light" or "dark").
    theme: Var[LiteralCodeTheme] = Var.create("one-light")

    # The set of themes to use for different modes.
    themes: Var[Union[list[dict[str, Any]], dict[str, str]]]

    # The code to display.
    code: Var[str]

    # The transformers to use for the syntax highlighter.
    transformers: Var[list[Union[ShikiBaseTransformers, dict[str, Any]]]] = Var.create(
        []
    )

    # The decorations to use for the syntax highlighter.
    decorations: Var[list[ShikiDecorations]] = Var.create([])

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
        decorations = props.pop("decorations", [])

        class_props = cls.get_props()

        # Distribute props between the code block and wrapper
        for key, value in props.items():
            (code_block_props if key in class_props else code_wrapper_props)[key] = (
                value
            )

        # cast decorations into ShikiDecorations.
        decorations = [
            ShikiDecorations(**decoration)
            if not isinstance(decoration, ShikiDecorations)
            else decoration
            for decoration in decorations
        ]
        code_block_props["decorations"] = decorations

        code_block_props["code"] = children[0]
        code_block = super().create(**code_block_props)

        transformer_styles = {}
        # Collect styles from transformers and wrapper
        for transformer in code_block.transformers._var_value:  # type: ignore
            if isinstance(transformer, ShikiBaseTransformers) and transformer.style:
                transformer_styles.update(transformer.style)
        transformer_styles.update(code_wrapper_props.pop("style", {}))

        return Box.create(
            code_block,
            *children[1:],
            style=Style({**transformer_styles, **BOX_PARENT_STYLING}),
            **code_wrapper_props,
        )

    def add_imports(self) -> dict[str, list[str]]:
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
                (
                    self.lib_dependencies.append(transformer.library)
                    if transformer.library not in self.lib_dependencies
                    else None
                )
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
        return ShikiBaseTransformers(  # type: ignore
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

    # If this is enabled, the default transformers(shikijs transformer) will be used.
    use_transformers: Var[bool]

    # If this is enabled line numbers will be shown next to the code block.
    show_line_numbers: Var[bool]

    # Whether a copy button should appear.
    can_copy: bool = False

    # copy_button: A custom copy button to override the default one.
    copy_button: Optional[Union[Component, bool]] = None

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
        use_transformers = props.pop("use_transformers", False)
        show_line_numbers = props.pop("show_line_numbers", False)
        language = props.pop("language", None)
        can_copy = props.pop("can_copy", False)
        copy_button = props.pop("copy_button", None)

        if use_transformers:
            props["transformers"] = [ShikiJsTransformer()]

        if language is not None:
            props["language"] = cls._map_languages(language)

        # line numbers are generated via css
        if show_line_numbers:
            props["style"] = {**LINE_NUMBER_STYLING, **props.get("style", {})}

        theme = props.pop("theme", None)
        props["theme"] = props["theme"] = (
            cls._map_themes(theme)
            if theme is not None
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
                    Icon.create(tag="copy", size=16, color=color("gray", 11)),
                    on_click=[
                        set_clipboard(cls._strip_transformer_triggers(code)),  # type: ignore
                        copy_script(),
                    ],
                    style=Style(
                        {
                            "position": "absolute",
                            "top": "4px",
                            "right": "4px",
                            "background": color("gray", 3),
                            "border": "1px solid",
                            "border-color": color("gray", 5),
                            "border-radius": "6px",
                            "padding": "5px",
                            "opacity": "1",
                            "cursor": "pointer",
                            "_hover": {
                                "background": color("gray", 4),
                            },
                            "transition": "background 0.250s ease-out",
                            "&>svg": {
                                "transition": "transform 0.250s ease-out, opacity 0.250s ease-out",
                            },
                            "_active": {
                                "background": color("gray", 5),
                            },
                        }
                    ),
                )
            )

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

    @staticmethod
    def _map_languages(language: str) -> str:
        if isinstance(language, str) and language in LANGUAGE_MAPPING:
            return LANGUAGE_MAPPING[language]
        return language

    @staticmethod
    def _strip_transformer_triggers(code: str | StringVar) -> StringVar | str:
        if not isinstance(code, (StringVar, str)):
            raise VarTypeError(
                f"code should be string literal or a StringVar type. Got {type(code)} instead."
            )
        regex_pattern = r"[\/#]+ *\[!code.*?\]"

        if isinstance(code, Var):
            return string_replace_operation(
                code, StringVar(_js_expr=f"/{regex_pattern}/g", _var_type=str), ""
            )
        if isinstance(code, str):
            return re.sub(regex_pattern, "", code)


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
