"""Components that type a prop of their parents more narrowly in the stub.

This module tests:
- `_pyi_overwrite_types`: the annotation a class gives a prop in its stub
- `_pyi_imports`: the names those annotations need, imported into the stub
- Both are inherited by subclasses, which may overwrite them again
- A class without them keeps the annotation every component has
"""

from typing import ClassVar

from reflex_base.components.component import Component
from reflex_base.vars.base import Var


class TypedStyleComponent(Component):
    """A component whose style is typed more narrowly than a mapping."""

    _pyi_overwrite_types: ClassVar[dict[str, str]] = {
        "style": "OrderedDict[str, str] | None",
    }
    _pyi_imports: ClassVar[dict[str, list[str]]] = {
        "collections": ["OrderedDict"],
    }

    # The title displayed on the component.
    title: Var[str]


class InheritingComponent(TypedStyleComponent):
    """A component that inherits the annotation of its parent."""

    # The count to display.
    count: Var[int]


class RetypedComponent(TypedStyleComponent):
    """A component that overwrites one of its own props as well."""

    _pyi_overwrite_types: ClassVar[dict[str, str]] = {
        **TypedStyleComponent._pyi_overwrite_types,
        "title": "Decimal | None",
    }
    _pyi_imports: ClassVar[dict[str, list[str]]] = {
        **TypedStyleComponent._pyi_imports,
        "decimal": ["Decimal"],
    }


class PlainComponent(Component):
    """A component that keeps the annotation every component has."""

    # The label of the component.
    label: Var[str]
