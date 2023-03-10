"""Dynamically generate tag classes."""

import os
from pynecone.el.constants import ELEMENT_TO_PROPS, ELEMENTS

TEMPLATE = """
from typing import Union
from pynecone.var import Var
from pynecone.el.element import Element

class {pyclass}(Element):
    \"\"\"Display the {name} element.\"\"\"

    tag = "{name}"

{props}

{name} = {pyclass}.create
"""


FILE_DIR = os.path.dirname(os.path.realpath(__file__))
ELEMENTS_DIR = os.path.join(FILE_DIR, "elements")

os.makedirs(ELEMENTS_DIR, exist_ok=True)


def pyclass_name(element: str) -> str:
    """Return the name of the Python class for the given element."""
    return element.capitalize()


def element_path(element: str) -> str:
    """Return the name of the Python file for the given element."""
    return os.path.join(ELEMENTS_DIR, f"{element}.py")


def format_prop_attrs(element: str):
    """Return the code for the prop attributes."""
    return "\n".join(
        f"    {prop}: Var[Union[str, int, bool]]" for prop in ELEMENT_TO_PROPS[element]
    )


INIT_PY = []

for element in ELEMENTS:
    # Name of the Python class we're generating.
    pyclass = pyclass_name(element)

    # Handle the "del" element, which is a Python keyword.
    # Note that the class name is still "Del".
    if element == "del":
        element = "del_"

    # Write the code for the class out to a new file.
    code = TEMPLATE.format(
        name=element,
        pyclass=pyclass,
        props=format_prop_attrs(element),
    )
    with open(element_path(element), "w+") as f:
        f.write(code)

    # Add the class to the __init__.py file.
    INIT_PY.append(f"from .{element} import {pyclass}, {element}")

# Write the __init__.py file.
with open(os.path.join(ELEMENTS_DIR, "__init__.py"), "w+") as f:
    f.write("\n".join(INIT_PY))
