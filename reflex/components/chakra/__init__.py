"""Chakra components."""


import importlib
from typing import Type

from .media.image import Image

image = Image.create

# _MAPPING = {
#     "image": "media",
# }


# def __getattr__(name: str) -> Type:
#     print(f"importing {name}")
#     if name not in _MAPPING:
#         return importlib.import_module(name)

#     module = importlib.import_module(_MAPPING[name], package=".")

#     return getattr(module, name) if name != _MAPPING[name].rsplit(".")[-1] else module
