import datetime

import pytest

from reflex.utils import serializers


@pytest.fixture
def sending_user(mail_admin):
    user = mail_admin.create_user()
    yield user
    mail_admin.delete_user(user)


@pytest.mark.parametrize(
    "type_,expected",
    [
        (str, True),
        (dict, True),
        (dict[int, int], True),
    ],
)
def test_has_serializer(type_, expected):
    assert serializers.has_serializer(type_) == expected


@pytest.mark.parametrize(
    "type_,expected",
    [
        (str, serializers.serialize_str),
        (dict, serializers.serialize_dict),
        (dict[int, int], serializers.serialize_dict),
        (datetime.datetime, serializers.serialize_datetime),
        (datetime.date, serializers.serialize_datetime),
        (datetime.time, serializers.serialize_datetime),
        (datetime.timedelta, serializers.serialize_datetime),
    ],
)
def test_get_serializer(type_, expected):
    assert serializers.get_serializer(type_) == expected


def test_add_serializer():
    def serialize_test(value: int) -> str:
        return str(value)

    # Initially there should be no serializer for int.
    assert not serializers.has_serializer(int)
    assert serializers.serialize(5) is None

    # Register the serializer.
    serializers.serializer(serialize_test)

    # There should now be a serializer for int.
    assert serializers.has_serializer(int)
    assert serializers.get_serializer(int) == serialize_test
    assert serializers.serialize(5) == "5"

    # Remove the serializer.
    serializers.SERIALIZERS.pop(int)


def test_serialize_str():
    assert serializers.serialize_str("test") == "test"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("test", "test"),
        (datetime.datetime(2021, 1, 1, 1, 1, 1, 1), "2021-01-01 01:01:01.000001"),
        (datetime.date(2021, 1, 1), "2021-01-01"),
        (datetime.time(1, 1, 1, 1), "01:01:01.000001"),
        (datetime.timedelta(1, 1, 1), "1 day, 0:00:01.000001"),
        (5, None),
        (None, None),
        ([], None),
    ],
)
def test_serialize(value, expected):
    assert serializers.serialize(value) == expected
