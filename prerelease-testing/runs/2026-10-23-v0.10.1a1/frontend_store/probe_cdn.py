"""#7405: the dynamic-component serializer's CDN fallback for sub-path imports.

Run with each venv:  EXPECT_VENV=new $SB/envs/new/bin/python probe_cdn.py
Prints the import lines the serializer generates for a component whose library is a
sub-path of a package that is NOT bundled into the frontend.
"""

import os

import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__

from reflex_base.components.dynamic import load_dynamic_serializer  # noqa: E402
from reflex_base.utils.serializers import serialize  # noqa: E402


class SubpathIcon(rx.Component):
    library = "react-icons/fa"
    tag = "FaBeer"


class RootLib(rx.Component):
    library = "some-unbundled-lib"
    tag = "Thing"


class DeepSubpath(rx.Component):
    library = "@scope/pkg/dist/esm"
    tag = "Deep"


# serializer is registered when reflex is imported
for cls in (SubpathIcon, RootLib, DeepSubpath):
    code = serialize(cls.create())
    print(f"== {cls.__name__} ({cls.library})")
    for line in code.splitlines():
        if "import" in line and ("cdn" in line or "+esm" in line or "__reflex" in line):
            print("  ", line.strip()[:200])


from reflex_base.utils.imports import ImportVar  # noqa: E402


class PkgPath(rx.Component):
    """Imports its tag from a sub-path via ImportVar(package_path=...), the #7405 case."""

    tag = "FaCoffee"

    def add_imports(self):
        return {"react-icons": ImportVar(tag="FaCoffee", package_path="/fa")}


code = serialize(PkgPath.create())
print("== PkgPath (react-icons + package_path=/fa)")
for line in code.splitlines():
    if "import" in line and ("cdn" in line or "+esm" in line or "__reflex" in line):
        print("  ", line.strip()[:200])
