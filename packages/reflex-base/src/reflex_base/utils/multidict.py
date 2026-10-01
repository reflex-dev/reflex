"""An immutable mapping that keeps every value of a repeated key."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any, TypeVar

__all__ = ["MultiDict"]

_K = TypeVar("_K")
_V_co = TypeVar("_V_co", covariant=True)


class MultiDict(Mapping[_K, _V_co]):
    """An immutable mapping that keeps every value of a repeated key, in order.

    Indexing, iteration and ``len`` see each key once with its last value, so a
    MultiDict reads like the dict built from the same items. ``getlist`` and
    ``multi_items`` expose every value, such as the fields of a submitted form
    that share a name.
    """

    __slots__ = ("_dict", "_items")

    _dict: dict[_K, _V_co]
    _items: tuple[tuple[_K, _V_co], ...]

    def __init__(
        self,
        items: Mapping[_K, _V_co] | Iterable[tuple[_K, _V_co]] = (),
    ) -> None:
        """Build a MultiDict.

        Args:
            items: ``(key, value)`` pairs, or a mapping; a MultiDict keeps every
                item.
        """
        if isinstance(items, MultiDict):
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
            AttributeError: Always, since a MultiDict is immutable.
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
            For a MultiDict, whether both hold the same items in the same order;
            for another mapping, whether it equals this one's last values.
        """
        if isinstance(other, MultiDict):
            return self._items == other._items
        return super().__eq__(other)

    __hash__ = None  # pyright: ignore[reportAssignmentType]

    def __repr__(self) -> str:
        """Represent the MultiDict by its items.

        Returns:
            The representation.
        """
        return f"{type(self).__name__}({list(self._items)!r})"

    def __reduce__(self) -> tuple[type[MultiDict[_K, _V_co]], tuple[list]]:
        """Pickle the MultiDict by its items.

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

    def multi_items(self) -> list[tuple[_K, _V_co]]:
        """Get every ``(key, value)`` item, repeated keys included.

        Returns:
            The items in order.
        """
        return list(self._items)
