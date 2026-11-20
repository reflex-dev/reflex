"""Tests for orjson-based serializers in reflex_base.utils.format.

Covers ``orjson_dumps``, ``orjson_loads`` and ``orjson_dumps_socket``.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import math
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from reflex_base.style import Style
from reflex_base.utils.format import (
    json_dumps,
    orjson_dumps,
    orjson_dumps_socket,
    orjson_loads,
)
from reflex_base.utils.serializers import (
    get_serializer,
    serialize_enum,
    serialize_uuid,
    serializer,
)


@pytest.fixture(autouse=True)
def _orjson_enabled(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Run every test here with the orjson paths enabled.

    An Enum/UUID serializer registered at import time by any other test module
    would otherwise disable them process-wide. Tests requesting ``no_orjson``
    drive the stdlib fallback and run whether or not the extra is installed --
    that is the configuration the fallback exists for.

    Args:
        request: The pytest request fixture, for the test's fixture names.
        monkeypatch: The pytest monkeypatch fixture.
    """
    from reflex_base.utils import format as format_module

    if "no_orjson" not in request.fixturenames:
        pytest.importorskip("orjson")

    monkeypatch.setattr(format_module, "_orjson_registry_shadowed", False)


# orjson_dumps + orjson_loads round-trip


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        0,
        -1,
        1.5,
        "hello",
        "",
        [],
        {},
        [1, 2, 3],
        {"a": 1, "b": [2, 3]},
        {"nested": {"deep": {"value": [1, 2, 3]}}},
    ],
)
def test_orjson_round_trip(value):
    """``orjson_loads`` reads back what ``orjson_dumps`` wrote.

    Args:
        value: A JSON-native value.
    """
    assert orjson_loads(orjson_dumps(value)) == value


# socket.io kwarg compat (regression test for the bug that broke
# integration tests: socket.io calls dumps(data, separators=(',',':')))


def test_orjson_dumps_socket_accepts_separators_kwarg():
    """socket.io's ``separators`` argument is accepted and output stays compact."""
    out = orjson_dumps_socket({"a": 1}, separators=(",", ":"))
    assert out == '{"a":1}'


def test_orjson_dumps_socket_ignores_arbitrary_kwargs():
    """Encoder kwargs must not reach the backend: output stays compact and
    keeps insertion order whatever separators/sort_keys are passed.
    """
    payload = {"b": 1, "a": [2, 3]}
    out = orjson_dumps_socket(payload, separators=(" | ", " = "), sort_keys=True)
    assert out == orjson_dumps_socket(payload) == '{"b":1,"a":[2,3]}'


# non-finite floats survive the wire in both backends


def _wire(out: str) -> Any:
    """Decode a socket payload the way the frontend does.

    Non-finite floats come back as ``'nan'``/``'inf'``/``'-inf'`` so they
    compare by value.

    Args:
        out: The serialized socket payload.

    Returns:
        The decoded payload with non-finite floats named.
    """

    def named(value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            return repr(value)
        if isinstance(value, dict):
            return {k: named(v) for k, v in value.items()}
        if isinstance(value, list):
            return [named(v) for v in value]
        return value

    # stdlib json accepts the bare NaN/Infinity tokens the frontend rewrites.
    return named(json.loads(out))


def test_nan_top_level():
    """A bare NaN survives the socket round trip."""
    assert _wire(orjson_dumps_socket(float("nan"))) == "nan"


def test_inf_top_level():
    """A bare Infinity survives the socket round trip."""
    assert _wire(orjson_dumps_socket(float("inf"))) == "inf"


def test_neg_inf_top_level():
    """A bare -Infinity survives the socket round trip."""
    assert _wire(orjson_dumps_socket(float("-inf"))) == "-inf"


def test_nan_in_list():
    """NaN survives inside a list."""
    assert _wire(orjson_dumps_socket([1.0, float("nan"), 2.0])) == [1.0, "nan", 2.0]


def test_nan_in_dict():
    """NaN survives inside a dict."""
    out = orjson_dumps_socket({"x": float("nan"), "y": 1.0})
    assert _wire(out) == {"x": "nan", "y": 1.0}


def test_non_finite_floats_deeply_nested():
    """Non-finite floats survive at any nesting depth."""
    out = orjson_dumps_socket({"a": {"b": [{"c": float("nan")}, float("inf")]}})
    assert _wire(out) == {"a": {"b": [{"c": "nan"}, "inf"]}}


def test_all_three_non_finite_floats():
    """NaN, Infinity and -Infinity survive side by side."""
    out = orjson_dumps_socket([float("nan"), float("inf"), float("-inf")])
    assert _wire(out) == ["nan", "inf", "-inf"]


def test_nan_inside_dataclass_field():
    """Dataclass fields with NaN must survive too."""

    @dataclasses.dataclass
    class Point:
        x: float
        y: float

    out = orjson_dumps_socket({"p": Point(float("nan"), 1.0)})
    assert _wire(out) == {"p": {"x": "nan", "y": 1.0}}


# format compatibility with the existing json_dumps


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        0,
        1,
        1.5,
        "hello",
        [1, 2, 3],
        {"a": 1, "b": "two"},
        {"nested": {"deep": [1, "two", None]}},
        datetime.datetime(2026, 4, 25, 10, 30, 45),
        datetime.datetime(2026, 4, 25, 10, 30, 45, 123456),
        datetime.datetime(2026, 4, 25, 10, 30, 45, tzinfo=datetime.UTC),
        datetime.date(2026, 4, 25),
        datetime.time(10, 30, 45),
        datetime.timedelta(days=1, seconds=1, microseconds=1),
        Decimal("3.14"),
        UUID("12345678-1234-5678-1234-567812345678"),
        Path("/tmp/foo"),
    ],
)
def test_socket_output_matches_json_dumps_for_finite_inputs(value):
    """For inputs without NaN/Inf, ``orjson_dumps_socket`` must produce
    a payload that decodes to the same Python object as ``json_dumps``.
    """
    socket_out = orjson_dumps_socket(value)
    json_out = json_dumps(value)
    assert json.loads(socket_out) == json.loads(json_out)


def test_enum_value_serialized_consistently():
    """An Enum serializes the same through both backends."""

    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    assert json.loads(orjson_dumps_socket({"c": Color.RED})) == json.loads(
        json_dumps({"c": Color.RED})
    )


def test_dict_subclass_style_serializes_equivalently():
    """``Style`` is a dict subclass; both paths must agree on the output."""
    style = Style({"color": "red", "size": 12})
    assert json.loads(orjson_dumps_socket(style)) == json.loads(json_dumps(style))


# native scalar subclasses serialize as their base value


class _IntSubclass(int):
    pass


class _StrSubclass(str):
    pass


class _FloatSubclass(float):
    pass


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (_IntSubclass(25), 25),
        (_IntSubclass(0), 0),
        (_StrSubclass("hello"), "hello"),
        (_StrSubclass(""), ""),
        (_FloatSubclass(1.5), 1.5),
    ],
)
def test_native_subclass_serializes_to_base_value(value, expected):
    """A str/int/float subclass serializes as its base value.

    Args:
        value: The subclass instance.
        expected: Its base value.
    """
    assert orjson_loads(orjson_dumps_socket({"v": value})) == {"v": expected}


@pytest.mark.parametrize(
    "value",
    [_IntSubclass(25), _StrSubclass("hello"), _FloatSubclass(1.5)],
)
def test_native_subclass_matches_json_dumps(value):
    """A str/int/float subclass serializes as the stdlib does.

    Args:
        value: The subclass instance.
    """
    assert json.loads(orjson_dumps_socket({"v": value})) == json.loads(
        json_dumps({"v": value})
    )


# user-registered serializers must win over orjson's native handling.
# These live at module scope because ``get_type_hints`` resolves the
# serializer annotations against module globals.


class _EnumForSerializer(Enum):
    ACTIVE = "raw"


class _FloatForSerializer(float):
    pass


class _DictForSerializer(dict):
    pass


class _MixinForLaterEnum:
    pass


class _MixinForEarlierEnum:
    pass


@pytest.fixture
def isolated_serializer_registry(monkeypatch: pytest.MonkeyPatch):
    """Undo serializer registrations made by the test.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Yields:
        The ``format`` module, for asserting on the shadow flag.
    """
    from reflex_base.utils import format as format_module
    from reflex_base.utils import serializers

    monkeypatch.setattr(serializers, "SERIALIZERS", dict(serializers.SERIALIZERS))
    monkeypatch.setattr(
        serializers, "SERIALIZER_TYPES", dict(serializers.SERIALIZER_TYPES)
    )
    serializers.get_serializer.cache_clear()
    serializers.get_serializer_type.cache_clear()
    yield format_module
    serializers.get_serializer.cache_clear()
    serializers.get_serializer_type.cache_clear()


@pytest.mark.parametrize("value", [_EnumForSerializer.ACTIVE, UUID(int=1)])
def test_stock_enum_and_uuid_serializers_agree_with_orjson(value):
    """Check the premise behind the bundled Enum/UUID serializers opting out.

    Args:
        value: A value covered by a bundled, opted-out serializer.
    """
    payload = {"v": value}
    assert orjson_dumps(payload) == json_dumps(payload, separators=(",", ":"))
    assert orjson_dumps_socket(payload) == json_dumps(payload, separators=(",", ":"))


@pytest.mark.parametrize(
    ("type_", "stock"), [(_EnumForSerializer, serialize_enum), (UUID, serialize_uuid)]
)
def test_resolving_stock_enum_and_uuid_serializers_keeps_orjson(
    isolated_serializer_registry, type_: type, stock
):
    """Resolving a bundled, opted-out serializer leaves the orjson paths on.

    Args:
        isolated_serializer_registry: Fixture restoring the global registry.
        type_: A type orjson emits natively.
        stock: The bundled serializer for it.
    """
    assert get_serializer(type_) is stock
    assert isolated_serializer_registry._orjson_registry_shadowed is False


def test_mixin_serializer_inherited_by_later_enum_wins_over_orjson(
    isolated_serializer_registry,
):
    """An Enum defined after a serializer for its mixin still bypasses orjson.

    Args:
        isolated_serializer_registry: Fixture restoring the global registry.
    """

    @serializer
    def serialize_mixin(value: _MixinForLaterEnum) -> str:
        return "CUSTOM"

    class Status(_MixinForLaterEnum, Enum):
        ACTIVE = "raw"

    # State var validation resolves the serializer of each field's type.
    assert get_serializer(Status) is serialize_mixin
    value = {"v": Status.ACTIVE}
    assert isolated_serializer_registry._orjson_registry_shadowed is True
    assert orjson_dumps(value) == '{"v":"CUSTOM"}'
    assert orjson_dumps_socket(value) == '{"v":"CUSTOM"}'


def test_mixin_serializer_inherited_by_earlier_enum_wins_over_orjson(
    isolated_serializer_registry,
):
    """A serializer for the mixin of an existing Enum bypasses orjson at once.

    Args:
        isolated_serializer_registry: Fixture restoring the global registry.
    """

    class Status(_MixinForEarlierEnum, Enum):
        ACTIVE = "raw"

    @serializer
    def serialize_mixin(value: _MixinForEarlierEnum) -> str:
        return "CUSTOM"

    value = {"v": Status.ACTIVE}
    assert isolated_serializer_registry._orjson_registry_shadowed is True
    assert orjson_dumps(value) == '{"v":"CUSTOM"}'
    assert orjson_dumps_socket(value) == '{"v":"CUSTOM"}'


def test_custom_enum_serializer_wins_over_orjson(isolated_serializer_registry):
    """An Enum is emitted natively by orjson, which would bypass the registry.

    Args:
        isolated_serializer_registry: Fixture restoring the global registry.
    """

    @serializer
    def serialize_status(status: _EnumForSerializer) -> str:
        return "CUSTOM"

    value = {"v": _EnumForSerializer.ACTIVE}
    assert isolated_serializer_registry._orjson_registry_shadowed is True
    assert orjson_dumps(value) == json_dumps(value, separators=(",", ":"))
    assert orjson_dumps_socket(value) == '{"v":"CUSTOM"}'


def test_union_annotated_enum_serializer_wins_over_orjson(
    isolated_serializer_registry,
):
    """A serializer annotated with a union still shadows orjson's native output.

    ``get_serializer`` resolves the union's Enum member, so the stdlib path uses
    the custom serializer; the orjson path must not disagree.

    Args:
        isolated_serializer_registry: Fixture restoring the global registry.
    """

    @serializer
    def serialize_status(status: _EnumForSerializer | None) -> str:
        return "CUSTOM"

    value = {"v": _EnumForSerializer.ACTIVE}
    assert isolated_serializer_registry._orjson_registry_shadowed is True
    assert orjson_dumps(value) == json_dumps(value, separators=(",", ":"))
    assert orjson_dumps_socket(value) == '{"v":"CUSTOM"}'


def test_uuid_serializer_override_wins_over_orjson(isolated_serializer_registry):
    """A UUID is emitted natively by orjson, which would bypass an override.

    Args:
        isolated_serializer_registry: Fixture restoring the global registry.
    """

    @serializer(overwrite=True)
    def serialize_uuid_override(value: UUID) -> str:
        return "CUSTOM"

    assert isolated_serializer_registry._orjson_registry_shadowed is True
    assert orjson_dumps_socket({"v": UUID(int=1)}) == '{"v":"CUSTOM"}'


def test_float_subclass_serializer_does_not_shadow_orjson(
    isolated_serializer_registry,
):
    """The stdlib serializes float subclasses natively, so orjson must too.

    Args:
        isolated_serializer_registry: Fixture restoring the global registry.
    """

    @serializer
    def serialize_money(value: _FloatForSerializer) -> str:
        return "CUSTOM"

    payload = {"v": _FloatForSerializer(1.5)}
    assert isolated_serializer_registry._orjson_registry_shadowed is False
    assert orjson_dumps(payload) == json_dumps(payload, separators=(",", ":"))
    assert orjson_dumps_socket(payload) == '{"v":1.5}'


def test_builtin_subclass_serializer_bypassed_by_both_backends(
    isolated_serializer_registry,
):
    """Neither backend consults the registry for str/dict subclasses.

    Args:
        isolated_serializer_registry: Fixture restoring the global registry.
    """

    @serializer
    def serialize_str_subclass(value: _StrSubclass) -> str:
        return "CUSTOM"

    @serializer
    def serialize_dict_subclass(value: _DictForSerializer) -> str:
        return "CUSTOM"

    assert isolated_serializer_registry._orjson_registry_shadowed is False
    for payload in ({"v": _StrSubclass("x")}, {"v": _DictForSerializer(a=1)}):
        assert orjson_dumps_socket(payload) == json_dumps(
            payload, separators=(",", ":")
        )


def test_int_subclass_inside_dataclass_field():
    """An int subclass in a dataclass field serializes as its base value."""

    @dataclasses.dataclass
    class Pagination:
        page: int
        size: int

    out = orjson_dumps_socket({"p": Pagination(_IntSubclass(3), _IntSubclass(25))})
    assert orjson_loads(out) == {"p": {"page": 3, "size": 25}}


def test_datetime_uses_space_separator_not_iso_t():
    """Regression: orjson natively emits 'T'-separated datetimes; we route
    them through ``serializers.serialize_datetime`` to keep the existing
    space-separated format consumed by the JS side.
    """
    dt = datetime.datetime(2026, 4, 25, 10, 30, 45)
    out = orjson_dumps_socket({"dt": dt})
    assert orjson_loads(out) == {"dt": "2026-04-25 10:30:45"}


# non-string dict keys


def test_non_str_dict_keys_coerced_to_strings():
    """Non-string dict keys become strings, as with the stdlib."""
    out = orjson_dumps_socket({1: "a", 2.5: "b", False: "c", None: "d"})
    assert out == '{"1":"a","2.5":"b","false":"c","null":"d"}'


@pytest.mark.parametrize(
    ("key", "type_name"),
    [
        (_EnumForSerializer.ACTIVE, "_EnumForSerializer"),
        (datetime.date(2026, 4, 25), "datetime.date"),
        (UUID(int=1), "UUID"),
    ],
)
def test_dict_keys_the_stdlib_rejects_are_rejected(key: Any, type_name: str):
    """A key type the stdlib refuses is refused whatever the backend.

    Args:
        key: A dict key that is neither str, int, float, bool nor None.
        type_name: The key's type as the stdlib names it.
    """
    with pytest.raises(TypeError) as exc_info:
        orjson_dumps_socket({key: 1})
    assert str(exc_info.value) == (
        f"keys must be str, int, float, bool or None, not {type_name}"
    )


# unknown-type fallback


def test_unknown_type_serializes_to_null():
    """Types without a registered serializer return None from
    ``serializers.serialize`` and end up as JSON null -- matches stdlib
    ``json.dumps(default=serialize)`` behavior.
    """

    class Unknown:
        pass

    out = orjson_dumps_socket({"x": Unknown()})
    assert orjson_loads(out) == {"x": None}


@pytest.fixture
def no_orjson(monkeypatch: pytest.MonkeyPatch):
    """Simulate orjson not being installed.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    from reflex_base.utils import format as format_module

    monkeypatch.setattr(format_module, "orjson", None)


def test_fallback_emits_bare_non_finite_tokens(no_orjson):
    """Without orjson, non-finite floats stay as bare stdlib tokens, which the
    frontend's ``parseJson`` restores.
    """
    assert (
        orjson_dumps_socket([1.0, float("nan"), float("inf")]) == "[1.0,NaN,Infinity]"
    )


def test_fallback_uses_compact_separators(no_orjson):
    """The stdlib fallback emits compact output."""
    assert orjson_dumps_socket({"a": 1, "b": [2, 3]}) == '{"a":1,"b":[2,3]}'


def test_socket_output_always_encodes_as_utf8():
    """A lone surrogate must not reach the transport unescaped.

    orjson rejects one outright, so the payload takes the stdlib fallback,
    whose ``ensure_ascii=False`` would otherwise emit an unencodable string.
    """
    assert orjson_dumps_socket({"path": "bad\udcff"}) == '{"path":"bad\\udcff"}'


_BARE_STRINGS = [
    "",
    "hello",
    "null",
    'with "quotes" and \\ backslash',
    "control\nchars\t",
    "ünïcödé ✨",
]


@pytest.mark.parametrize("value", _BARE_STRINGS)
def test_orjson_dumps_bare_string_matches_stdlib(value):
    """The bare-string fast path must produce exactly what ``json_dumps`` does.

    Args:
        value: The string to serialize.
    """
    assert orjson_dumps(value) == json_dumps(value)


@pytest.mark.parametrize("value", _BARE_STRINGS)
def test_orjson_dumps_bare_string_fallback_matches_stdlib(no_orjson, value):
    """Without orjson the fast path must still emit the same string.

    Args:
        no_orjson: Fixture removing orjson from the format module.
        value: The string to serialize.
    """
    assert orjson_dumps(value) == json_dumps(value)


def test_orjson_dumps_lone_surrogate_falls_back_to_stdlib():
    """Orjson rejects strings that are not valid UTF-8, so the stdlib takes over.

    It must escape the surrogate rather than pass it through: every caller
    writes the result to a UTF-8 file, which a raw surrogate cannot encode.
    """
    assert orjson_dumps("\ud800") == '"\\ud800"'


def test_orjson_dumps_lone_surrogate_without_orjson(no_orjson):
    """The stdlib fast path escapes a lone surrogate the same way.

    Args:
        no_orjson: Fixture removing orjson from the format module.
    """
    assert orjson_dumps("\ud800") == '"\\ud800"'


def test_orjson_dumps_str_subclass_uses_general_path():
    """A str subclass may have a registered serializer, so it must not take the
    ``type(obj) is str`` fast path.
    """

    class _StrSubclass(str):
        pass

    assert orjson_dumps(_StrSubclass("x")) == json_dumps("x")


def test_orjson_dumps_indent_4_falls_back_to_stdlib():
    """Orjson only supports 2-space indent; other widths must not be
    silently coerced to 2.
    """
    out = orjson_dumps({"a": 1}, indent=4)
    assert out == json.dumps({"a": 1}, indent=4, ensure_ascii=False)


def test_orjson_dumps_indent_2_matches_orjson():
    """Two-space indentation is rendered by orjson itself."""
    import orjson as orjson_module

    assert (
        orjson_dumps({"a": 1}, indent=2)
        == orjson_module.dumps({"a": 1}, option=orjson_module.OPT_INDENT_2).decode()
    )


def test_orjson_dumps_type_error_fallback_preserves_kwargs():
    """Orjson raises TypeError for ints > 64-bit; the stdlib fallback must
    keep sort_keys/indent instead of dropping them.
    """
    out = orjson_dumps({"b": 2**70, "a": 1}, sort_keys=True)
    assert out.index('"a"') < out.index('"b"')


def test_orjson_serializes_clean_payload_in_one_pass(monkeypatch: pytest.MonkeyPatch):
    """A payload without None/NaN must not reach the stdlib path."""
    from reflex_base.utils import format as format_module

    def _fail(_obj):
        pytest.fail("stdlib path ran on a clean payload")

    monkeypatch.setattr(format_module, "_json_dumps_socket", _fail)
    payload = {"rows": [{"id": 1, "name": "x", "balance": 1.5}] * 3}
    assert orjson_loads(orjson_dumps_socket(payload)) == payload


def _state_update_packet(delta_values: dict) -> list:
    """Build a socket packet carrying a ``StateUpdate``, as the app emits it.

    Args:
        delta_values: The vars of the single state in the delta.

    Returns:
        The packet.
    """
    from reflex.state import StateUpdate

    return ["event", StateUpdate(delta={"state": delta_values})]


def test_orjson_keeps_its_output_for_none(monkeypatch: pytest.MonkeyPatch):
    """A None puts a null in orjson's output without a non-finite float behind it.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    from reflex_base.utils import format as format_module

    def _fail(_obj):
        pytest.fail("stdlib path ran on a payload without a non-finite float")

    monkeypatch.setattr(format_module, "_json_dumps_socket", _fail)
    payload = _state_update_packet({"a": None, "b": [None, 1.0], "c": "x"})
    assert orjson_dumps_socket(payload) == (
        '["event",{"delta":{"state":{"a":null,"b":[null,1.0],"c":"x"}}}]'
    )


class _DictSubclass(dict):
    pass


class _ListSubclass(list):
    pass


class _NanEnum(Enum):
    NAN = float("nan")


@dataclasses.dataclass
class _Reading:
    value: float
    previous: _Reading | None = None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (float("nan"), "NaN"),
        (_FloatSubclass("inf"), "Infinity"),
        (_DictSubclass(v=float("nan")), '{"v":NaN}'),
        (_ListSubclass([float("-inf")]), "[-Infinity]"),
        (_NanEnum.NAN, "NaN"),
        (
            _Reading(1.0, _Reading(float("-inf"))),
            '{"value":1.0,"previous":{"value":-Infinity,"previous":null}}',
        ),
        (Decimal("NaN"), "NaN"),
    ],
    ids=[
        "float",
        "float_subclass",
        "dict_subclass",
        "list_subclass",
        "enum",
        "nested_dataclass",
        "decimal",
    ],
)
def test_non_finite_float_behind_a_null_is_found(value: Any, expected: str):
    """A non-finite float next to a None reaches the wire as a bare token.

    orjson writes both as null, so the float has to be found wherever orjson
    met it: natively, in a subclass or an Enum, or through ``default``.

    Args:
        value: A value holding a non-finite float.
        expected: The value as the stdlib serializes it.
    """
    payload = _state_update_packet({"n": None, "v": value})
    assert orjson_dumps_socket(payload) == (
        f'["event",{{"delta":{{"state":{{"n":null,"v":{expected}}}}}}}]'
    )


def test_orjson_null_substring_in_string_is_safe():
    """A user string containing 'null' must not be corrupted."""
    payload = {"msg": "the null hypothesis", "n": 1}
    assert orjson_loads(orjson_dumps_socket(payload)) == payload


def test_orjson_none_and_nan_together():
    """Real None stays null while NaN in the same payload stays non-finite."""
    out = orjson_dumps_socket({"a": None, "b": float("nan")})
    assert _wire(out) == {"a": None, "b": "nan"}


# orjson_dumps routes custom types through the serializer registry


def test_orjson_dumps_serializes_dataclass_via_registry():
    """Regression: orjson natively renders a dataclass as its field dict,
    which would turn a Color into ``{"color": ..., "shade": ...}`` instead of
    the CSS string ``serializers.serialize_color`` produces.
    """
    import reflex as rx

    assert orjson_dumps({"c": rx.color("blue", 9)}) == '{"c":"var(--blue-9)"}'


@pytest.mark.parametrize(
    "value",
    [
        datetime.datetime(2026, 4, 25, 10, 30, 45),
        datetime.date(2026, 4, 25),
        datetime.timedelta(seconds=90),
        Path("a/b"),
        UUID(int=5),
        Decimal("1.5"),
        {"nested": [datetime.date(2026, 4, 25)]},
    ],
)
def test_orjson_dumps_matches_json_dumps_for_custom_types(value):
    """``orjson_dumps`` must agree with ``json_dumps`` on every type the
    serializer registry handles, including the ones orjson supports natively.
    """
    assert orjson_loads(orjson_dumps({"v": value})) == json.loads(
        json_dumps({"v": value})
    )


def test_orjson_dumps_ensure_ascii_true_falls_back_to_stdlib():
    """Orjson always emits UTF-8, so an explicit ``ensure_ascii=True`` has to
    go through stdlib instead of being silently ignored.
    """
    assert orjson_dumps({"a": "é"}, ensure_ascii=True) == json.dumps({"a": "é"})


# generated artifacts must not depend on the optional extra


_NULL_FREE_PAYLOAD = {"b": {"nested": [1, 2.5, "café"], "empty": {}}, "a": True}
# Either the None or the dropped Infinity puts a null in orjson's output, which
# sends orjson_dumps to the stdlib in both backends.
_NULL_BEARING_PAYLOAD = {
    "b": {"nested": [1, 2.5, None, "café", float("inf")], "empty": {}},
    "a": True,
}


def test_orjson_dumps_keeps_orjson_output_for_null_free_payload():
    """Pin that a null-free payload really is served by orjson.

    A null anywhere in the output routes ``orjson_dumps`` to the stdlib, so a
    payload carrying one would make the byte-identity test below compare the
    stdlib against itself.
    """
    import orjson as orjson_module

    assert (
        orjson_dumps(_NULL_FREE_PAYLOAD)
        == orjson_module.dumps(_NULL_FREE_PAYLOAD).decode()
    )


@pytest.mark.parametrize(
    "payload", [_NULL_FREE_PAYLOAD, _NULL_BEARING_PAYLOAD], ids=["null_free", "null"]
)
@pytest.mark.parametrize(
    "kwargs",
    [{}, {"indent": 2}, {"sort_keys": True}, {"indent": 2, "sort_keys": True}],
)
def test_orjson_dumps_output_is_backend_independent(
    kwargs: dict, payload: dict, monkeypatch: pytest.MonkeyPatch
):
    """Files rendered with ``orjson_dumps`` (package.json, config files,
    pyi_hashes.json) must be byte-identical with and without orjson.
    """
    from reflex_base.utils import format as format_module

    with_orjson = orjson_dumps(payload, **kwargs)

    monkeypatch.setattr(format_module, "orjson", None)
    assert orjson_dumps(payload, **kwargs) == with_orjson


@pytest.mark.parametrize("value", [1e-5, 1e-7, 1.5e-8])
def test_orjson_dumps_small_floats_are_backend_dependent(
    value: float, monkeypatch: pytest.MonkeyPatch
):
    """Pin the one documented gap in ``orjson_dumps``' byte-identity.

    Below 1e-4 the two backends pick different float representations and
    neither exposes a hook to change it. Artifact hashes are unaffected --
    ``get_package_json_and_hash`` serializes with the stdlib -- but a byte
    comparison against a file the other backend wrote can report a change.

    Args:
        value: A float small enough to trigger the divergence.
        monkeypatch: The pytest monkeypatch fixture.
    """
    from reflex_base.utils import format as format_module

    with_orjson = orjson_dumps({"a": value})

    monkeypatch.setattr(format_module, "orjson", None)
    without_orjson = orjson_dumps({"a": value})

    assert with_orjson != without_orjson
    assert json.loads(with_orjson) == json.loads(without_orjson) == {"a": value}


def test_orjson_dumps_keeps_non_finite_floats_as_bare_tokens():
    """Orjson would emit null for these; the stdlib tokens are valid literals
    in the JS files ``orjson_dumps`` renders, so it takes over instead.
    """
    out = orjson_dumps({"x": float("inf"), "y": float("nan"), "z": None})
    assert out == '{"x":Infinity,"y":NaN,"z":null}'


def test_orjson_dumps_large_int_fallback_stays_compact():
    """The >64-bit fallback must keep orjson's compact separators, so one big
    number in an artifact cannot reformat the whole file.
    """
    assert orjson_dumps({"a": 2**70, "b": 1}) == f'{{"a":{2**70},"b":1}}'


class _Unserializable:
    """A type with no registered serializer."""


def test_orjson_dumps_rejects_unserializable_type():
    """An unregistered type must raise, not become ``null``.

    Every ``orjson_dumps`` call site replaced a bare ``json.dumps``, which
    raised ``TypeError``. Emitting ``null`` instead would silently drop a
    tailwind theme entry or a package.json field.
    """
    with pytest.raises(TypeError, match="not JSON serializable"):
        orjson_dumps({"theme": {"colors": {"brand": _Unserializable()}}})


def test_orjson_dumps_rejects_unserializable_type_without_orjson(no_orjson):
    """The stdlib path must reject the same payload the orjson path rejects.

    Args:
        no_orjson: Fixture simulating orjson not being installed.
    """
    with pytest.raises(TypeError, match="not JSON serializable"):
        orjson_dumps({"theme": {"colors": {"brand": _Unserializable()}}})


def test_orjson_dumps_socket_keeps_unserializable_lenient():
    """Socket payloads keep the pre-existing ``json_dumps`` leniency.

    The socket codec replaced ``format.json_dumps``, which serialized an
    unregistered value as ``null`` rather than dropping the state update.
    """
    assert orjson_dumps_socket({"a": _Unserializable()}) == '{"a":null}'


def test_orjson_dumps_escapes_lone_surrogate():
    """A lone surrogate must not reach a UTF-8 encoder as a raw character.

    orjson rejects such strings, and the stdlib fallback used
    ``ensure_ascii=False``, leaving a raw surrogate that ``write_file`` then
    could not encode.
    """
    out = orjson_dumps("bad\ud800end")

    assert out.encode("utf-8")


@pytest.mark.parametrize(
    "kwargs", [{}, {"indent": 2}, {"indent": 4}, {"ensure_ascii": True}]
)
def test_orjson_dumps_rejects_unserializable_type_for_every_kwarg_path(kwargs: dict):
    """Strictness must not depend on which backend path the kwargs select.

    Args:
        kwargs: Keyword arguments steering orjson_dumps to a different path.
    """
    with pytest.raises(TypeError, match="not JSON serializable"):
        orjson_dumps({"a": _Unserializable()}, **kwargs)
