"""Table components."""
from typing import List, Tuple

from reflex.components.component import Component
from reflex.components.layout.foreach import Foreach
from reflex.components.libs.chakra import ChakraComponent
from reflex.utils import types
from reflex.vars import Var


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
            *children: The children of the component.
            caption: The caption of the table component.
            headers: The headers of the table component.
            rows: The rows of the table component.
            footers: The footers of the table component.
            **props: The properties of the component.

        Returns:
            The table component.
        """
        if len(children) == 0:
            children = []

            if caption is not None:
                children.append(TableCaption.create(caption))

            if headers is not None:
                children.append(Thead.create(headers=headers))

            if rows is not None:
                children.append(Tbody.create(rows=rows))

            if footers is not None:
                children.append(Tfoot.create(footers=footers))
        return super().create(*children, **props)


class Thead(ChakraComponent):
    """A table header component."""

    tag = "Thead"

    # invalid children components
    invalid_children: List[str] = ["Tbody", "Thead", "Tfoot"]

    @classmethod
    def create(cls, *children, headers=None, **props) -> Component:
        """Create a table header component.

        Args:
            *children: The children of the component.
            headers (list, optional): List of headers. Defaults to None.
            **props: The properties of the component.

        Returns:
            The table header component.

        Raises:
            TypeError: If headers are not of type list or type tuple.
        """
        if len(children) == 0:
            if (
                (
                    isinstance(headers, Var)
                    and types.get_base_class(headers.type_) not in (list, tuple)
                )
                or not isinstance(headers, Var)
                and types.get_base_class(type(headers)) not in (list, tuple)
            ):
                raise TypeError("table headers should be a list or tuple")
            children = [Tr.create(cell_type="header", cells=headers)]
        return super().create(*children, **props)


class Tbody(ChakraComponent):
    """A table body component."""

    tag = "Tbody"

    # invalid children components
    invalid_children: List[str] = ["Tbody", "Thead", "Tfoot", "Td", "Th"]

    @classmethod
    def create(cls, *children, rows=None, **props) -> Component:
        """Create a table body component.

        Args:
            *children: The children of the component.
            rows (list[list], optional): The rows of the table body. Defaults to None.
            **props: The properties of the component.

        Returns:
            Component: _description_

        Raises:
            TypeError: If rows are not of type list[list[Any]].
        """
        if len(children) == 0:
            if isinstance(rows, Var):
                t = rows.type_
                # check if outer container type is a list.
                if not issubclass(types.get_base_class(t), (List, Tuple)):
                    raise TypeError(
                        f"table rows should be a list of list. Got {t} instead"
                    )

                # Check if the inner type is also a list.
                inner_type = t.__args__[0] if hasattr(t, "__args__") else None
                if not inner_type or not issubclass(
                    types.get_base_class(inner_type), (List, Tuple)
                ):
                    raise TypeError(
                        f"table rows should be a list of list. Got {t} instead"
                    )

                children = [
                    Foreach.create(
                        rows, lambda row: Tr.create(cell_type="data", cells=row)
                    )
                ]
            else:
                if (
                    rows
                    and not isinstance(rows, (list, tuple))
                    or isinstance(rows, list)
                    and not isinstance(rows[0], (list, tuple))
                ):
                    raise TypeError("table rows should be a list of list")
                children = [
                    Tr.create(cell_type="data", cells=row) for row in rows or []
                ]
        return super().create(*children, **props)


class Tfoot(ChakraComponent):
    """A table footer component."""

    tag = "Tfoot"

    # invalid children components
    invalid_children: List[str] = ["Tbody", "Thead", "Td", "Th", "Tfoot"]

    @classmethod
    def create(cls, *children, footers=None, **props) -> Component:
        """Create a table footer component.

        Args:
            *children: The children of the component.
            footers (list, optional): List of footers. Defaults to None.
            **props: The properties of the component.

        Returns:
            The table footer component.

        Raises:
            TypeError: If footers are not of type list.
        """
        if len(children) == 0:
            if (
                (
                    isinstance(footers, Var)
                    and types.get_base_class(footers.type_) not in (list, tuple)
                )
                or not isinstance(footers, Var)
                and types.get_base_class(type(footers)) not in (list, tuple)
            ):
                raise TypeError("table headers should be a list")
            children = [Tr.create(cell_type="header", cells=footers)]
        return super().create(*children, **props)


class Tr(ChakraComponent):
    """A table row component."""

    tag = "Tr"

    # invalid children components
    invalid_children: List[str] = ["Tbody", "Thead", "Tfoot", "Tr"]

    @classmethod
    def create(cls, *children, cell_type: str = "", cells=None, **props) -> Component:
        """Create a table row component.

        Args:
            *children: The children of the component.
            cell_type: the type of cells in this table row. "header" or "data". Defaults to None.
            cells: The cells value to add in the table row. Defaults to None.
            **props: The properties of the component.

        Returns:
            The table row component
        """
        types = {"header": Th, "data": Td}
        cell_cls = types.get(cell_type)
        if len(children) == 0 and cell_cls:
            if isinstance(cells, Var):
                children = [Foreach.create(cells, cell_cls.create)]
            else:
                children = [cell_cls.create(cell) for cell in cells or []]
        return super().create(*children, **props)


class Th(ChakraComponent):
    """A table header cell component."""

    tag = "Th"

    # invalid children components
    invalid_children: List[str] = ["Tbody", "Thead", "Tr", "Td", "Th"]

    # Aligns the cell content to the right.
    is_numeric: Var[bool]


class Td(ChakraComponent):
    """A table data cell component."""

    tag = "Td"

    # invalid children components
    invalid_children: List[str] = ["Tbody", "Thead"]

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
