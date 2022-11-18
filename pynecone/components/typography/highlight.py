"""A heading component."""

from typing import List, Union

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Highlight(ChakraComponent):
    """Highlights a specific part of a string."""

    tag = "Highlight"

    # A query for the text to highlight. Can be a string or a list of strings.
    query: Var[List[str]]
