"""Markdown component."""

from __future__ import annotations

import dataclasses
import textwrap
from collections.abc import Callable, Sequence
from functools import lru_cache
from hashlib import md5
from types import SimpleNamespace
from typing import Any

from reflex.components.component import (
    BaseComponent,
    Component,
    ComponentNamespace,
    CustomComponent,
    field,
)
from reflex.components.el.elements.typography import Div
from reflex.components.tags.tag import Tag
from reflex.utils import console
from reflex.utils.imports import ImportDict, ImportTypes, ImportVar
from reflex.vars.base import LiteralVar, Var, VarData
from reflex.vars.function import ArgsFunctionOperation, DestructuredArg
from reflex.vars.number import ternary_operation
from reflex.vars.sequence import LiteralArrayVar

# Special vars used in the component map.
_CHILDREN = Var(_js_expr="children", _var_type=str)
_PROPS = Var(_js_expr="props")
_PROPS_SPREAD = Var(_js_expr="...props")
_REST = Var(_js_expr="rest")
_REST_SPREAD = Var(_js_expr="...rest")
_MOCK_ARG = Var(_js_expr="", _var_type=str)
_LANGUAGE = Var(_js_expr="_language", _var_type=str)


class Plugin(SimpleNamespace):
    """Create new remark/rehype plugin or access pre-wrapped plugins."""

    @staticmethod
    def create(
        package: str,
        tag: str,
        additional_imports: dict[str, ImportTypes] | None = None,
        **import_var_kwargs,
    ) -> Var:
        """Create a plugin Var.

        Args:
            package: The package to import the plugin from.
            tag: The imported identifier.
            additional_imports: Additional imports to include in the VarData, such as CSS.
            **import_var_kwargs: Additional kwargs to pass to the ImportVar.

        Returns:
            The plugin Var.
        """
        import_var_kwargs.setdefault("is_default", True)
        return Var(
            _js_expr=tag,
            _var_data=VarData(
                imports={
                    package: ImportVar(
                        tag=tag,
                        **import_var_kwargs,
                    ),
                    **(additional_imports or {}),
                }
            ),
        )

    __call__ = create

    math = create("remark-math@6.0.0", "remarkMath")
    gfm = create("remark-gfm@4.0.1", "remarkGfm")
    unwrap_images = create("rehype-unwrap-images@1.0.0", "rehypeUnwrapImages")
    katex = create(
        "rehype-katex@7.0.1",
        "rehypeKatex",
        additional_imports={
            "": "katex/dist/katex.min.css",
        },
    )
    raw = create("rehype-raw@7.0.0", "rehypeRaw")
    _undefined = Var(_js_expr="() => undefined")


def _h1(value: object):
    from reflex.components.radix.themes.typography.heading import Heading

    return Heading.create(value, as_="h1", size="6", margin_y="0.5em")


def _h2(value: object):
    from reflex.components.radix.themes.typography.heading import Heading

    return Heading.create(value, as_="h2", size="5", margin_y="0.5em")


def _h3(value: object):
    from reflex.components.radix.themes.typography.heading import Heading

    return Heading.create(value, as_="h3", size="4", margin_y="0.5em")


def _h4(value: object):
    from reflex.components.radix.themes.typography.heading import Heading

    return Heading.create(value, as_="h4", size="3", margin_y="0.5em")


def _h5(value: object):
    from reflex.components.radix.themes.typography.heading import Heading

    return Heading.create(value, as_="h5", size="2", margin_y="0.5em")


def _h6(value: object):
    from reflex.components.radix.themes.typography.heading import Heading

    return Heading.create(value, as_="h6", size="1", margin_y="0.5em")


def _p(value: object):
    from reflex.components.radix.themes.typography.text import Text

    return Text.create(value, margin_y="1em")


def _ul(value: object):
    from reflex.components.radix.themes.layout.list import UnorderedList

    return UnorderedList.create(value, margin_y="1em")


def _ol(value: object):
    from reflex.components.radix.themes.layout.list import OrderedList

    return OrderedList.create(value, margin_y="1em")


def _li(value: object):
    from reflex.components.radix.themes.layout.list import ListItem

    return ListItem.create(value, margin_y="0.5em")


def _a(value: object):
    from reflex.components.radix.themes.typography.link import Link

    return Link.create(value)


def _code(value: object):
    from reflex.components.radix.themes.typography.code import Code

    return Code.create(value)


def _codeblock(value: object, **props):
    from reflex.components.datadisplay.code import CodeBlock

    return CodeBlock.create(value, margin_y="1em", wrap_long_lines=True, **props)


# Component Mapping
@lru_cache
def get_base_component_map() -> dict[str, Callable]:
    """Get the base component map.

    Returns:
        The base component map.
    """
    return {
        "h1": _h1,
        "h2": _h2,
        "h3": _h3,
        "h4": _h4,
        "h5": _h5,
        "h6": _h6,
        "p": _p,
        "ul": _ul,
        "ol": _ol,
        "li": _li,
        "a": _a,
        "code": _code,
        "pre": _codeblock,
    }


@dataclasses.dataclass()
class MarkdownComponentMap:
    """Mixin class for handling custom component maps in Markdown components."""

    _explicit_return: bool = dataclasses.field(default=False)

    @classmethod
    def get_component_map_custom_code(cls) -> Var:
        """Get the custom code for the component map.

        Returns:
            The custom code for the component map.
        """
        return Var("")

    @classmethod
    def create_map_fn_var(
        cls,
        fn_body: Var | None = None,
        fn_args: Sequence[str] | None = None,
        explicit_return: bool | None = None,
        var_data: VarData | None = None,
    ) -> Var:
        """Create a function Var for the component map.

        Args:
            fn_body: The formatted component as a string.
            fn_args: The function arguments.
            explicit_return: Whether to use explicit return syntax.
            var_data: The var data for the function.

        Returns:
            The function Var for the component map.
        """
        fn_args = fn_args or cls.get_fn_args()
        fn_body = fn_body if fn_body is not None else cls.get_fn_body()
        explicit_return = explicit_return or cls._explicit_return

        return ArgsFunctionOperation.create(
            args_names=(DestructuredArg(fields=tuple(fn_args)),),
            return_expr=fn_body,
            explicit_return=explicit_return,
            _var_data=var_data,
        )

    @classmethod
    def get_fn_args(cls) -> Sequence[str]:
        """Get the function arguments for the component map.

        Returns:
            The function arguments as a list of strings.
        """
        return ["node", _CHILDREN._js_expr, _PROPS_SPREAD._js_expr]

    @classmethod
    def get_fn_body(cls) -> Var:
        """Get the function body for the component map.

        Returns:
            The function body as a string.
        """
        return Var(_js_expr="undefined", _var_type=None)


class Markdown(Component):
    """A markdown component."""

    library = "react-markdown@10.1.0"

    tag = "ReactMarkdown"

    is_default = True

    # The component map from a tag to a lambda that creates a component.
    component_map: dict[str, Any] = field(
        default_factory=dict, is_javascript_property=False
    )

    # The hash of the component map, generated at create() time.
    component_map_hash: str = field(default="", is_javascript_property=False)

    # Remark plugins to use when rendering the content. Provide (plugin, options) if the plugin requires options.
    remark_plugins: Var[Sequence[Var | tuple[Var, Var]]]

    # Rehype (HTML processor) plugins to use when rendering the content. Provide (plugin, options) if the plugin requires options.
    rehype_plugins: Var[Sequence[Var | tuple[Var, Var]]]

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
        """Create a markdown component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Raises:
            ValueError: If the children are not valid.

        Returns:
            The markdown component.
        """
        if len(children) != 1 or not isinstance(children[0], (str, Var)):
            msg = "Markdown component must have exactly one child containing the markdown source."
            raise ValueError(msg)

        # Update the base component map with the custom component map.
        component_map = {**get_base_component_map(), **props.pop("component_map", {})}
        if "codeblock" in component_map:
            console.deprecate(
                feature_name="'codeblock' in component_map",
                reason="Use 'pre' instead of 'codeblock' to customize code block rendering in markdown",
                deprecation_version="0.8.25",
                removal_version="0.9.0",
            )
            component_map["pre"] = component_map.pop("codeblock")

        # Get the markdown source.
        src = children[0]

        # Dedent the source.
        if isinstance(src, str):
            src = textwrap.dedent(src)

        # Create the component.
        return super().create(
            src,
            component_map=component_map,
            component_map_hash=cls._component_map_hash(component_map),
            **props,
        )

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the markdown component.

        Returns:
            The imports for the markdown component.
        """
        return [
            *[
                component(_MOCK_ARG)._get_all_imports()
                for component in self.component_map.values()
            ],
            *(
                [codeblock_var_data.old_school_imports()]
                if (
                    codeblock_var_data
                    := self._get_codeblock_fn_var()._get_all_var_data()
                )
                is not None
                else []
            ),
        ]

    def _get_tag_map_fn_var(self, tag: str) -> Var:
        return self._get_map_fn_var_from_children(self.get_component(tag), tag)

    def format_component_map(self) -> dict[str, Var]:
        """Format the component map for rendering.

        Returns:
            The formatted component map.
        """
        components = {
            tag: self._get_tag_map_fn_var(tag)
            for tag in self.component_map
            if tag != "pre"
        }

        # Special handling for code blocks to extract the language.
        components["pre"] = self._get_codeblock_fn_var()

        return components

    def _get_codeblock_fn_var(self) -> Var:
        """Get the function variable for codeblock.

        This function creates a Var that represents a function to handle
        both code blocks in markdown.

        Returns:
            The Var for pre code.
        """
        # Get any custom code from the code block "pre" component.
        custom_code_list = self._get_map_fn_custom_code_from_children(
            self.get_component("pre")
        )
        var_data = VarData.merge(*[
            code._get_all_var_data()
            for code in custom_code_list
            if isinstance(code, Var)
        ])
        codeblock_custom_code = "\n".join(map(str, custom_code_list))

        # Format the code to handle code block with language extraction.
        formatted_code = f"""
const {{node: childNode, className, children: components, {_PROPS_SPREAD._js_expr}}} = {_REST._js_expr}.children.props;
const {_CHILDREN._js_expr} = String(Array.isArray(components) ? components.join('\\n') : components).replace(/\\n$/, '');
const match = (className || '').match(/language-(?<lang>.*)/);
let {_LANGUAGE!s} = match ? match[1] : '';
{codeblock_custom_code};
            return {self.format_component("pre", language=_LANGUAGE)};
        """.replace("\n", " ")

        return MarkdownComponentMap.create_map_fn_var(
            fn_body=Var(_js_expr=formatted_code),
            fn_args=["node", _REST_SPREAD._js_expr],
            explicit_return=True,
            var_data=var_data,
        )

    def get_component(self, tag: str, **props) -> Component:
        """Get the component for a tag and props.

        Args:
            tag: The tag of the component.
            **props: The props of the component.

        Returns:
            The component.

        Raises:
            ValueError: If the tag is invalid.
        """
        # Check the tag is valid.
        if tag not in self.component_map:
            msg = f"No markdown component found for tag: {tag}."
            raise ValueError(msg)

        # If the children are set as a prop, don't pass them as children.
        children = [_CHILDREN] if props.get("children") is None else []
        # Get the component.
        return self.component_map[tag](*children, **props).set(special_props=[_PROPS])

    def format_component(self, tag: str, **props) -> str:
        """Format a component for rendering in the component map.

        Args:
            tag: The tag of the component.
            **props: Extra props to pass to the component function.

        Returns:
            The formatted component.
        """
        return str(self.get_component(tag, **props)).replace("\n", "")

    def _get_map_fn_var_from_children(self, component: Component, tag: str) -> Var:
        """Create a function Var for the component map for the specified tag.

        Args:
            component: The component to check for custom code.
            tag: The tag of the component.

        Returns:
            The function Var for the component map.
        """
        formatted_component = Var(
            _js_expr=f"({self.format_component(tag)})", _var_type=str
        )
        if isinstance(component, MarkdownComponentMap):
            return component.create_map_fn_var(fn_body=formatted_component)

        # fallback to the default fn Var creation if the component is not a MarkdownComponentMap.
        return MarkdownComponentMap.create_map_fn_var(fn_body=formatted_component)

    def _get_map_fn_custom_code_from_children(
        self, component: BaseComponent
    ) -> list[str | Var]:
        """Recursively get markdown custom code from children components.

        Args:
            component: The component to check for custom code.

        Returns:
            A list of markdown custom code strings.
        """
        custom_code_list: list[str | Var] = []
        if isinstance(component, MarkdownComponentMap):
            custom_code_list.append(component.get_component_map_custom_code())

        # If the component is a custom component(rx.memo), obtain the underlining
        # component and get the custom code from the children.
        if isinstance(component, CustomComponent):
            custom_code_list.extend(
                self._get_map_fn_custom_code_from_children(
                    component.component_fn(*component.get_prop_vars())
                )
            )
        elif isinstance(component, Component):
            for child in component.children:
                custom_code_list.extend(
                    self._get_map_fn_custom_code_from_children(child)
                )

        return custom_code_list

    @staticmethod
    def _component_map_hash(component_map: dict) -> str:
        inp = str({
            tag: (
                f"{component.__module__}.{component.__qualname__}"
                if (
                    "<" not in component.__name__
                )  # simple way to check against lambdas
                else component(_MOCK_ARG)
            )
            for tag, component in component_map.items()
        }).encode()
        return md5(inp).hexdigest()

    def _get_component_map_name(self) -> str:
        return f"ComponentMap_{self.component_map_hash}"

    def _get_custom_code(self) -> str | None:
        hooks = {}
        from reflex.compiler.templates import _render_hooks

        for component_factory in self.component_map.values():
            comp = component_factory(_MOCK_ARG)
            hooks.update(comp._get_all_hooks())
        formatted_hooks = _render_hooks(hooks)
        return f"""
        function {self._get_component_map_name()} () {{
            {formatted_hooks}
            return (
                {LiteralVar.create(self.format_component_map())!s}
            )
        }}
        """

    def _render(self) -> Tag:
        return (
            super()
            ._render()
            .add_props(
                components=Var(_js_expr=f"{self._get_component_map_name()}()"),
            )
            .remove_props("componentMap", "componentMapHash")
        )


class MarkdownWrapper(Div):
    """A markdown component, with optional div-wrapping when style props are given."""

    @classmethod
    def create(
        cls,
        *children,
        use_math: bool | Var[bool] = True,
        use_gfm: bool | Var[bool] = True,
        use_unwrap_images: bool | Var[bool] = True,
        use_katex: bool | Var[bool] = True,
        use_raw: bool | Var[bool] = True,
        **props,
    ) -> Component:
        """Create a markdown component.

        Args:
            *children: The children of the component.
            use_math: Whether to use the remark-math plugin.
            use_gfm: Whether to use the GitHub Flavored Markdown plugin.
            use_unwrap_images: Whether to use the unwrap images plugin.
            use_katex: Whether to use the KaTeX plugin.
            use_raw: Whether to use the raw HTML plugin.
            **props: The properties of the component.

        Raises:
            ValueError: If the children are not valid.

        Returns:
            The markdown component or div wrapping markdown component.
        """
        # Assemble the plugin lists.
        builtin_remark_plugins = []
        if isinstance(use_math, Var):
            builtin_remark_plugins.append(
                ternary_operation(
                    use_math, markdown.plugin.math, markdown.plugin._undefined
                )
            )
        elif use_math:
            builtin_remark_plugins.append(markdown.plugin.math)
        if isinstance(use_gfm, Var):
            builtin_remark_plugins.append(
                ternary_operation(
                    use_gfm, markdown.plugin.gfm, markdown.plugin._undefined
                )
            )
        elif use_gfm:
            builtin_remark_plugins.append(markdown.plugin.gfm)
        remark_plugins = LiteralArrayVar.create(builtin_remark_plugins)
        if (user_remark_plugins := props.pop("remark_plugins", None)) is not None:
            if not isinstance(user_remark_plugins, Var):
                user_remark_plugins = Var.create(user_remark_plugins)
            remark_plugins = remark_plugins + user_remark_plugins.to(list)

        builtin_rehype_plugins = []
        if isinstance(use_katex, Var):
            builtin_rehype_plugins.append(
                ternary_operation(
                    use_katex, markdown.plugin.katex, markdown.plugin._undefined
                )
            )
        elif use_katex:
            builtin_rehype_plugins.append(markdown.plugin.katex)
        if isinstance(use_raw, Var):
            builtin_rehype_plugins.append(
                ternary_operation(
                    use_raw, markdown.plugin.raw, markdown.plugin._undefined
                )
            )
        elif use_raw:
            builtin_rehype_plugins.append(markdown.plugin.raw)
        if isinstance(use_unwrap_images, Var):
            builtin_rehype_plugins.append(
                ternary_operation(
                    use_unwrap_images,
                    markdown.plugin.unwrap_images,
                    markdown.plugin._undefined,
                )
            )
        elif use_unwrap_images:
            builtin_rehype_plugins.append(markdown.plugin.unwrap_images)
        rehype_plugins = LiteralArrayVar.create(builtin_rehype_plugins)
        if (user_rehype_plugins := props.pop("rehype_plugins", None)) is not None:
            if not isinstance(user_rehype_plugins, Var):
                user_rehype_plugins = Var.create(user_rehype_plugins)
            rehype_plugins = rehype_plugins + user_rehype_plugins.to(list)

        return super().create(
            Markdown.create(
                *children,
                component_map=props.pop("component_map", {}),
                remark_plugins=remark_plugins.to(list[Var | tuple[Var, Var]]),
                rehype_plugins=rehype_plugins.to(list[Var | tuple[Var, Var]]),
            ),
            **props,
        )


class MarkdownNamespace(ComponentNamespace):
    """A namespace for markdown components."""

    __call__ = staticmethod(MarkdownWrapper.create)
    root = staticmethod(Markdown.create)
    plugin = Plugin()


markdown = MarkdownNamespace()
