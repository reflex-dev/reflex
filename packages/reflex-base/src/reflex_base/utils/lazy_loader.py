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

import importlib
import os
import sys
from collections.abc import Mapping, Sequence

SubmodAttrsType = Mapping[str, Sequence[str | tuple[str, str]]]

# PEP 810 explicit lazy imports, available from Python 3.15
_NATIVE_LAZY_IMPORTS = sys.version_info >= (3, 15)


def _attach_native(
    package_name: str,
    submodules: set[str],
    alias_to_module_and_attr: Mapping[str, tuple[str, str]],
    extra_mappings: Mapping[str, str],
) -> bool:
    """Bind native lazy import proxies (PEP 810) in the package namespace.

    Names already bound in the package namespace are left untouched.

    Args:
        package_name: name of the package.
        submodules: Set of submodules to attach.
        alias_to_module_and_attr: Mapping of alias -> (submodule, attribute).
        extra_mappings: Mapping of alias -> absolute dotted import path.

    Returns:
        False if the caller should fall back to the classic
        __getattr__-based mechanism.
    """
    package = sys.modules.get(package_name)
    if package is None:
        return False

    # Names are embedded in generated import statements below, so ensure
    # they are identifiers and not arbitrary code.
    names = [package_name, *submodules]
    for alias, (mod, attr) in alias_to_module_and_attr.items():
        names += [alias, mod, attr]
    for alias, path in extra_mappings.items():
        names += [alias, path]
    if not all(part.isidentifier() for name in names for part in name.split(".")):
        return False

    pkg_dict = vars(package)

    # Filters preserve the classic lookup priority:
    # extra_mappings > submodules > submod_attrs.
    lines: list[str] = []
    for alias, path in extra_mappings.items():
        if alias in pkg_dict:
            continue
        if "." not in path:
            lines.append(f"lazy import {path} as {alias}")
        else:
            mod, _, attr = path.rpartition(".")
            lines.append(f"lazy from {mod} import {attr} as {alias}")
    lines += [
        f"lazy from {package_name} import {name}"
        for name in sorted(submodules)
        if name not in pkg_dict and name not in extra_mappings
    ]
    lines += [
        f"lazy from {package_name}.{mod} import {attr} as {alias}"
        for alias, (mod, attr) in alias_to_module_and_attr.items()
        if alias not in pkg_dict
        and alias not in extra_mappings
        and alias not in submodules
    ]

    if not lines:
        return True

    try:
        code = compile(
            "\n".join(lines), f"<lazy_loader.attach {package_name!r}>", "exec"
        )
    except SyntaxError:
        # A name that is not expressible as import syntax (e.g. a keyword)
        return False

    exec(code, pkg_dict)
    return True


def attach(
    package_name: str,
    submodules: set[str] | None = None,
    submod_attrs: SubmodAttrsType | None = None,
    **extra_mappings: str,
):
    """Replaces a package's __getattr__, __dir__, and __all__ attributes using lazy.attach.
    The lazy loader __getattr__ doesn't support tuples as list values. We needed to add
    this functionality (tuples) in Reflex to support 'import as _' statements. This function
    reformats the submod_attrs dictionary to flatten the module list before passing it to
    lazy_loader.

    On Python 3.15 and newer, this delegates to the interpreter's native
    lazy import mechanism (PEP 810) whenever possible.

    Args:
        package_name: name of the package.
        submodules : List of submodules to attach.
        submod_attrs : Dictionary of submodule -> list of attributes / functions.
                    These attributes are imported as they are used.
        extra_mappings: Additional mappings to resolve lazily.

    Returns:
        __getattr__, __dir__, __all__
    """
    if submod_attrs is None:
        submod_attrs = {}

    submodules = set(submodules) if submodules is not None else set()

    alias_to_module_and_attr = {
        comp_alias(attr): (mod, comp_name(attr))
        for mod, attrs in submod_attrs.items()
        for attr in attrs
    }

    __all__ = sorted([
        *(submodules | alias_to_module_and_attr.keys()),
        *(extra_mappings or []),
    ])

    def __getattr__(name: str):  # noqa: N807
        if name in extra_mappings:
            path = extra_mappings[name]
            if "." not in path:
                attr = importlib.import_module(path)
            else:
                submod_path, attr_name = path.rsplit(".", 1)
                submod = importlib.import_module(submod_path)
                attr = getattr(submod, attr_name)
        elif name in submodules:
            attr = importlib.import_module(f"{package_name}.{name}")
        elif name in alias_to_module_and_attr:
            module, attr_name = alias_to_module_and_attr[name]
            submod = importlib.import_module(f"{package_name}.{module}")
            attr = getattr(submod, attr_name)
        else:
            msg = f"No {package_name} attribute {name}"
            raise AttributeError(msg)

        # Cache the resolved value on the package so that subsequent
        # accesses bypass __getattr__; this also ensures an attribute
        # shadows a same-named submodule.
        pkg = sys.modules.get(package_name)
        if pkg is not None:
            pkg.__dict__[name] = attr

        return attr

    def __dir__():  # noqa: N807
        return __all__

    if os.environ.get("EAGER_IMPORT", ""):
        for attr in set(alias_to_module_and_attr.keys()) | submodules:
            __getattr__(attr)
    elif _NATIVE_LAZY_IMPORTS:
        # On Python 3.15+, bind native lazy imports (PEP 810) directly in
        # the package namespace; the returned __getattr__ is then only
        # consulted for unknown names.  Falls back to the classic
        # __getattr__ mechanism when native binding is not possible.
        _attach_native(
            package_name, submodules, alias_to_module_and_attr, extra_mappings
        )

    return __getattr__, __dir__, list(__all__)


def comp_name(comp: str | tuple[str, str]) -> str:
    """Get the component name from the mapping value.

    This is the name used internally in the codebase.

    Args:
        comp: The component name or a tuple of (component name, alias).

    Returns:
        The component name.
    """
    return comp[0] if isinstance(comp, tuple) else comp


def comp_alias(comp: str | tuple[str, str]) -> str:
    """Get the component alias from the mapping value.

    This is the name external users will import.

    Args:
        comp: The component name or a tuple of (component name, alias).

    Returns:
        The component alias, or the compoenent name if there is no alias.
    """
    return comp[1] if isinstance(comp, tuple) else comp


def comp_path(path: str, comp: str | tuple[str, str]) -> str:
    """Get the component path from the mapping key and value.

    This is the internal path that will be imported.

    Args:
        path: The base path of the component.
        comp: The component name or a tuple of (component name, alias).

    Returns:
        The component path.
    """
    return path + "." + comp_name(comp)
