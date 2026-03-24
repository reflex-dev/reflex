---
order: 2
---

```python exec
import reflex as rx
import reflex_enterprise as rxe
from pcweb.pages.docs import enterprise
```

# Value Transformers

AgGrid allow you to apply transformers based on the column of your grid. This allow you to perform operations on the data before displaying it on the grid, without having to pre-process the data on the backend, reducing the load on your application.

TOC:
- [Value Getter](#value-getter)
- [Value Formatter](#value-formatter)

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
    {"field": "sum", "header_name": "Sum", "value_getter": "params.data.col_a + params.data.col_b"},
    rxe.ag_grid.column_def(field="diff", header_name="Difference", value_getter="params.data.col_b - params.data.col_a"),
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

df = pd.DataFrame({"product_name":["Product A", "Product B", "Product C", "Product D", "Product E"], "price": [100, 200, 300, 400, 500]})
column_defs = [
    {"field": "product_name", "header_name": "Product Name"},
    {"field": "price", "header_name": "Price ($)", "value_formatter": "'$' + params.value"},
    rxe.ag_grid.column_def(col_id="price_eur", header_name="Price (€)", value_formatter="params.data.price + ' €'"),
]

def ag_grid_value_formatter():
    return rxe.ag_grid(
        id="ag_grid_value_formatter",
        row_data=df.to_dict("records"),
        column_defs=column_defs,
        width="100%",
    )
```


