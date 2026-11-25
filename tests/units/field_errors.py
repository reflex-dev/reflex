"""Expected messages of the error for a field with no frontend var."""

_REPR_HINT = " To print or log the field itself in server code, use repr()."


def backend_var_error(path: str) -> str:
    """Build the full error message for using a backend var in the UI.

    Args:
        path: The backend var as ``State._name``.

    Returns:
        The complete error message.
    """
    return (
        f"Backend var '{path}' exists only on the server and has no frontend"
        f" value, so it cannot be used in the UI. Use {path}.default_value() for"
        " its default value, declare it as ClassVar[...] for a constant shared by"
        " all sessions, or use a regular state var for a value the UI should show"
        " and update." + _REPR_HINT
    )


def mixin_var_error(path: str) -> str:
    """Build the full error message for using a mixin's field in the UI.

    Args:
        path: The field as ``Mixin.name``.

    Returns:
        The complete error message.
    """
    return (
        f"Var '{path}' is declared on a mixin state, which has no frontend vars."
        " Access it through a state that includes the mixin instead." + _REPR_HINT
    )
