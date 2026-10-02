"""Form data submitted to event handlers."""

from __future__ import annotations

import dataclasses
import functools
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, TypeVar, get_origin

from typing_extensions import is_typeddict

from reflex_base.utils import types

__all__ = [
    "FORM_DATA_ENTRIES_KEY",
    "FormData",
    "form_data_as_dict",
    "transform_form_data",
]

# Wire key wrapping a form's ordered ``[name, value]`` entries; must match
# ``FORM_DATA_ENTRIES_KEY`` in ``state.js``.
FORM_DATA_ENTRIES_KEY = "__reflex_form_data__"

_K = TypeVar("_K")
_V_co = TypeVar("_V_co", covariant=True)


class FormData(Mapping[_K, _V_co]):
    """The fields of a submitted form: an immutable mapping keeping every value.

    Indexing, iteration and ``len`` see each name once with its last value, so
    FormData reads like the dict built from the same items. ``getlist`` (or its
    alias ``getAll``, as in the browser's ``FormData``) and ``multi_items``
    expose every value of fields that share a name, in submission order.
    """

    __slots__ = ("_dict", "_items")

    _dict: dict[_K, _V_co]
    _items: tuple[tuple[_K, _V_co], ...]

    def __init__(
        self,
        items: Mapping[_K, _V_co] | Iterable[tuple[_K, _V_co]] = (),
    ) -> None:
        """Build a FormData.

        Args:
            items: ``(key, value)`` pairs, or a mapping; another FormData keeps
                every item.
        """
        if isinstance(items, FormData):
            pairs = items._items
        elif isinstance(items, Mapping):
            pairs = tuple(items.items())
        else:
            pairs = tuple((key, value) for key, value in items)
        object.__setattr__(self, "_items", pairs)
        object.__setattr__(self, "_dict", dict(pairs))

    def __setattr__(self, name: str, value: Any) -> None:
        """Reject attribute assignment.

        Args:
            name: The attribute name.
            value: The attribute value.

        Raises:
            AttributeError: Always, since a FormData is immutable.
        """
        msg = f"{type(self).__name__} is immutable"
        raise AttributeError(msg)

    def __getitem__(self, key: _K) -> _V_co:
        """Get the last value of a key.

        Args:
            key: The key.

        Returns:
            The key's last value.
        """
        return self._dict[key]

    def __iter__(self) -> Iterator[_K]:
        """Iterate over each key once, in order of first appearance.

        Returns:
            An iterator over the keys.
        """
        return iter(self._dict)

    def __len__(self) -> int:
        """Count the distinct keys.

        Returns:
            The number of distinct keys.
        """
        return len(self._dict)

    def __contains__(self, key: object) -> bool:
        """Check whether a key is present.

        Args:
            key: The key.

        Returns:
            Whether the key has at least one value.
        """
        return key in self._dict

    def __eq__(self, other: object) -> bool:
        """Compare to another mapping.

        Args:
            other: The object to compare to.

        Returns:
            For a FormData, whether both hold the same items in the same order;
            for another mapping, whether it equals this one's last values.
        """
        if isinstance(other, FormData):
            return self._items == other._items
        return super().__eq__(other)

    __hash__ = None  # pyright: ignore[reportAssignmentType]

    def __repr__(self) -> str:
        """Represent the FormData by its items.

        Returns:
            The representation.
        """
        return f"{type(self).__name__}({list(self._items)!r})"

    def __reduce__(self) -> tuple[type[FormData[_K, _V_co]], tuple[list]]:
        """Pickle the FormData by its items.

        Returns:
            The class and the arguments that rebuild it.
        """
        return type(self), (list(self._items),)

    def getlist(self, key: _K) -> list[_V_co]:
        """Get every value of a key.

        Args:
            key: The key.

        Returns:
            The key's values in order, empty when the key is absent.
        """
        return [value for item_key, value in self._items if item_key == key]

    getAll = getlist  # noqa: N815

    def multi_items(self) -> list[tuple[_K, _V_co]]:
        """Get every ``(key, value)`` item, repeated keys included.

        Returns:
            The items in order.
        """
        return list(self._items)


@dataclasses.dataclass(frozen=True, slots=True)
class _CoercedFormField:
    """A TypedDict field that submitted form data is coerced into."""

    name: str
    # The names whose values fill the field: a list field also collects the
    # ``name[]`` entries of multi-value controls such as a range slider.
    names: tuple[str, ...]
    is_list: bool
    # An unsubmitted field is left out unless it is required: then it is None
    # when its type allows None, otherwise an empty list or False.
    optional: bool
    required: bool


@functools.cache
def _typed_dict_form_fields(typed_dict: Any) -> tuple[_CoercedFormField, ...]:
    """Find the TypedDict fields that form data is coerced into.

    Args:
        typed_dict: The TypedDict annotating the form data, or a specialization
            of a generic one.

    Returns:
        The ``list`` and ``bool`` fields, optional or not.
    """
    required = types.get_required_typed_dict_keys(typed_dict)
    fields = []
    for name, hint in types.get_typed_dict_field_types(typed_dict).items():
        field_type = types.value_inside_optional(hint)
        is_list = (get_origin(field_type) or field_type) is list
        if not is_list and field_type is not bool:
            continue
        fields.append(
            _CoercedFormField(
                name=name,
                names=(name, f"{name}[]") if is_list else (name,),
                is_list=is_list,
                optional=field_type is not hint,
                required=name in required,
            )
        )
    return tuple(fields)


def _form_data_as_typed_dict(form_data: FormData, typed_dict: Any) -> dict[str, Any]:
    """Build the dict for a TypedDict-annotated form data argument.

    Args:
        form_data: The submitted form data.
        typed_dict: The TypedDict annotating the argument.

    Returns:
        A dict of each field's last value, where ``list`` fields hold every
        value submitted under ``name`` or ``name[]`` and ``bool`` fields whether
        a truthy value was submitted. An unsubmitted field is left out when it
        is not required, and otherwise is None when its type allows None, else
        an empty list or False.
    """
    result = dict(form_data)
    for field in _typed_dict_form_fields(typed_dict):
        if not any(name in form_data for name in field.names):
            if not field.required:
                continue
            if field.optional:
                result[field.name] = None
                continue
        if field.is_list:
            result[field.name] = [
                value for name, value in form_data.multi_items() if name in field.names
            ]
            result.pop(field.names[1], None)
        else:
            result[field.name] = bool(form_data.get(field.name))
    return result


def _form_data_entries(value: Any) -> list | None:
    """Get a form's wrapped ``[name, value]`` entries from an event argument.

    Args:
        value: The event argument.

    Returns:
        The entries, or None when the argument is not submitted form data.
    """
    return value.get(FORM_DATA_ENTRIES_KEY) if isinstance(value, dict) else None


def transform_form_data(value: Any, hinted_args: Any) -> Any:
    """Build an event argument's form data for the argument's annotation.

    Args:
        value: The event argument, possibly a form's wrapped ``[name, value]`` entries.
        hinted_args: The type hint for the argument.

    Returns:
        For a FormData annotation, a FormData of every entry (also built from a
        plain mapping); for a TypedDict annotation of form data, its coerced
        dict; for other form data, a dict of each name's last value; otherwise
        the value unchanged.
    """
    entries = _form_data_entries(value)
    if entries is not None:
        value = FormData(entries)
    elif not isinstance(value, Mapping):
        return value
    hinted_args = types.resolve_type_alias(hinted_args)
    if types.is_union(hinted_args):
        hinted_args = types.value_inside_optional(hinted_args)
    hinted_type = get_origin(hinted_args) or hinted_args
    if isinstance(hinted_type, type) and issubclass(hinted_type, FormData):
        return value if isinstance(value, hinted_type) else hinted_type(value)
    if isinstance(value, FormData) and is_typeddict(hinted_type):
        return _form_data_as_typed_dict(value, hinted_args)
    return value if entries is None else dict(value)


def form_data_as_dict(value: Any) -> Any:
    """Convert submitted form data to a dict, whatever the annotation.

    Args:
        value: The event argument.

    Returns:
        A dict of each name's last value for submitted form data, otherwise the
        value unchanged.
    """
    entries = _form_data_entries(value)
    return value if entries is None else dict(entries)
