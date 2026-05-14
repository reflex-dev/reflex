import pytest
from packaging.version import parse as parse_python_version
from pytest_mock import MockerFixture

from reflex.utils import telemetry


def _mock_event_defaults() -> dict:
    return {
        "api_key": "test_api_key",
        "properties": {
            "distinct_id": 12345,
            "distinct_app_id": 78285505863498957834586115958872998605,
            "user_os": "Test OS",
            "user_os_detail": "Mocked Platform",
            "reflex_version": "0.8.0",
            "python_version": "3.8.0",
            "node_version": None,
            "bun_version": None,
            "reflex_enterprise_version": None,
            "cpu_count": 4,
            "memory": 8192,
            "cpu_info": {},
        },
    }


def _patch_event_defaults(mocker: MockerFixture, value):
    """Replace the cached get_event_defaults() so it returns ``value``, bypassing the once_unless_none cache."""
    mocker.patch("reflex.utils.telemetry.get_event_defaults", return_value=value)


def test_telemetry():
    """Test that telemetry is sent correctly."""
    # Check that the user OS is one of the supported operating systems.
    user_os = telemetry.get_os()
    assert user_os is not None
    assert user_os in ["Linux", "Darwin", "Java", "Windows"]

    # Check that the CPU count and memory are greater than 0.
    assert telemetry.get_cpu_count() > 0

    # Check that the Reflex version is not None.
    assert telemetry.get_reflex_version() is not None

    # Check that the Python version is greater than 3.7.
    python_version = telemetry.get_python_version()
    assert python_version is not None
    assert parse_python_version(python_version) >= parse_python_version("3.7")


def test_disable():
    """Test that disabling telemetry works."""
    assert not telemetry._send("test", telemetry_enabled=False)


@pytest.mark.parametrize(
    ("event", "kwargs", "expected_props"),
    [
        ("init", {}, {}),
        ("reinit", {}, {}),
        ("run-dev", {}, {}),
        ("run-prod", {}, {}),
        ("export", {}, {}),
        (
            "export",
            {"status": "success", "duration": 1.23},
            {"status": "success", "duration": 1.23},
        ),
        (
            "export",
            {
                "status": "failure",
                "detail": "ValueError",
                "duration": 0.5,
                "compile_duration": 0.4,
            },
            {
                "status": "failure",
                "detail": "ValueError",
                "duration": 0.5,
                "compile_duration": 0.4,
            },
        ),
    ],
)
def test_send(mocker: MockerFixture, event, kwargs, expected_props):
    httpx_post_mock = mocker.patch("httpx.post")
    _patch_event_defaults(mocker, _mock_event_defaults())

    telemetry._send(event, telemetry_enabled=True, **kwargs)
    httpx_post_mock.assert_called_once()
    posted = httpx_post_mock.call_args.kwargs["json"]
    assert posted["event"] == event
    for key, value in expected_props.items():
        assert posted["properties"][key] == value


def test_send_does_not_leak_kwargs_between_events(mocker: MockerFixture):
    """Per-event kwargs must not leak into a subsequent event's payload."""
    httpx_post_mock = mocker.patch("httpx.post")
    defaults = _mock_event_defaults()
    _patch_event_defaults(mocker, defaults)

    telemetry._send("export", telemetry_enabled=True, status="success", duration=1.0)
    telemetry._send(
        "export",
        telemetry_enabled=True,
        status="failure",
        detail="ValueError",
        duration=2.0,
    )

    assert httpx_post_mock.call_count == 2
    first_props = httpx_post_mock.call_args_list[0].kwargs["json"]["properties"]
    second_props = httpx_post_mock.call_args_list[1].kwargs["json"]["properties"]

    assert first_props["status"] == "success"
    assert first_props["duration"] == pytest.approx(1.0)
    assert "detail" not in first_props

    assert second_props["status"] == "failure"
    assert second_props["detail"] == "ValueError"
    assert second_props["duration"] == pytest.approx(2.0)

    # The cached defaults must not have been polluted by either call.
    assert "status" not in defaults["properties"]
    assert "duration" not in defaults["properties"]
    assert "detail" not in defaults["properties"]


def test_send_drops_unknown_kwargs(mocker: MockerFixture):
    """Unknown kwargs must not land in the posted payload."""
    httpx_post_mock = mocker.patch("httpx.post")
    _patch_event_defaults(mocker, _mock_event_defaults())

    telemetry._send("export", telemetry_enabled=True, foo="bar", secret="leak")
    httpx_post_mock.assert_called_once()
    props = httpx_post_mock.call_args.kwargs["json"]["properties"]
    assert "foo" not in props
    assert "secret" not in props


def test_send_drops_none_kwargs(mocker: MockerFixture):
    """None-valued kwargs for allowed keys are omitted from the posted payload."""
    httpx_post_mock = mocker.patch("httpx.post")
    _patch_event_defaults(mocker, _mock_event_defaults())

    telemetry._send(
        "export",
        telemetry_enabled=True,
        status="success",
        detail=None,
        duration=0.1,
        compile_duration=None,
        build_duration=0.05,
        zip_duration=None,
    )
    httpx_post_mock.assert_called_once()
    props = httpx_post_mock.call_args.kwargs["json"]["properties"]
    assert props["status"] == "success"
    assert props["build_duration"] == pytest.approx(0.05)
    assert "detail" not in props
    assert "compile_duration" not in props
    assert "zip_duration" not in props
