"""Constants used to compile element classes."""

from collections import defaultdict

from reflex.utils import format

from .html import ATTR_TO_ELEMENTS
from .react import POSSIBLE_STANDARD_NAMES

# Maps HTML attributes that are invalid Python identifiers to their Reflex
# prop equivalents.
ATTR_TO_PROP_OVERRIDES = {
    "async": "async_",  # `async` is a reserved keyword in Python.
}


def attr_to_prop(attr_name: str) -> str:
    """Convert an HTML attribute name to its Reflex name.

    This function first uses React's `possibleStandardNames` to convert the
    HTML attribute name to its standard React name, then converts the standard
    name to a Reflex name.

    Args:
        attr_name: The HTML attribute name.

    Returns:
        A Reflex prop name that maps to the HTML attribute.
    """
    if attr_name in ATTR_TO_PROP_OVERRIDES:
        return ATTR_TO_PROP_OVERRIDES[attr_name]
    return format.to_snake_case(POSSIBLE_STANDARD_NAMES.get(attr_name, attr_name))


# Names of HTML attributes that are provided by Reflex out of the box.
REFLEX_PROVIDED_ATTRS = {"class", "id", "style"}

# ATTR_TO_ELEMENTS contains HTML attribute names, which might be invalid as
# Reflex prop names. PROP_TO_ELEMENTS contains the corresponding Reflex
# prop names. It omits props that are provided by Reflex out of the box.
PROP_TO_ELEMENTS = {
    attr_to_prop(attr_name): elements
    for attr_name, elements in ATTR_TO_ELEMENTS.items()
    if attr_name not in REFLEX_PROVIDED_ATTRS
}

# Invert PROP_TO_ELEMENTS to enable easier lookup.
ELEMENT_TO_PROPS = defaultdict(list)
for prop, elements in PROP_TO_ELEMENTS.items():
    for el in elements:
        ELEMENT_TO_PROPS[el].append(prop)
