"""Module to implement lazy loading in reflex.

BSD 3-Clause License

Copyright (c) 2022--2023, Scientific Python project All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

    Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

    Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from __future__ import annotations

import copy
import importlib
import os
import sys


def attach(
    package_name: str,
    submodules: set[str] | None = None,
    submod_attrs: dict[str, list[str]] | None = None,
    **extra_mappings,
):
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
        extra_mappings: Additional mappings to resolve lazily.

    Returns:
        __getattr__, __dir__, __all__
    """
    submod_attrs = copy.deepcopy(submod_attrs)
    if submod_attrs:
        for k, v in submod_attrs.items():
            # when flattening the list, only keep the alias in the tuple(mod[1])
            submod_attrs[k] = [
                mod if not isinstance(mod, tuple) else mod[1] for mod in v
            ]

    if submod_attrs is None:
        submod_attrs = {}

    submodules = set(submodules) if submodules is not None else set()

    attr_to_modules = {
        attr: mod for mod, attrs in submod_attrs.items() for attr in attrs
    }

    __all__ = sorted([*(submodules | attr_to_modules.keys()), *(extra_mappings or [])])

    def __getattr__(name: str):  # noqa: N807
        if name in extra_mappings:
            submod_path, attr = extra_mappings[name].rsplit(".", 1)
            submod = importlib.import_module(submod_path)
            return getattr(submod, attr)
        if name in submodules:
            return importlib.import_module(f"{package_name}.{name}")
        if name in attr_to_modules:
            submod_path = f"{package_name}.{attr_to_modules[name]}"
            submod = importlib.import_module(submod_path)
            attr = getattr(submod, name)

            # If the attribute lives in a file (module) with the same
            # name as the attribute, ensure that the attribute and *not*
            # the module is accessible on the package.
            if name == attr_to_modules[name]:
                pkg = sys.modules[package_name]
                pkg.__dict__[name] = attr

            return attr
        msg = f"No {package_name} attribute {name}"
        raise AttributeError(msg)

    def __dir__():  # noqa: N807
        return __all__

    if os.environ.get("EAGER_IMPORT", ""):
        for attr in set(attr_to_modules.keys()) | submodules:
            __getattr__(attr)

    return __getattr__, __dir__, list(__all__)
