Formatting a backend var as a string, e.g. `width=f"{State._size}px"`, now raises `BackendVarFormatError` (a `VarTypeError`) instead of silently embedding the field's repr in the page.
