---
meta_description: "Transform and format AG Grid cell values in Python with Reflex. Use value getters, formatters, and setters to control how data displays in your data grid."
order: 2
---

```python exec
import reflex as rx
import reflex_enterprise as rxe
```

# Value Transformers

AgGrid allow you to apply transformers based on the column of your grid. This allow you to perform operations on the data before displaying it on the grid, without having to pre-process the data on the backend, reducing the load on your application.

TOC:
- [Value Getter](#value-getter)
- [Value Formatter](#value-formatter)
- [Formatter Patterns](#formatter-patterns)
- [Cell Renderer](#cell-renderer)

## Value Getter

`value_getter` is a property of the column definition that allows you to define a function that will be called to get the value of the cell. This function will receive the row data as a parameter and should return the value to be displayed on the cell.

If you have two columns `col_a` and `col_b` and you want to display the sum of these two columns in a third column `sum`, you can define the `value_getter` of `sum` as follows:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
import pandas as pd


df = pd.DataFrame({"col_a": [1, 2, 3, 4, 5], "col_b": [10, 20, 30, 40, 50]})

column_defs = [
    {"field": "col_a", "header_name": "Column A"},
    {"field": "col_b", "header_name": "Column B"},
    {
        "field": "sum",
        "header_name": "Sum",
        "value_getter": "params.data.col_a + params.data.col_b",
    },
    rxe.ag_grid.column_def(
        field="diff",
        header_name="Difference",
        value_getter="params.data.col_b - params.data.col_a",
    ),
]


def ag_grid_value_getter():
    return rxe.ag_grid(
        id="ag_grid_value_getter",
        row_data=df.to_dict("records"),
        column_defs=column_defs,
        width="100%",
    )
```

## Value Formatter

`value_formatter` is a property of the column definition that allows you to define a function that will be called to format the value of the cell. This function will receive the value of the cell as a parameter and should return the formatted value to be displayed on the cell.

If you have a column `price` and you want to display the price with a currency symbol, you can define the `value_formatter` of `price` as follows:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
import pandas as pd

df = pd.DataFrame({
    "product_name": ["Product A", "Product B", "Product C", "Product D", "Product E"],
    "price": [100, 200, 300, 400, 500],
})
column_defs = [
    {"field": "product_name", "header_name": "Product Name"},
    {
        "field": "price",
        "header_name": "Price ($)",
        "value_formatter": "'$' + params.value",
    },
    rxe.ag_grid.column_def(
        col_id="price_eur",
        header_name="Price (€)",
        value_formatter="params.data.price + ' €'",
    ),
]


def ag_grid_value_formatter():
    return rxe.ag_grid(
        id="ag_grid_value_formatter",
        row_data=df.to_dict("records"),
        column_defs=column_defs,
        width="100%",
    )
```

## Formatter Patterns

Formatters and getters can be written in a few different styles. Simple inline JavaScript expressions are the most reliable and should be preferred:

```python
column_defs = [
    {"field": "name", "value_formatter": "params.value.toUpperCase()"},
    {"field": "price", "value_formatter": "'$' + params.value.toFixed(2)"},
    {"field": "percent", "value_formatter": "(params.value * 100).toFixed(1) + '%'"},
    {"field": "date", "value_formatter": "new Date(params.value).toLocaleDateString()"},
    # Conditional logic works inline with a ternary
    {"field": "score", "value_formatter": "params.value > 100 ? 'High' : 'Low'"},
]
```

Python lambdas are useful for basic type conversions — the lambda receives a `params` var and operates on it symbolically:

```python
column_defs = [
    {
        "field": "number",
        "value_formatter": lambda params: round(params.value.to(float), 2),
    },
    {"field": "status", "value_formatter": lambda params: params.value.to(str).title()},
]
```

Short arrow functions can also be passed via `rx.vars.FunctionStringVar`:

```python
CURRENCY_FORMATTER = rx.vars.FunctionStringVar.create(
    "(params) => '$' + params.value.toFixed(2)"
)
column_defs = [{"field": "price", "value_formatter": CURRENCY_FORMATTER}]
```

Keep JavaScript formatters short: multi-line function bodies with complex conditionals often fail to render. If the logic doesn't fit a simple expression, compute the value on the backend instead, or use a [cell renderer](#cell-renderer).

Formatters and getters are always passed directly in the column definition — they are not registered as AG Grid "components".

## Cell Renderer

While formatters change the displayed text, `cell_renderer` replaces the cell contents with a Reflex component. The renderer is a lambda that receives the cell `params` and returns a component:

```python
column_defs = [
    {
        "field": "number",
        "cell_renderer": lambda params: rx.text(
            params.value,
            font_family="monospace",
            color="rebeccapurple",
        ),
    },
    # params.valueFormatted holds the output of the column's value_formatter
    {
        "field": "total",
        "cell_renderer": lambda params: rx.tooltip(
            rx.text(params.valueFormatted, line_height="inherit", width="fit-content"),
            content=f"{params.data.number} * {params.data.percent}",
            side="left",
        ),
    },
]
```

### Interactive Cell Renderers

Renderers that use state or event handlers must be defined as an `@rx.memo` component. Pass it to `cell_renderer` through a lambda, with all arguments given by keyword — never pass the memoized function itself directly:

```python
@rx.memo
def row_action_button(rowid: str) -> rx.Component:
    return rx.flex(
        rx.button(
            RowClickCounterState.row_clicks.get(rowid, 0),
            on_click=RowClickCounterState.handle_click(rowid),
        ),
        height="100%",
        align="center",
    )


column_defs = [
    {
        "field": "actions",
        "cell_renderer": lambda params: row_action_button(rowid=params.node.id),
    },
]
```
