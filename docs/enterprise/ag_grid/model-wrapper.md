---
meta_description: "Wire AG Grid to a pandas DataFrame or a Reflex database model in Python. The model wrapper renders and edits your data in an interactive data grid, all in pure Python."
order: 6
---

# Model Wrapper

A model wrapper is an utility used to wrap a database model and provide a consistent interface over it. It allows automatically adding new rows to the database, updating existing rows, and deleting rows.

## Default Model Wrapper

You can use the basic functionality of the model wrapper by using the `rxe.model_wrapper` function. This function takes a database model and returns a wrapper object that can be used to interact with the model.

```python
import reflex as rx
import reflex_enterprise as rxe


def index_page():
    return rx.box(
        rxe.model_wrapper(model_class=MyModel, width="100%"),
        height="80vh",
    )
```

By default the model_wrapper use the infinite rows model from AgGrid. As the user scrolls, the wrapper automatically loads windows of rows from the database instead of loading the whole table into memory. The cache size can be tuned with the `max_blocks_in_cache` and `cache_block_size` props.

```md alert warning
# Always place the model wrapper in a container with a calculable height.
If the containing element has no fixed height, the grid will not render. Setting e.g. `height="80vh"` on the parent box is enough.
```

The model passed as `model_class` must exactly match the schema of the database table backing it, or querying will fail. In particular, don't invent a primary key that the actual table doesn't have.

## Custom Model Wrapper

If the default model wrapper does not fit your needs, you can create a custom model wrapper by subclassing the `rxe.ModelWrapper` class. This allows you to customize the behavior of the model wrapper to fit your specific use case.

```python
import reflex_enterprise as rxe


class MyCustomWrapper(rxe.ModelWrapper[MyModel]):
    pass
```

In the custom model wrapper, you can override the following methods:
- `_get_columns_defs`
- `_get_data`
- `_row_count`
- `on_value_setter`

to modify how the model wrapper will behave.

A custom wrapper is rendered with its `create` classmethod:

```python
def index_page():
    return rx.box(
        MyCustomWrapper.create(model_class=MyModel, width="100%"),
        height="80vh",
    )
```

### Authorization

By default there is no authentication checking for any database operation performed through the grid — inserts, updates, and deletes are open to any user who can reach the page. To restrict operations, override the `_is_authorized` method in a `ModelWrapper` subclass:

```python
from typing import Sequence

import reflex_enterprise as rxe
from reflex_enterprise.components.ag_grid.wrapper import ModelWrapperActionType


class UserModelWrapper(rxe.ModelWrapper[User]):
    async def _is_authorized(
        self,
        action: ModelWrapperActionType,
        action_data: Sequence[User] | dict | None,
    ) -> bool:
        """Check if the user is authorized to perform the action.

        For SELECT, action_data is None.
        For INSERT, action_data is a dict of the new row data.
        For UPDATE, action_data is a dict of updated row data.
        For DELETE, action_data is a list of model objects to delete.
        """
        auth_state = await self.get_state(AuthState)
        return auth_state.user_is_admin
```

### Customizing Columns and Toolbar

Override `_get_column_defs` to adjust the generated column definitions — for example to disable filtering or sorting on a specific field:

```python
class UserModelWrapper(rxe.ModelWrapper[User]):
    def _get_column_defs(self):
        cols = super()._get_column_defs()
        for col in cols:
            if col.field == "internal_notes":
                col.filter = None
                col.sortable = False
        return cols
```

The toolbar UI can be customized as well: override the `_top_toolbar`, `_delete_button`, and `_add_dialog` classmethods to replace the default add/delete controls with your own components.

## SSRM Model Wrapper

The SSRM model wrapper, used with `rxe.model_wrapper_ssrm`, is a version of the model wrapper that allows you to use the ServerSideRowModel of AgGrid.

```python
import reflex as rx
import reflex_enterprise as rxe


def index_page():
    return rx.box(
        rxe.model_wrapper_ssrm(model_class=MyModel, width="100%"),
        height="80vh",
    )
```

## SSRM Custom Model Wrapper

In the same way you can extend the default model wrapper, you can extend the SSRM custom model wrapper by subclassing the `rxe.ModelWrapperSSRM` class. This allows you to customize the behavior of the model wrapper to fit your specific use case.

```python
import reflex_enterprise as rxe


class MyCustomSSRMWrapper(rxe.ModelWrapperSSRM[MyModel]):
    pass
```

The overridable methods are the same as the standard model wrapper.