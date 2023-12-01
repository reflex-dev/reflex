"""The head component."""

from reflex.components.component import Component, MemoizationLeaf


class NextHeadLib(Component):
    """Header components."""

    library = "next/head"


class Head(NextHeadLib, MemoizationLeaf):
    """Head Component."""

    tag = "NextHead"

    is_default = True
