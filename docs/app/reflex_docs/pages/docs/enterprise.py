"""The enterprise documentation pages."""

from reflex_docs.templates.docpage import docpage


@docpage(
    set_path="/docs/enterprise/overview",
    t="Overview | Enterprise",
)
def overview():
    """The enterprise overview page."""
    pass
