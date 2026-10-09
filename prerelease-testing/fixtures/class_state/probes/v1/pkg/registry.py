"""A plugin registry module: the dict is filled when plugin modules are imported."""
PLUGINS: dict[str, str] = {}


def register(fn):
    PLUGINS[fn.__name__] = fn.__doc__ or fn.__name__
    return fn
