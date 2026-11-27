"""Tests for reflex_components_ui.layout.box."""

from collections.abc import Callable

from reflex_base.plugins import CompileContext
from reflex_components_ui.layout.box import Box
from reflex_components_ui.plugin import UIPlugin

import reflex as rx

BOX_PAGE = """import * as stylex from "@stylexjs/stylex"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"



const sx_b26ac4fb71 = stylex.create({ s: {"boxSizing": "border-box", "display": "block"} });
const sx_f49d6b3475 = stylex.create({ s: {"boxSizing": "border-box", "display": "block", "padding": "4px"} });

function Component() {


  return (
    jsx(Fragment,{},jsx("main",{},jsx("div",{...stylex.props(sx_b26ac4fb71.s)},"hello"),jsx("div",{...stylex.props(sx_b26ac4fb71.s)},"again"),jsx("div",{...stylex.props(sx_f49d6b3475.s, { $$css: true, className: "p-8" })},"padded")),jsx("title",{}," | Index"),jsx("meta",{content:"",property:"og:image"},))
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
