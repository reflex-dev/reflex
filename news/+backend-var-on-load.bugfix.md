`app.add_page(...)` now raises `BackendVarFormatError` when `on_load` is a backend var such as `State._handler`, instead of accepting it.
