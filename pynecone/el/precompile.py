"""Dynamically compile classes for all HTML elements and output them to the
elements directory.

This script generates the element classes in the pynecone.el.elements module.
Run as follows:

    python -m pynecone.el.precompile

Make sure to delete the __init__.py file in the elements directory before
running this script.
"""

import os

from .constants import ELEMENT_TO_PROPS, ELEMENTS

FILE_DIR = os.path.dirname(os.path.realpath(__file__))
ELEMENTS_DIR = os.path.join(FILE_DIR, "elements")
INIT_PY_PATH = os.path.join(ELEMENTS_DIR, "__init__.py")


def pyclass_name(element: str) -> str:
    """Get the name of the Python class for the given element."""
    return element.capitalize()


def element_path(element: str) -> str:
    """Get the name of the Python file for the given element."""
    return os.path.join(ELEMENTS_DIR, f"{element}.py")


def compile_pyclass_props(element: str):
    """Compile props for an element."""
    return "\n".join(
        f"    {prop}: PCVar[Union[str, int, bool]]"
        for prop in ELEMENT_TO_PROPS[element]
    )


TEMPLATE = """
class {pyclass}(Element):  # noqa: E742
    \"\"\"Display the {name} element.\"\"\"

    tag = "{name}"

{props}


{name} = {pyclass}.create
"""


INIT_PY = [
    '"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""',
    "from typing import Union",
    "",
    "from pynecone.el.element import Element",
    "from pynecone.var import Var as PCVar",
    "",
]


for element in sorted(ELEMENTS):
    # Name of the Python class we're generating.
    pyclass = pyclass_name(element)

    # Handle the "del" element, which is a Python keyword.
    # Note that the class name is still "Del".
    element_name_override = "del_" if element == "del" else element

    code = TEMPLATE.format(
        name=element_name_override,
        pyclass=pyclass,
        props=compile_pyclass_props(element),
    )

    # Add the element to the __init__.py file.
    INIT_PY.append(code)


os.makedirs(ELEMENTS_DIR, exist_ok=True)
with open(INIT_PY_PATH, "w+") as f:
    f.write("\n".join(INIT_PY))
