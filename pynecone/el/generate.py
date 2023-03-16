"""Dynamically generate element classes.

This script generates the element classes in the pynecone.el.elements module.
Run as follows:

    python -m pynecone.el.generate

Make sure to delete the __init__.py file in the elements directory before
running this script.
"""
import os

from pynecone.el.constants import ELEMENT_TO_PROPS, ELEMENTS

FILE_DIR = os.path.dirname(os.path.realpath(__file__))
ELEMENTS_DIR = os.path.join(FILE_DIR, "elements")
INIT_PY_PATH = os.path.join(ELEMENTS_DIR, "__init__.py")

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
        f"    {prop}: PCVar[Union[str, int, bool]]"
        for prop in ELEMENT_TO_PROPS[element]
    )


TEMPLATE = """
class {pyclass}(Element):
    \"\"\"Display the {name} element.\"\"\"

    tag = "{name}"

{props}


{name} = {pyclass}.create
"""


INIT_PY = [
    """# This is an auto-generated file. Do not edit. See ../generate.py.
from typing import Union
from pynecone.var import Var as PCVar
from pynecone.el.element import Element""",
]


for element in ELEMENTS:
    # Name of the Python class we're generating.
    pyclass = pyclass_name(element)

    # Handle the "del" element, which is a Python keyword.
    # Note that the class name is still "Del".
    element_name_override = "del_" if element == "del" else element

    code = TEMPLATE.format(
        name=element_name_override,
        pyclass=pyclass,
        props=format_prop_attrs(element),
    )

    # Add the element to the __init__.py file.
    INIT_PY.append(code)

# Write the __init__.py file.
with open(INIT_PY_PATH, "w+") as f:
    f.write("\n".join(INIT_PY))
