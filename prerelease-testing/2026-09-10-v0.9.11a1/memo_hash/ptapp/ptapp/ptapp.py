"""ptapp — the passthrough-memo import gap listed under #6947's "Not in this PR".

``compile_experimental_component_memo`` pulls the WHOLE subtree's imports into a
passthrough memo body, while ``_component_artifacts(recursive=False)`` feeds the
hash only the root's own imports. Two passthrough memos with identical roots and
descendants that render identically but import differently therefore share a tag
while their emitted import blocks differ.

``SpanA``/``SpanB`` render byte-identically to ``rx.el.span`` and differ only in
a tagless (side-effect) CSS ImportVar.
"""

import reflex as rx
from reflex_base.utils.imports import ImportVar


class Shared(rx.State):
    """Shared reactive state so the holder becomes a memo boundary."""

    label: str = "L0"

    @rx.event
    def relabel(self):
        """Change the label."""
        self.label = "L1"


class SpanA(rx.el.Span):
    """Renders exactly like rx.el.span; side-effect-imports pt_a.css."""

    def add_imports(self):
        """Side-effect stylesheet import.

        Returns:
            The import dict.
        """
        return {"$/public/pt_a.css": [ImportVar(tag=None)]}


class SpanB(rx.el.Span):
    """Renders exactly like rx.el.span; side-effect-imports pt_b.css."""

    def add_imports(self):
        """Side-effect stylesheet import.

        Returns:
            The import dict.
        """
        return {"$/public/pt_b.css": [ImportVar(tag=None)]}


class Holder(rx.el.Div):
    """The passthrough-memo root; identical props at both call sites."""


def index() -> rx.Component:
    """Two holders with identical roots and differing descendants.

    Returns:
        The page.
    """
    return rx.el.div(
        rx.el.div(
            Holder.create(SpanA.create("x", class_name="pt-target"), title=Shared.label),
            id="holder-a",
        ),
        rx.el.div(
            Holder.create(SpanB.create("x", class_name="pt-target"), title=Shared.label),
            id="holder-b",
        ),
        rx.el.button("relabel", on_click=Shared.relabel, id="relabel"),
        id="pt-page",
    )


app = rx.App()
app.add_page(index, route="/")
