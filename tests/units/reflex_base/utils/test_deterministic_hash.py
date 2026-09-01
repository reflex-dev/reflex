"""Tests for the deterministic content hash."""

from __future__ import annotations

import dataclasses
import enum
from typing import Any

import pytest
from reflex_base.constants import Hooks
from reflex_base.utils import deterministic_hash as deterministic_hash_module
from reflex_base.utils.deterministic_hash import (
    _HASH_BUFFER_FLUSH_SIZE,
    _HASH_MAX_CACHE_ENTRIES,
    _HASH_MAX_CACHED_DATACLASS,
    _hash_dataclass_encodings,
    _hash_dataclass_layouts,
    _hash_encoders,
    _hash_str_encodings,
    clear_hash_caches,
    deterministic_hash,
)
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import Var
from reflex_components_core.base.bare import Bare

import reflex as rx


class _HashLevel(enum.IntEnum):
    """An IntEnum, whose ``str()`` is just its integer."""

    ONE = 1


class _HashColor(enum.Enum):
    """An enum sharing a member name with ``_HashShade``."""

    RED = "red"


class _HashShade(enum.Enum):
    """A second enum with the same member name and value."""

    RED = "red"


@dataclasses.dataclass(frozen=True)
class _ShapeAlpha:
    """One of two dataclasses with identical field names and types."""

    a: str


@dataclasses.dataclass(frozen=True)
class _ShapeBeta:
    """The other; a distinct type holding the same values."""

    a: str


@pytest.fixture
def clean_hash_caches():
    """Isolate a test from the module-level memo-naming caches.

    Tests that fill these caches would otherwise leave their probe values in
    place for the rest of the session, and tests run in random order, so a test
    that reads cache state has to start from a known one.

    Yields:
        None, with the caches empty on entry and on exit.
    """
    clear_hash_caches()
    yield
    clear_hash_caches()


def test_deterministic_hash_is_stable():
    """The same value must hash identically across calls and dict orderings."""
    value = {"b": [1, "x"], "a": {"k": None}}
    reordered = {"a": {"k": None}, "b": [1, "x"]}

    assert deterministic_hash(value) == deterministic_hash(value)
    assert deterministic_hash(value) == deterministic_hash(reordered)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        # Type tags must keep values of different types apart.
        ("1", 1),
        (1, True),
        (0, False),
        (None, "None"),
        ({"a": "b"}, [["a", "b"]]),
        # Length prefixes must keep concatenations apart.
        (["ab", "c"], ["a", "bc"]),
        ([[], []], [[[]]]),
        ({"a": "", "b": ""}, {"ab": ""}),
        # Nested containers must not flatten into their contents.
        ([1, [2]], [1, 2]),
        # str-keyed enums encode as enums, not as their string value.
        (Hooks.HookPosition.PRE_TRIGGER, Hooks.HookPosition.PRE_TRIGGER.value),
        # Same dataclass type, different field values.
        (ImportVar(tag="a"), ImportVar(tag="a", alias="a")),
        # Different dataclass types with the same field names and values.
        (_ShapeAlpha(a="x"), _ShapeBeta(a="x")),
        # An IntEnum member and the int it equals.
        (_HashLevel.ONE, 1),
        # Same member name on two enums, and a member against its own value.
        (_HashColor.RED, _HashShade.RED),
        (_HashColor.RED, _HashColor.RED.value),
    ],
)
def test_deterministic_hash_distinguishes(left: Any, right: Any):
    """Distinct values must not collide under the type-tagged encoding."""
    assert deterministic_hash(left) != deterministic_hash(right)


def test_deterministic_hash_treats_lists_and_tuples_alike():
    """Sequences share one type tag, so a list and tuple of equal items match."""
    assert deterministic_hash([1, "a"]) == deterministic_hash((1, "a"))


def test_deterministic_hash_import_var_cache_is_by_value():
    """Equal ``ImportVar`` instances hash the same; unequal ones do not.

    ``ImportVar`` encodings are cached by value, so a stale or over-eager cache
    entry would show up as two unequal imports hashing alike.
    """
    a = ImportVar(tag="useState", is_default=False, install=True)
    b = ImportVar(tag="useState", is_default=False, install=True)
    c = ImportVar(tag="useState", is_default=True, install=True)

    assert deterministic_hash(a) == deterministic_hash(b)
    assert deterministic_hash(a) != deterministic_hash(c)
    assert deterministic_hash({"react": (a, c)}) != deterministic_hash({
        "react": (c, a)
    })


def test_deterministic_hash_long_strings():
    """Strings past the encoding cache's size limit still hash correctly."""
    long_a = "a" * 10_000
    long_b = "a" * 9_999 + "b"

    assert deterministic_hash(long_a) == deterministic_hash("a" * 10_000)
    assert deterministic_hash(long_a) != deterministic_hash(long_b)


def test_deterministic_hash_beyond_string_cache_capacity(clean_hash_caches: None):
    """Strings that arrive after the encoding cache fills still hash correctly."""
    values = [f"cache_capacity_probe_{i}" for i in range(_HASH_MAX_CACHE_ENTRIES + 500)]
    digests = [deterministic_hash(value) for value in values]

    assert len(set(digests)) == len(values)
    assert [deterministic_hash(value) for value in values] == digests


def test_deterministic_hash_flushes_large_payloads():
    """A payload larger than the buffer flush size hashes deterministically."""
    payload = {f"key_{i}": "v" * 200 for i in range(2000)}

    assert deterministic_hash(payload) == deterministic_hash(dict(payload))
    mutated = {**payload, "key_0": "w" * 200}
    assert deterministic_hash(payload) != deterministic_hash(mutated)


def test_deterministic_hash_var_larger_than_the_flush_buffer():
    """A Var whose payload passes the flush size hashes correctly.

    A single leaf is appended whole, so the buffer holds it in full before the
    first flush can run -- the one value the flush size cannot bound.
    """
    size = _HASH_BUFFER_FLUSH_SIZE * 3
    big = rx.Var.create("x" * size)
    same = rx.Var.create("x" * size)
    differs_in_last_char = rx.Var.create("x" * (size - 1) + "y")

    assert len(big._js_expr) > _HASH_BUFFER_FLUSH_SIZE
    assert deterministic_hash(big) == deterministic_hash(same)
    assert deterministic_hash(big) != deterministic_hash(differs_in_last_char)
    # Nested, where the enclosing container flushes between items.
    assert deterministic_hash([big, big]) != deterministic_hash([
        big,
        differs_in_last_char,
    ])


@pytest.mark.parametrize("flush_size", [1, 64, _HASH_BUFFER_FLUSH_SIZE, 1 << 30])
def test_deterministic_hash_is_independent_of_the_flush_size(
    monkeypatch: pytest.MonkeyPatch, flush_size: int
):
    """Where the buffer is handed to the hasher must not change the digest.

    Flushing only moves bytes from the buffer into the hasher, so every flush
    size has to agree -- including one that flushes after every item and one
    that never flushes at all.
    """
    payload = {
        "var": rx.Var.create("x" * (_HASH_BUFFER_FLUSH_SIZE * 2)),
        "items": [f"item_{i}" for i in range(500)],
        "nested": {"deep": [{"k": "v" * 300} for _ in range(50)]},
    }
    expected = deterministic_hash(payload)

    monkeypatch.setattr(
        deterministic_hash_module, "_HASH_BUFFER_FLUSH_SIZE", flush_size
    )
    clear_hash_caches()
    assert deterministic_hash(payload) == expected


def test_deterministic_hash_components_and_vars():
    """Components and Vars hash by rendered content, not by identity."""
    assert deterministic_hash(Bare.create(contents="a")) == deterministic_hash(
        Bare.create(contents="a")
    )
    assert deterministic_hash(Bare.create(contents="a")) != deterministic_hash(
        Bare.create(contents="b")
    )
    assert deterministic_hash(Var("a")) == deterministic_hash(Var("a"))
    assert deterministic_hash(Var("a")) != deterministic_hash(Var("b"))
    # A Var and the bare string it renders to must not collide.
    assert deterministic_hash(Var("a")) != deterministic_hash("a")


def test_deterministic_hash_rejects_unsupported_types():
    """Values with no encoding raise rather than hashing to a shared digest."""
    with pytest.raises(TypeError):
        deterministic_hash(object())


def test_deterministic_hash_encodes_dataclass_components_as_components():
    """A component that also inherits a dataclass encodes its render."""
    assert deterministic_hash(rx.text("a")) != deterministic_hash(rx.text("b"))
    # A Var is a frozen dataclass too, and must keep encoding as a Var.
    assert deterministic_hash(Var("a")) != deterministic_hash(Var("b"))


@dataclasses.dataclass(frozen=True)
class _KeyedProbe:
    """A frozen dataclass whose declared fields are all safe to key on."""

    name: str
    flag: bool = False
    alias: str | None = None


@dataclasses.dataclass(frozen=True)
class _DefaultsProbe:
    """A frozen dataclass every field of which has a default."""

    name: str = "default"


class _PlainProbe:
    """A plain class -- no encoding, and ``_DefaultsProbe``'s metaclass."""


@dataclasses.dataclass(frozen=True)
class _NumericProbe:
    """A frozen dataclass with a field that ``==`` can conflate."""

    value: int | bool


@dataclasses.dataclass(frozen=True)
class _ContainerProbe:
    """A frozen dataclass holding something that can still change."""

    items: list[int]


@dataclasses.dataclass
class _MutableProbe:
    """An unfrozen dataclass, and so an unhashable cache key."""

    value: str


def test_deterministic_hash_caches_any_keyable_frozen_dataclass(
    clean_hash_caches: None,
):
    """Frozen dataclasses of str/bool/None fields are cached, not just imports."""
    probe = _KeyedProbe(name="probe")

    digest = deterministic_hash(probe)
    assert _hash_dataclass_encodings.get(probe) is not None
    # An equal instance reuses the entry and lands on the same digest; unequal
    # ones must not.
    assert deterministic_hash(_KeyedProbe(name="probe")) == digest
    assert deterministic_hash(_KeyedProbe(name="probe", flag=True)) != digest
    assert deterministic_hash(_KeyedProbe(name="other")) != digest


def test_deterministic_hash_does_not_cache_numeric_frozen_dataclasses(
    clean_hash_caches: None,
):
    """A field that can hold a number is not keyable by value.

    ``True == 1`` and the two hash alike, so a cache keyed on the instance would
    hand ``_NumericProbe(1)`` the encoding of ``_NumericProbe(True)``.
    """
    boolean, numeric = _NumericProbe(value=True), _NumericProbe(value=1)

    assert boolean == numeric
    assert deterministic_hash(boolean) != deterministic_hash(numeric)
    assert not _hash_dataclass_encodings


def test_deterministic_hash_dataclass_field_contradicting_its_annotation():
    """A field holding something its annotation does not admit must still hash.

    The value-keyed cache is gated on declared field types, so an instance that
    contradicts them reaches the cache lookup and is not hashable as a key.
    """
    probe = _KeyedProbe(name=["not", "a", "str"])  # pyright: ignore [reportArgumentType]

    assert deterministic_hash(probe) == deterministic_hash(
        _KeyedProbe(name=["not", "a", "str"])  # pyright: ignore [reportArgumentType]
    )
    assert deterministic_hash(probe) != deterministic_hash(
        _KeyedProbe(name=["other"])  # pyright: ignore [reportArgumentType]
    )
    # The well-typed instances alongside it still take the cached path.
    assert deterministic_hash(_KeyedProbe(name="probe")) == deterministic_hash(
        _KeyedProbe(name="probe")
    )


def test_deterministic_hash_tracks_dataclasses_that_can_still_change():
    """Dataclasses whose contents can change must be re-encoded every time."""
    mutable = _MutableProbe(value="before")
    digest = deterministic_hash(mutable)
    mutable.value = "after"
    assert deterministic_hash(mutable) != digest

    # Frozen, but a field holds a mutable container.
    container = _ContainerProbe(items=[1])
    digest = deterministic_hash(container)
    container.items.append(2)
    assert deterministic_hash(container) != digest


def test_deterministic_hash_handles_dataclasses_without_params():
    """Classes that copy ``__dataclass_fields__`` without the decorator hash.

    ``MutableProxy`` synthesizes its wrapper classes exactly this way:
    ``dataclasses.is_dataclass`` is true, but ``__dataclass_params__`` never
    comes along, so there is no ``frozen`` flag to read.
    """
    synthesized = type(
        "_SynthesizedProbe",
        (),
        {
            "__dataclass_fields__": _KeyedProbe.__dataclass_fields__,
            "name": "probe",
            "flag": False,
            "alias": None,
        },
    )

    # Hashes without reaching for the missing ``frozen`` flag, and stably.
    assert deterministic_hash(synthesized()) == deterministic_hash(synthesized())
    # A distinct class, so a distinct digest from the one it copied its fields
    # from, even holding the same values.
    assert deterministic_hash(synthesized()) != deterministic_hash(
        _KeyedProbe(name="probe")
    )


def test_deterministic_hash_skips_oversized_dataclass_encodings(
    clean_hash_caches: None,
):
    """Outsized encodings are not retained, keeping the cache's memory bounded."""
    oversized = _KeyedProbe(name="x" * _HASH_MAX_CACHED_DATACLASS)

    digest = deterministic_hash(oversized)
    assert not _hash_dataclass_encodings
    assert deterministic_hash(_KeyedProbe(name="x" * _HASH_MAX_CACHED_DATACLASS)) == (
        digest
    )


def test_deterministic_hash_beyond_dataclass_cache_capacity(clean_hash_caches: None):
    """Frozen dataclasses arriving after the cache fills still hash correctly."""
    values = [
        _KeyedProbe(name=f"capacity_probe_{i}")
        for i in range(_HASH_MAX_CACHE_ENTRIES + 100)
    ]
    digests = [deterministic_hash(value) for value in values]

    assert len(set(digests)) == len(values)
    assert [deterministic_hash(value) for value in values] == digests


def test_deterministic_hash_encoder_table_keeps_types_apart(clean_hash_caches: None):
    """Memoizing an encoder per type must not route other types through it."""
    # A str-keyed enum resolves to the enum encoder; plain strings must keep
    # their own fast path, and the two must not collide.
    position = Hooks.HookPosition.PRE_TRIGGER
    assert deterministic_hash(position) != deterministic_hash(position.value)
    assert deterministic_hash(position.value) == deterministic_hash(str(position.value))
    # Dataclass types are encoded from their defaults. A class's own type is
    # its metaclass, which it shares with unrelated classes, so caching an
    # encoder under it would send those down the dataclass path too.
    assert type(_DefaultsProbe) is type(_PlainProbe)
    assert deterministic_hash(_DefaultsProbe) == deterministic_hash(
        _DefaultsProbe(name="default")
    )
    with pytest.raises(TypeError, match="Cannot hash value"):
        deterministic_hash(_PlainProbe)


def test_deterministic_hash_unsupported_type_is_not_memoized(clean_hash_caches: None):
    """A type with no encoder must raise every time, not just the first."""
    with pytest.raises(TypeError, match="Cannot hash value"):
        deterministic_hash(object())
    with pytest.raises(TypeError, match="Cannot hash value"):
        deterministic_hash(object())
    assert not _hash_encoders


def test_clear_hash_caches_drops_every_cache(clean_hash_caches: None):
    """The compile-scoped encoding caches must all be released together.

    Nothing asks for these values after a compile, and a dataclass type defined
    inside a function body is a fresh class object each time -- so a cache left
    behind would pin one per compile for the life of the process.
    """
    ephemeral = dataclasses.make_dataclass("Ephemeral", [("v", str)])
    before = deterministic_hash({
        "prop": ephemeral(v="x"),
        "imports": (ImportVar(tag="useCacheProbe"),),
    })

    assert _hash_dataclass_layouts
    assert _hash_str_encodings
    assert _hash_dataclass_encodings
    assert _hash_encoders

    clear_hash_caches()

    assert not _hash_dataclass_layouts
    assert not _hash_str_encodings
    assert not _hash_dataclass_encodings
    assert not _hash_encoders
    # Hashing rebuilds them from scratch and must land on the same digest.
    assert (
        deterministic_hash({
            "prop": ephemeral(v="x"),
            "imports": (ImportVar(tag="useCacheProbe"),),
        })
        == before
    )
