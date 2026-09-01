"""A stable content hash over components, vars and the data they render to.

:func:`deterministic_hash` digests values under a self-delimiting, type-tagged
encoding: every type writes a distinct tag and a length-prefixed payload, so
the encoding is injective. Unlike :func:`hash` it is stable across processes,
which is what lets a digest name a generated file.

Encoders are resolved once per type, and the encodings of recurring values are
cached until :func:`clear_hash_caches` drops them.
"""

from __future__ import annotations

import dataclasses
import enum
import operator
from collections.abc import Callable, Mapping, Sequence
from hashlib import md5
from types import UnionType
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin, get_type_hints
from weakref import WeakKeyDictionary

if TYPE_CHECKING:
    from reflex_base.components.component import BaseComponent
    from reflex_base.vars.base import Var

_HASH_BUFFER_FLUSH_SIZE = 1 << 16
_HASH_MAX_CACHED_STR = 128
_HASH_MAX_CACHED_DATACLASS = 512
_HASH_MAX_CACHE_ENTRIES = 4096

# Field types for which ``==`` implies an identical encoding, so a frozen
# dataclass of them can key an encoding cache by value. Numbers are excluded:
# ``True == 1 == 1.0`` compare equal and hash alike but encode differently.
_HASH_VALUE_KEYED_FIELD_TYPES = frozenset({str, bool, type(None)})

# Appends one value's encoding to a buffer, taking the hasher that buffer is
# flushed into so it can pass it down to nested encodings.
_HashEncoder = Callable[[Any, bytearray, Any], None]

# Dropped together by :func:`clear_hash_caches`. The two value caches stop
# admitting entries at ``_HASH_MAX_CACHE_ENTRIES``, so recurring values get in
# first and a run of one-off values cannot grow them without bound.
_hash_str_encodings: dict[str, bytes] = {}
_hash_dataclass_encodings: dict[Any, bytes] = {}
_hash_dataclass_layouts: dict[type, tuple[bytes, tuple[tuple[bytes, str], ...]]] = {}
_hash_encoders: dict[type, _HashEncoder] = {}

# Whether a frozen dataclass type is safe to key by value. Resolving a class's
# annotations is expensive enough that this outlives a single run, and weak keys
# keep a dataclass defined in a function body collectable.
_hash_value_keyed_types: WeakKeyDictionary[type, bool] = WeakKeyDictionary()


def _hash_dataclass_layout(cls: type) -> tuple[bytes, tuple[tuple[bytes, str], ...]]:
    """Get the cached type tag and pre-encoded field names for a dataclass.

    Args:
        cls: The dataclass type to describe.

    Returns:
        The type tag, field count and defining class, and each field's encoded
        and plain name.
    """
    layout = _hash_dataclass_layouts.get(cls)
    if layout is None:
        fields = dataclasses.fields(cls)  # pyright: ignore [reportArgumentType]
        # The defining class is part of the header: two dataclasses with the
        # same field names and values are different values.
        layout = (
            b"D"
            + len(fields).to_bytes(8, "little")
            + _encode_str_for_hash(f"{cls.__module__}.{cls.__qualname__}"),
            tuple((field.name.encode(), field.name) for field in fields),
        )
        _hash_dataclass_layouts[cls] = layout
    return layout


def _hash_dataclass_is_value_keyed(cls: type) -> bool:
    """Check whether instances of ``cls`` can key an encoding cache by value.

    True when every declared field type is in
    ``_HASH_VALUE_KEYED_FIELD_TYPES``, which is what makes ``==`` imply an
    identical encoding. A field typed ``int | bool`` fails: ``1`` and ``True``
    compare equal and hash alike but encode differently.

    Args:
        cls: The frozen dataclass type to check.

    Returns:
        Whether every declared field type is safe to key on.
    """
    keyed = _hash_value_keyed_types.get(cls)
    if keyed is None:
        keyed = _hash_value_keyed_types[cls] = _hash_dataclass_declares_keyed_fields(
            cls
        )
    return keyed


def _hash_dataclass_declares_keyed_fields(cls: type) -> bool:
    """Resolve whether every field ``cls`` declares is safe to key a cache on.

    Args:
        cls: The frozen dataclass type to check.

    Returns:
        Whether every declared field type is drawn from
        ``_HASH_VALUE_KEYED_FIELD_TYPES``.
    """
    # Not the cached wrapper in ``reflex_base.utils.types``: its ``lru_cache``
    # stores results but not exceptions, and holds its keys strongly.
    try:
        hints = get_type_hints(cls)
    except (NameError, TypeError):
        # Annotations that don't resolve at runtime state no contract to read.
        return False
    for _, name in _hash_dataclass_layout(cls)[1]:
        hint = hints.get(name)
        members = get_args(hint) if get_origin(hint) in (Union, UnionType) else (hint,)
        if not all(member in _HASH_VALUE_KEYED_FIELD_TYPES for member in members):
            return False
    return True


def _encode_str_for_hash(value: str) -> bytes:
    """Encode a string as a type-tagged, length-prefixed payload.

    Args:
        value: The string to encode.

    Returns:
        The encoded string.
    """
    encoded = value.encode()
    return b"s" + len(encoded).to_bytes(8, "little") + encoded


def _encode_hash_number(value: float, out: bytearray, hasher: Any) -> None:
    """Append a number's encoding to ``out``.

    Args:
        value: The value to encode.
        out: The buffer to append the encoding to.
        hasher: Unused; kept for the shared encoder signature.
    """
    out += b"n"
    out += str(value).encode()


def _encode_hash_enum(value: enum.Enum, out: bytearray, hasher: Any) -> None:
    """Append an enum member's encoding to ``out``.

    Encodes the member's identity rather than ``str(value)``, which for an
    ``IntEnum`` is just its integer.

    Args:
        value: The enum member to encode.
        out: The buffer to append the encoding to.
        hasher: Unused; kept for the shared encoder signature.
    """
    cls = type(value)
    out += b"e"
    out += _encode_str_for_hash(f"{cls.__module__}.{cls.__qualname__}.{value.name}")


def _encode_hash_str(value: str, out: bytearray, hasher: Any) -> None:
    """Append a ``str`` subclass instance's encoding to ``out``.

    Args:
        value: The value to encode.
        out: The buffer to append the encoding to.
        hasher: Unused; kept for the shared encoder signature.
    """
    out += _encode_str_for_hash(value)


def _encode_hash_dict(value: Mapping[Any, Any], out: bytearray, hasher: Any) -> None:
    """Append a mapping's encoding to ``out``.

    Args:
        value: The mapping to encode.
        out: The buffer to append the encoding to.
        hasher: The hasher ``out`` is flushed into once it grows too large.
    """
    out += b"d"
    out += len(value).to_bytes(8, "little")
    for k, v in sorted(value.items(), key=operator.itemgetter(0)):
        _encode_deterministic(k, out, hasher)
        _encode_deterministic(v, out, hasher)
        if len(out) > _HASH_BUFFER_FLUSH_SIZE and hasher is not None:
            hasher.update(out)
            del out[:]


def _encode_hash_sequence(value: Sequence[Any], out: bytearray, hasher: Any) -> None:
    """Append a sequence's encoding to ``out``.

    Args:
        value: The sequence to encode.
        out: The buffer to append the encoding to.
        hasher: The hasher ``out`` is flushed into once it grows too large.
    """
    out += b"l"
    out += len(value).to_bytes(8, "little")
    for item in value:
        _encode_deterministic(item, out, hasher)
        if len(out) > _HASH_BUFFER_FLUSH_SIZE and hasher is not None:
            hasher.update(out)
            del out[:]


def _encode_hash_var(value: Var, out: bytearray, hasher: Any) -> None:
    """Append a ``Var``'s encoding to ``out``.

    Args:
        value: The var to encode.
        out: The buffer to append the encoding to.
        hasher: The hasher ``out`` is flushed into once it grows too large.
    """
    out += b"v"
    _encode_deterministic(value._js_expr, out, hasher)
    _encode_deterministic(value._get_all_var_data(), out, hasher)


def _encode_hash_component(value: BaseComponent, out: bytearray, hasher: Any) -> None:
    """Append a component's encoding to ``out``.

    Args:
        value: The component to encode.
        out: The buffer to append the encoding to.
        hasher: The hasher ``out`` is flushed into once it grows too large.
    """
    out += b"C"
    _encode_deterministic(value.render(), out, hasher)


def _encode_hash_dataclass_fields(
    cls: type, value: Any, out: bytearray, hasher: Any
) -> None:
    """Append the encoding of ``value``'s dataclass fields to ``out``.

    Args:
        cls: The dataclass type supplying the field layout.
        value: The instance -- or the class itself, for its defaults -- to read
            the field values off.
        out: The buffer to append the encoding to.
        hasher: The hasher ``out`` is flushed into once it grows too large.
    """
    header, fields = _hash_dataclass_layout(cls)
    out += header
    for encoded_name, name in fields:
        out += encoded_name
        _encode_deterministic(getattr(value, name), out, hasher)


def _encode_hash_dataclass(value: Any, out: bytearray, hasher: Any) -> None:
    """Append a dataclass instance's encoding to ``out``.

    Args:
        value: The dataclass instance to encode.
        out: The buffer to append the encoding to.
        hasher: The hasher ``out`` is flushed into once it grows too large.
    """
    _encode_hash_dataclass_fields(type(value), value, out, hasher)


def _encode_hash_dataclass_type(value: type, out: bytearray, hasher: Any) -> None:
    """Append a dataclass type's encoding -- its field defaults -- to ``out``.

    Args:
        value: The dataclass type to encode.
        out: The buffer to append the encoding to.
        hasher: The hasher ``out`` is flushed into once it grows too large.
    """
    _encode_hash_dataclass_fields(value, value, out, hasher)


def _encode_hash_cached_dataclass(value: Any, out: bytearray, hasher: Any) -> None:
    """Append a frozen dataclass instance's encoding to ``out``, caching it.

    Args:
        value: The frozen dataclass instance to encode.
        out: The buffer to append the encoding to.
        hasher: Unused; the fields are encoded into a private buffer that must
            not be drained, since the caller needs its full contents.
    """
    encoded = _hash_dataclass_encodings.get(value)
    if encoded is None:
        buffer = bytearray()
        _encode_hash_dataclass_fields(type(value), value, buffer, None)
        encoded = bytes(buffer)
        if (
            len(encoded) <= _HASH_MAX_CACHED_DATACLASS
            and len(_hash_dataclass_encodings) < _HASH_MAX_CACHE_ENTRIES
        ):
            _hash_dataclass_encodings[value] = encoded
    out += encoded


def _resolve_hash_encoder(value: Any) -> _HashEncoder:
    """Pick the encoder for a value whose exact type has no fast path.

    Called once per type: :func:`_encode_deterministic` memoizes the result.
    Branch order matters where a value matches several -- a ``str``-based enum
    must encode as an enum, not as a string.

    Args:
        value: A value of the type to resolve an encoder for.

    Returns:
        The encoder for the value's type.

    Raises:
        TypeError: If the value is not hashable.
    """
    # Imported here rather than at module scope: nothing else under ``utils``
    # depends on ``components`` at runtime, and resolving an encoder happens
    # once per type, so the lookup never shows up in a profile.
    from reflex_base.components.component import BaseComponent
    from reflex_base.vars.base import Var

    # ``bool`` cannot be subclassed, so every bool is caught by the exact-type
    # fast path and none arrives here to be mistaken for a number.
    if isinstance(value, enum.Enum):
        return _encode_hash_enum
    if isinstance(value, (int, float)):
        return _encode_hash_number
    if isinstance(value, str):
        return _encode_hash_str
    if isinstance(value, dict):
        return _encode_hash_dict
    if isinstance(value, (tuple, list)):
        return _encode_hash_sequence
    if isinstance(value, Var):
        return _encode_hash_var
    # Ahead of the dataclass branch: a component that also inherits a dataclass
    # (anything built on ``MarkdownComponentMap``) must encode as a component,
    # not as that mixin's field list.
    if isinstance(value, BaseComponent):
        return _encode_hash_component
    if dataclasses.is_dataclass(value):
        if isinstance(value, type):
            return _encode_hash_dataclass_type
        # Classes synthesized at runtime (``MutableProxy``) copy
        # ``__dataclass_fields__`` without the decorator's params.
        params = getattr(type(value), "__dataclass_params__", None)
        if (
            params is not None
            and params.frozen
            and _hash_dataclass_is_value_keyed(type(value))
        ):
            return _encode_hash_cached_dataclass
        return _encode_hash_dataclass
    msg = (
        f"Cannot hash value `{value}` of type `{type(value).__name__}`. "
        "Only BaseComponent, Var, VarData, dict, str, tuple, and enum.Enum are supported."
    )
    raise TypeError(msg)


def _encode_deterministic(value: Any, out: bytearray, hasher: Any | None) -> None:
    """Append ``value``'s self-delimiting encoding to ``out``.

    Dispatch is on the exact type, so the common leaves skip the ``isinstance``
    ladder in :func:`_resolve_hash_encoder`; every other type walks it once and
    is then memoized in ``_hash_encoders``. ``out`` is flushed into ``hasher``
    at container boundaries once it passes ``_HASH_BUFFER_FLUSH_SIZE``, so a
    large subtree is never buffered whole.

    Args:
        value: The value to encode.
        out: The buffer to append the encoding to.
        hasher: The hasher ``out`` is flushed into when it grows too large, or
            ``None`` when ``out`` is a sub-buffer whose full contents the caller
            needs and so must not be drained mid-encoding.
    """
    value_type = type(value)
    if value_type is str:
        encoded = _hash_str_encodings.get(value)
        if encoded is None:
            encoded = _encode_str_for_hash(value)
            if (
                len(value) <= _HASH_MAX_CACHED_STR
                and len(_hash_str_encodings) < _HASH_MAX_CACHE_ENTRIES
            ):
                _hash_str_encodings[value] = encoded
        out += encoded
    elif value_type is bool:
        out += b"T" if value else b"F"
    elif value_type is dict:
        _encode_hash_dict(value, out, hasher)
    elif value_type is list or value_type is tuple:
        _encode_hash_sequence(value, out, hasher)
    elif value is None:
        out += b"N"
    elif value_type is int or value_type is float:
        out += b"n"
        out += str(value).encode()
    else:
        encoder = _hash_encoders.get(value_type)
        if encoder is None:
            encoder = _resolve_hash_encoder(value)
            if not isinstance(value, type):
                # ``value_type`` is the metaclass when the value is itself a
                # class, so memoizing would route every other class through the
                # encoder resolved for this one.
                _hash_encoders[value_type] = encoder
        encoder(value, out, hasher)
        if len(out) > _HASH_BUFFER_FLUSH_SIZE and hasher is not None:
            hasher.update(out)
            del out[:]


def deterministic_hash(*values: object) -> str:
    """Fold values into a single digest, in the order given.

    All values share one buffer, so a digest over many values costs a handful
    of hasher updates rather than one per value.

    Args:
        *values: The values to hash.

    Returns:
        The hex digest over all values.

    Raises:
        TypeError: If a value has no encoding.
    """
    hasher = md5(usedforsecurity=False)
    buffer = bytearray()
    for value in values:
        _encode_deterministic(value, buffer, hasher)
    hasher.update(buffer)
    return hasher.hexdigest()


def clear_hash_caches() -> None:
    """Drop the encoding caches.

    Both the layout cache and the encoder table key on types, so leaving them
    populated pins every dataclass type they have seen.
    """
    _hash_str_encodings.clear()
    _hash_dataclass_encodings.clear()
    _hash_dataclass_layouts.clear()
    _hash_encoders.clear()
