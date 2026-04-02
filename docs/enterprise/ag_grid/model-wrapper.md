---
order: 6
---

# Model Wrapper

A model wrapper is an utility used to wrap a database model and provide a consistent interface over it. It allows automatically adding new rows to the database, updating existing rows, and deleting rows.

## Default Model Wrapper

You can use the basic functionality of the model wrapper by using the `rxe.model_wrapper` function. This function takes a database model and returns a wrapper object that can be used to interact with the model.

```python
import reflex_enterprise as rxe

def index_page():
    return rxe.model_wrapper(class_model=MyModel)
```

By default the model_wrapper use the infinite rows model from AgGrid.

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


## SSRM Model Wrapper

The SSRM model wrapper, used with `rxe.model_wrapper_ssrm`, is a version of the model wrapper that allows you to use the ServerSideRowModel of AgGrid.

```python
import reflex_enterprise as rxe

def index_page():
    return rxe.model_wrapper_ssrm(class_model=MyModel)
```

## SSRM Custom Model Wrapper

In the same way you can extend the default model wrapper, you can extend the SSRM custom model wrapper by subclassing the `rxe.ModelWrapperSSRM` class. This allows you to customize the behavior of the model wrapper to fit your specific use case.

```python
import reflex_enterprise as rxe

class MyCustomSSRMWrapper(rxe.ModelWrapperSSRM[MyModel]):
   pass
```

The overridable methods are the same as the standard model wrapper.