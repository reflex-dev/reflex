"""Module to implement lazy loading in reflex."""
import copy

import lazy_loader as lazy


def attach(package_name, submodules=None, submod_attrs=None):
    """Replace a package's __getattr__, __dir__ and __all__ via
    lazy.attach. Lazy loader __getattr__ doesnt support tuples as list values.
    We needed to add this functionality(tuples) in reflex to support 'import as _'
    cases. We reformat the submod_attrs dict to make sure only the module name(not the
    alias) is present in the list before passing over ot lazy_loader.

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
            _submod_attrs[k] = [
                mod if not isinstance(mod, tuple) else mod[0] for mod in v
            ]

    return lazy.attach(
        package_name=package_name, submodules=submodules, submod_attrs=_submod_attrs
    )
