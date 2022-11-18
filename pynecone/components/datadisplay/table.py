"""Table components."""

from typing import List

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Table(ChakraComponent):
    """A table component."""

    tag = "Table"

    # The color scheme of the table
    color_scheme: Var[str]

    # The variant of the table style to use
    variant: Var[str]

    # The size of the table
    size: Var[str]

    # The placement of the table caption.
    placement: Var[str]


class Thead(Table):
    """A table header component."""

    tag = "Thead"


class Tbody(Table):
    """A table body component."""

    tag = "Tbody"


class Tfoot(Table):
    """A table footer component."""

    tag = "Tfoot"


class Tr(Table):
    """A table row component."""

    tag = "Tr"


class Th(ChakraComponent):
    """A table header cell component."""

    tag = "Th"

    # Aligns the cell content to the right.
    is_numeric: Var[bool]


class Td(ChakraComponent):
    """A table data cell component."""

    tag = "Td"

    # Aligns the cell content to the right.
    is_numeric: Var[bool]


class TableCaption(ChakraComponent):
    """A table caption component."""

    tag = "TableCaption"

    # The placement of the table caption. This sets the `caption-side` CSS attribute.
    placement: Var[str]


class TableContainer(ChakraComponent):
    """The table container component renders a div that wraps the table component."""

    tag = "TableContainer"
