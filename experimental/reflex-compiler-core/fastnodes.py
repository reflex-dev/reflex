"""Native element factories driven by the Rust component registry.

`register_elements()` registers the `rx.el.*` HTML elements with the Rust core
(name -> tag, is_element=True). After that, `el.div(...)`, `el.span(...)`, etc.
build native nodes via `rcc.make` — no `Component` subclass is instantiated, no
pydantic, no per-prop `LiteralVar.create`. Prop ordering is handled by the Rust
side's sort (matching Reflex's `format_props`), so no per-component field-order
table is needed. Radix components (rx.box/text/...) differ only in carrying a
JS tag != name plus `add_style`; they register the same way once their tag and
style mapping are generated from the Python class — the next step.
"""

import types

import reflex_compiler_core as rcc

# The rx.el.* elements the docs app leans on (div/span/p/a/ul/li/h1/h2/button…).
ELEMENTS = [
    "div", "span", "p", "a", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "nav", "header", "footer", "main", "aside",
    "button", "strong", "em", "b", "i", "code", "pre",
    "img", "table", "thead", "tbody", "tr", "td", "th",
    "label", "form", "input", "hr", "br", "div",
]


def register_elements():
    """Register each element with the Rust core (the code-gen registry step)."""
    for name in ELEMENTS:
        rcc.register_component(name, name, True)  # element: tag == name


register_elements()


def _factory(name):
    def make(*children, **props):
        return rcc.make(name, list(children), props)

    make.__name__ = name
    return make


# el.div(...), el.span(...), ... — registry-driven native element factories.
el = types.SimpleNamespace(**{name: _factory(name) for name in set(ELEMENTS)})

render_to_js = rcc.render_to_js
render_to_js_pure = rcc.render_to_js_pure


# Legacy single-purpose shims kept for the original bench.
def fast_div(*children, **props):
    return rcc.make("div", list(children), props)


def fast_span(*children, **props):
    return rcc.make("span", list(children), props)


def fast_h1(*children, **props):
    return rcc.make("h1", list(children), props)
