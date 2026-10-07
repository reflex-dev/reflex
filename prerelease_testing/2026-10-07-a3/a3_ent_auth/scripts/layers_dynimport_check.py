"""Print the dynamic-import line reflex generates for rxe LayersControlBaseLayer / Overlay (no server needed).

Usage: <venv>/bin/python -I layers_dynimport_check.py <expected-venv-substring>
"""
import sys

import reflex as rx

assert sys.argv[1] in rx.__file__, rx.__file__
import importlib.metadata

from reflex_enterprise.components.map.controls import LayersControlBaseLayer, LayersControlOverlay

print("reflex", importlib.metadata.version("reflex"), "rxe", importlib.metadata.version("reflex-enterprise"))
for cls in (LayersControlBaseLayer, LayersControlOverlay):
    comp = cls.create(name="x")
    print(cls.__name__, "->", comp._get_dynamic_imports())
