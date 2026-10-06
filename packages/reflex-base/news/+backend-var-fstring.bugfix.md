Using a backend var (prefixed with `_`) in an f-string, e.g. `width=f"{State._size}px"`, now raises `VarTypeError` instead of silently embedding the field's repr in the page.
