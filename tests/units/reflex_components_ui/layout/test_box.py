"""Tests for reflex_components_ui.layout.box."""

import ast
from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_base.plugins import CompileContext
from reflex_base.utils.pyi_generator import PyiGenerator
from reflex_components_ui.layout import box as box_module
from reflex_components_ui.layout.box import Box
from reflex_components_ui.plugin import UIPlugin

import reflex as rx

BOX_PAGE = """import * as stylex from "@stylexjs/stylex"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"



const sx_b26ac4fb71 = stylex.create({ s: {"boxSizing": "border-box", "display": "block"} });
const sx_b26ac4fb71_c = stylex.props(sx_b26ac4fb71.s).className;
const sx_30d00d85a0 = stylex.create({ s: {"boxSizing": "border-box", "display": "block", "paddingTop": "4px", "paddingRight": "4px", "paddingBottom": "4px", "paddingLeft": "4px"} });
const sx_30d00d85a0_c = stylex.props(sx_30d00d85a0.s).className;

function Component() {


  return (
    jsx(Fragment,{},jsx("main",{},jsx("div",{className:sx_b26ac4fb71_c},"hello"),jsx("div",{className:sx_b26ac4fb71_c},"again"),jsx("div",{className:"p-8 " + sx_30d00d85a0_c},"padded")),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
  )
}
Component.displayName = "Component(/)";

export default Component;
"""


def test_box_page_source(
    ui_plugin: UIPlugin, compile_page: Callable[..., CompileContext]
):
    """A box is a div: no component is imported, and equal styles declare once."""

    def page():
        return rx.el.main(
            rx.ui.box("hello"),
            rx.ui.box("again"),
            rx.ui.box("padded", style={"padding": "4px"}, class_name="p-8"),
        )

    assert compile_page(page).compiled_pages["/"].output_code == BOX_PAGE


def test_box_is_a_name_of_the_ui_namespace():
    assert rx.ui.box == Box.create
    assert "box" in dir(rx.ui)


@pytest.fixture(scope="module")
def box_stub() -> ast.Module:
    """Generate the stub of the box, where a build writes it.

    Returns:
        The stub, parsed.
    """
    source = Path(box_module.__file__)
    PyiGenerator().scan_all([source])
    return ast.parse(source.with_suffix(".pyi").read_text())


def test_stub_types_the_style_as_css(box_stub: ast.Module):
    """The stub of every rx.ui component types its style, and imports the type."""
    (box,) = [node for node in box_stub.body if isinstance(node, ast.ClassDef)]
    (create,) = [node for node in box.body if isinstance(node, ast.FunctionDef)]
    annotations = {
        argument.arg: ast.unparse(argument.annotation)
        for argument in create.args.kwonlyargs
        if argument.annotation is not None
    }
    assert annotations["style"] == (
        "Sequence[StyleProps] | StyleProps | Var[Mapping[str, Any]] | Breakpoints "
        "| None"
    )
    # Keyword arguments stay open: data_* and aria_* come through them.
    assert create.args.kwarg is not None
    assert create.args.kwarg.arg == "props"
    assert [
        ast.unparse(node)
        for node in box_stub.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "reflex_components_ui.style"
    ] == ["from reflex_components_ui.style import ComponentStyles, StyleProps"]


def test_valid_styles_of_a_component_type_check(
    box_stub: ast.Module, pyright: Callable[[str], list[tuple[int, str, str]]]
):
    assert pyright("component_valid") == []


def test_invalid_styles_of_a_component_are_type_errors(
    box_stub: ast.Module, pyright: Callable[[str], list[tuple[int, str, str]]]
):
    assert pyright("component_errors") == COMPONENT_ERRORS


# What pyright says of each call of the fixture: its line, rule and message.
COMPONENT_ERRORS: list[tuple[int, str, str]] = [
    (
        5,
        "reportArgumentType",
        (
            'Argument of type "dict[str, str]" cannot be assigned to parameter "style" of type '
            '"Sequence[StyleProps] | StyleProps | Var[Mapping[str, Any]] | Breakpoints[Unknown, '
            'Unknown] | None" in function "create"\n'
            '\xa0\xa0Type "dict[str, str]" is not assignable to type "Sequence[StyleProps] | '
            'StyleProps | Var[Mapping[str, Any]] | Breakpoints[Unknown, Unknown] | None"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Sequence[StyleProps]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "StyleProps"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Var[Mapping[str, Any]]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Breakpoints[Unknown, '
            'Unknown]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "None"'
        ),
    ),
    (
        7,
        "reportArgumentType",
        (
            'Argument of type "dict[str, str]" cannot be assigned to parameter "style" of type '
            '"Sequence[StyleProps] | StyleProps | Var[Mapping[str, Any]] | Breakpoints[Unknown, '
            'Unknown] | None" in function "create"\n'
            '\xa0\xa0Type "dict[str, str]" is not assignable to type "Sequence[StyleProps] | '
            'StyleProps | Var[Mapping[str, Any]] | Breakpoints[Unknown, Unknown] | None"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Sequence[StyleProps]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "StyleProps"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Var[Mapping[str, Any]]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "Breakpoints[Unknown, '
            'Unknown]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, str]" is not assignable to "None"'
        ),
    ),
    (
        9,
        "reportArgumentType",
        (
            'Argument of type "dict[str, dict[str, str]]" cannot be assigned to parameter '
            '"style" of type "Sequence[StyleProps] | StyleProps | Var[Mapping[str, Any]] | '
            'Breakpoints[Unknown, Unknown] | None" in function "create"\n'
            '\xa0\xa0Type "dict[str, dict[str, str]]" is not assignable to type '
            '"Sequence[StyleProps] | StyleProps | Var[Mapping[str, Any]] | Breakpoints[Unknown, '
            'Unknown] | None"\n'
            '\xa0\xa0\xa0\xa0"dict[str, dict[str, str]]" is not assignable to '
            '"Sequence[StyleProps]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, dict[str, str]]" is not assignable to "StyleProps"\n'
            '\xa0\xa0\xa0\xa0"dict[str, dict[str, str]]" is not assignable to "Var[Mapping[str, '
            'Any]]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, dict[str, str]]" is not assignable to '
            '"Breakpoints[Unknown, Unknown]"\n'
            '\xa0\xa0\xa0\xa0"dict[str, dict[str, str]]" is not assignable to "None"'
        ),
    ),
    (
        11,
        "reportArgumentType",
        (
            'Argument of type "list[StyleProps | dict[str, str]]" cannot be assigned to '
            'parameter "style" of type "Sequence[StyleProps] | StyleProps | Var[Mapping[str, '
            'Any]] | Breakpoints[Unknown, Unknown] | None" in function "create"\n'
            '\xa0\xa0Type "Literal[\'flx\']" is not assignable to type "_Value[_Display | '
            '_StrVar]"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'flx\']" is not assignable to "Var[str]"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'flx\']" is not assignable to "Sequence[_Display | '
            '_StrVar]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0Type parameter "_T_co@Sequence" is covariant, but "str" is '
            'not a subtype of "_Display | _StrVar"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0Type "str" is not assignable to type "_Display | '
            '_StrVar"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to "Var[str]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to type '
            "\"Literal['-webkit-box']\"\n"
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to type '
            "\"Literal['block']\""
        ),
    ),
    (
        13,
        "reportArgumentType",
        (
            "Argument of type \"Literal['padding: 1em']\" cannot be assigned to parameter "
            '"style" of type "Sequence[StyleProps] | StyleProps | Var[Mapping[str, Any]] | '
            'Breakpoints[Unknown, Unknown] | None" in function "create"\n'
            "\xa0\xa0Type \"Literal['padding: 1em']\" is not assignable to type "
            '"Sequence[StyleProps] | StyleProps | Var[Mapping[str, Any]] | Breakpoints[Unknown, '
            'Unknown] | None"\n'
            "\xa0\xa0\xa0\xa0\"Literal['padding: 1em']\" is not assignable to "
            '"Sequence[StyleProps]"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0Type parameter "_T_co@Sequence" is covariant, but "str" is '
            'not a subtype of "StyleProps"\n'
            '\xa0\xa0\xa0\xa0\xa0\xa0\xa0\xa0"str" is not assignable to "StyleProps"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'padding: 1em\']" is not assignable to "StyleProps"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'padding: 1em\']" is not assignable to "Var[Mapping[str, '
            'Any]]"\n'
            "\xa0\xa0\xa0\xa0\"Literal['padding: 1em']\" is not assignable to "
            '"Breakpoints[Unknown, Unknown]"\n'
            '\xa0\xa0\xa0\xa0"Literal[\'padding: 1em\']" is not assignable to "None"'
        ),
    ),
]
