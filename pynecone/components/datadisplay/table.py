"""Table components."""

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
    def create(
        cls, *children, caption=None, headers=None, rows=None, footers=None, **props
    ) -> Component:
        """Create a table component.

        Args:
            children: The children of the component.
            caption: The caption of the table component.
            headers: The headers of the table component.
            rows: The rows of the table component.
            footers: The footers of the table component.
            props: The properties of the component.

        Returns:
            The table component.
        """
        if len(children) == 0:
            children = []

            if caption:
                children.append(TableCaption.create(caption))

            if headers:
                children.append(Thead.create(headers=headers))

            if rows:
                children.append(Tbody.create(rows=rows))

            if footers:
                children.append(Tfoot.create(footers=footers))
        return super().create(*children, **props)


class Thead(ChakraComponent):
    """A table header component."""

    tag = "Thead"

    @classmethod
    def create(cls, *children, headers=None, **props) -> Component:
        """Create a table header component.

        Args:
            children: The children of the component.
            props: The properties of the component.
            headers (list, optional): List of headers. Defaults to None.

        Returns:
            The table header component.
        """
        if len(children) == 0:
            children = [Tr.create(cell_type="header", cells=headers)]
        return super().create(*children, **props)


class Tbody(ChakraComponent):
    """A table body component."""

    tag = "Tbody"

    @classmethod
    def create(cls, *children, rows=None, **props) -> Component:
        """Create a table body component.

        Args:
            children: The children of the component.
            props: The properties of the component.
            rows (list[list], optional): The rows of the table body. Defaults to None.

        Returns:
            Component: _description_
        """
        if len(children) == 0:
            children = [Tr.create(cell_type="data", cells=row) for row in rows or []]
        return super().create(*children, **props)


class Tfoot(ChakraComponent):
    """A table footer component."""

    tag = "Tfoot"

    @classmethod
    def create(cls, *children, footers=None, **props) -> Component:
        """Create a table footer component.

        Args:
            children: The children of the component.
            props: The properties of the component.
            footers (list, optional): List of footers. Defaults to None.

        Returns:
            The table footer component.
        """
        if len(children) == 0:
            children = [Tr.create(cell_type="header", cells=footers)]
        return super().create(*children, **props)


class Tr(ChakraComponent):
    """A table row component."""

    tag = "Tr"

    @classmethod
    def create(cls, *children, cell_type: str = "", cells=None, **props) -> Component:
        """Create a table row component.

        Args:
            children: The children of the component.
            props: The properties of the component.
            cell_type (str): the type of cells in this table row. "header" or "data". Defaults to None.
            cells (list, optional): The cells value to add in the table row. Defaults to None.

        Returns:
            The table row component
        """
        types = {"header": Th, "data": Td}
        cell_cls = types.get(cell_type)
        if len(children) == 0 and cell_cls:
            children = [cell_cls.create(cell) for cell in cells or []]
        return super().create(*children, **props)


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
