"""Module to implement lazy loading in reflex."""

import copy

import lazy_loader as lazy


def attach(package_name, submodules=None, submod_attrs=None):
    """Replaces a package's __getattr__, __dir__, and __all__ attributes using lazy.attach.
    The lazy loader __getattr__ doesn't support tuples as list values. We needed to add
    this functionality (tuples) in Reflex to support 'import as _' statements. This function
    reformats the submod_attrs dictionary to flatten the module list before passing it to
    lazy_loader.

    Args:
        package_name: name of the package.
        submodules : List of submodules to attach.
        submod_attrs : Dictionary of submodule -> list of attributes / functions.
                    These attributes are imported as they are used.

    Returns:
        __getattr__, __dir__, __all__
    """
    _submod_attrs = copy.deepcopy(submod_attrs)
    if _submod_attrs:
        for k, v in _submod_attrs.items():
            # when flattening the list, only keep the alias in the tuple(mod[1])
            _submod_attrs[k] = [
                mod if not isinstance(mod, tuple) else mod[1] for mod in v
            ]

    return lazy.attach(
        package_name=package_name, submodules=submodules, submod_attrs=_submod_attrs
    )
