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

        """
        if len(children) == 0:
            cls.validate_headers(headers)

            children = [Tr.create(cell_type="header", cells=headers)]
        return super().create(*children, **props)

    @staticmethod
    def validate_headers(headers):
        """Type checking for table headers.

        Args:
            headers: The table headers.

        Raises:
            TypeError: If headers are not of type list or type tuple.

        """
        allowed_types = (list, tuple)
        if (
            (
                isinstance(headers, Var)
                and not types.check_type_in_allowed_types(headers.type_, allowed_types)
            )
            or not isinstance(headers, Var)
            and not types.check_type_in_allowed_types(type(headers), allowed_types)
        ):
            raise TypeError("table headers should be a list or tuple")


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
            Component: The table body component
        """
        if len(children) == 0:
            cls.validate_rows(rows) if rows is not None else None

            if isinstance(rows, Var):
                children = [
                    Foreach.create(
                        rows, lambda row: Tr.create(cell_type="data", cells=row)
                    )
                ]
            else:
                children = [
                    Tr.create(cell_type="data", cells=row) for row in rows or []
                ]
        return super().create(*children, **props)

    @staticmethod
    def validate_rows(rows):
        """Type checking for table rows.

        Args:
            rows: Table rows.

        Raises:
            TypeError: If rows are not lists or tuples containing inner lists or tuples.
        """
        allowed_subclasses = (List, Tuple)
        if isinstance(rows, Var):
            outer_type = rows.type_
            inner_type = (
                outer_type.__args__[0] if hasattr(outer_type, "__args__") else None
            )

            # check that the outer container and inner container types are lists or tuples.
            if not (
                types._issubclass(types.get_base_class(outer_type), allowed_subclasses)
                and (
                    inner_type is None
                    or types._issubclass(
                        types.get_base_class(inner_type), allowed_subclasses
                    )
                )
            ):
                raise TypeError(
                    f"table rows should be a list or tuple containing inner lists or tuples. Got {outer_type} instead"
                )
        elif not (
            types._issubclass(type(rows), allowed_subclasses)
            and (not rows or types._issubclass(type(rows[0]), allowed_subclasses))
        ):
            raise TypeError(
                "table rows should be a list or tuple containing inner lists or tuples."
            )


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
        """
        if len(children) == 0:
            cls.validate_footers(footers)
            children = [Tr.create(cell_type="header", cells=footers)]
        return super().create(*children, **props)

    @staticmethod
    def validate_footers(footers):
        """Type checking for table footers.

        Args:
            footers: Table rows.

        Raises:
            TypeError: If footers are not of type list.
        """
        allowed_types = (list, tuple)
        if (
            (
                isinstance(footers, Var)
                and not types.check_type_in_allowed_types(footers.type_, allowed_types)
            )
            or not isinstance(footers, Var)
            and not types.check_type_in_allowed_types(type(footers), allowed_types)
        ):
            raise TypeError("table headers should be a list or tuple")


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
