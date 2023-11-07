"""Import all classes and functions the end user will need to make an app.

Anything imported here will be available in the default Reflex import as `rx.*`.
To signal to typecheckers that something should be reexported,
we use the Flask "import name as name" syntax.
"""

_MAPPING = {
    "reflex.admin": ["AdminDash"],
    "reflex.app": ["App", "UploadFile"],
    "reflex.base": ["Base"],
    "reflex.compiler.utils": ["get_asset_path"],
    "reflex.components.component": ["memo"],
    "reflex.components.graphing": ["reccharts"],
    "reflex.config": ["Config", "DBConfig"],
    "reflex.constants": ["constants", "Env"],
    "reflex.event": ["EventChain", "FileUpload", "background", "call_script", "clear_local_storage", "console_log", "download", "prevent_default", "redirect", "remove_cookie", "remove_local_storage", "set_clipboard", "set_focus", "set_value", "stop_propagation", "window_alert"],
    "reflex.middleware": ["Middleware"],
    "reflex.model": ["model", "session", "Model"],
    "reflex.page": ["page"],
    "reflex.state": ["var", "Cookie", "LocalStorage", "State"],
    "reflex.style": ["color_mode", "toggle_color_mode"],
    "reflex.vars": ["cached_var", "Var"],
}
_MAPPING = {value: key for key, values in _MAPPING.items() for value in values}


def __getattr__(name):
    """Lazy load all modules."""
    import importlib
    # Import the module.
    module = importlib.import_module(_MAPPING[name])
    # Add the module to the globals.
    globals()[name] = module
    # Get the attribute from the module if the name is not the module itself.
    attr = getattr(module, name) if name != _MAPPING[name] else module
    # Return the attribute.
    return attr

# from . import el as el
# from .components import *
