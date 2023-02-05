"""Table components."""

from typing import List
from pynecone.components.component import Component

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

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a table component

        Args:
            children: The children of the component.
            props: The properties of the component.
        Returns:
            The table component
        """
        if not children:
            children = []
            prop_caption = props.pop("caption", None)
            prop_headers = props.pop("headers", [])  # list of headers
            prop_rows = props.pop("rows", [[]])  # list of rows
            prop_footers = props.pop("footers", [])  # list of footers

            if prop_caption:
                children.append(TableCaption.create(prop_caption))

            if prop_headers:
                children.append(
                    Thead.create(
                        Tr.create(*[Th.create(header) for header in prop_headers])
                    )
                )

            if prop_rows:
                children.append(
                    Tbody.create(
                        *[
                            Tr.create(*[Td.create(item) for item in row])
                            for row in prop_rows
                        ]
                    )
                )

            if prop_footers:
                children.append(
                    Tfoot.create(
                        Tr.create(*[Th.create(footer) for footer in prop_footers])
                    )
                )
        return super().create(*children, **props)


class Thead(ChakraComponent):
    """A table header component."""

    tag = "Thead"


class Tbody(ChakraComponent):
    """A table body component."""

    tag = "Tbody"


class Tfoot(ChakraComponent):
    """A table footer component."""

    tag = "Tfoot"


class Tr(ChakraComponent):
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
