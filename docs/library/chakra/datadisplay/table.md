---
components:
    - rx.chakra.Table
    - rx.chakra.TableCaption
    - rx.chakra.Thead
    - rx.chakra.Tbody
    - rx.chakra.Tfoot
    - rx.chakra.Tr
    - rx.chakra.Th
    - rx.chakra.Td
    - rx.chakra.TableContainer
---

```python exec
import reflex as rx
```

# Table

Tables are used to organize and display data efficiently.
The table component differs from the `data_table`` component in that it is not meant to display large amounts of data.
It is meant to display data in a more organized way.

Tables can be created with a shorthand syntax or by explicitly creating the table components.
The shorthand syntax is great for simple tables, but if you need more control over the table you can use the explicit syntax.

Let's start with the shorthand syntax.
The shorthand syntax has `headers`, `rows`, and `footers` props.

```python demo
rx.chakra.table_container(
    rx.chakra.table(
        headers=["Name", "Age", "Location"],
        rows=[
            ("John", 30, "New York"),
            ("Jane", 31, "San Francisco"),
            ("Joe", 32, "Los Angeles")
        ],
        footers=["Footer 1", "Footer 2", "Footer 3"],
        variant='striped'
    )
)
```

Let's create a simple table explicitly. In this example we will make a table with 2 columns: `Name` and `Age`.

```python demo
rx.chakra.table(
    rx.chakra.thead(
        rx.chakra.tr(
            rx.chakra.th("Name"),
            rx.chakra.th("Age"),
        )
    ),
    rx.chakra.tbody(
        rx.chakra.tr(
            rx.chakra.td("John"),
            rx.chakra.td(30),
        )
    ),
)
```

In the examples we will be using this data to display in a table.

```python exec
columns = ["Name", "Age", "Location"]
data = [
    ["John", 30, "New York"],
    ["Jane", 25, "San Francisco"],
]
footer = ["Footer 1", "Footer 2", "Footer 3"]
```

```python
columns = ["Name", "Age", "Location"]
data = [
    ["John", 30, "New York"],
    ["Jane", 25, "San Francisco"],
]
footer = ["Footer 1", "Footer 2", "Footer 3"]
```

Now lets create a table with the data we created.

```python eval
rx.chakra.center(
    rx.chakra.table_container(
        rx.chakra.table(
            rx.chakra.table_caption("Example Table"),
            rx.chakra.thead(
                rx.chakra.tr(
                    *[rx.chakra.th(column) for column in columns]
                )
            ),
            rx.chakra.tbody(
                *[rx.chakra.tr(*[rx.chakra.td(item) for item in row]) for row in data]
            ),
            rx.chakra.tfoot(
                rx.chakra.tr(
                    *[rx.chakra.th(item) for item in footer]
                )
            ),
        )
    )
)
```

Tables can also be styled with the variant and color_scheme arguments.

```python demo
rx.chakra.table_container(
    rx.chakra.table(
        rx.chakra.thead(
        rx.chakra.tr(
            rx.chakra.th("Name"),
            rx.chakra.th("Age"),
            rx.chakra.th("Location"),
            )
        ),
        rx.chakra.tbody(
            rx.chakra.tr(
                rx.chakra.td("John"),
                rx.chakra.td(30),
                rx.chakra.td("New York"),
            ),
            rx.chakra.tr(
                rx.chakra.td("Jane"), 
                rx.chakra.td(31),
                rx.chakra.td("San Francisco"),
            ),
            rx.chakra.tr(
                rx.chakra.td("Joe"),
                rx.chakra.td(32),
                rx.chakra.td("Los Angeles"),
            )
        ),
        variant='striped',
        color_scheme='teal'
    )
)
```
