"""Thin Python factory shims over the Rust compiler core.

Each shim carries only static metadata (tag name) and hands raw children +
props to Rust. No `Component` subclass is instantiated, no pydantic model, no
per-prop `LiteralVar.create`. Contrast with `rx.el.div(...)` which runs the
full `Component.create` -> `_post_init` machinery per node.

In a real implementation these shims would be code-generated from the existing
Python component class definitions (so the `.pyi` typed signatures are
preserved); here they are hand-written for box/text/heading == div/span/h1.
"""

import reflex_compiler_core as _rcc


def fast_div(*children, **props):
    """Build a native <div> node (rx.box analog)."""
    return _rcc.make_node("div", True, list(children), props)


def fast_span(*children, **props):
    """Build a native <span> node (rx.text analog)."""
    return _rcc.make_node("span", True, list(children), props)


def fast_h1(*children, **props):
    """Build a native <h1> node (rx.heading analog)."""
    return _rcc.make_node("h1", True, list(children), props)


render_to_js = _rcc.render_to_js
