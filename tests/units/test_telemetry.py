import pytest
from packaging.version import parse as parse_python_version
from pytest_mock import MockerFixture

from reflex.utils import telemetry


@pytest.fixture
def event_defaults(mocker: MockerFixture) -> dict:
    """Patch ``get_event_defaults()`` with a fresh dict.

    Returns:
        The dict that ``get_event_defaults()`` is patched to return, so tests
        can assert it isn't mutated by the code under test.
    """
    defaults = {
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
    mocker.patch("reflex.utils.telemetry.get_event_defaults", return_value=defaults)
    return defaults


@pytest.fixture
def httpx_post(mocker: MockerFixture):
    """Mock ``httpx.post`` used by ``telemetry._send``.

    Returns:
        The mock for ``httpx.post`` so tests can assert on the posted payload.
    """
    return mocker.patch("httpx.post")


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
def test_send(event_defaults, httpx_post, event, kwargs, expected_props):
    telemetry._send(event, telemetry_enabled=True, **kwargs)
    httpx_post.assert_called_once()
    posted = httpx_post.call_args.kwargs["json"]
    assert posted["event"] == event
    for key, value in expected_props.items():
        assert posted["properties"][key] == value


def test_send_does_not_leak_kwargs_between_events(event_defaults, httpx_post):
    """Per-event kwargs must not leak into a subsequent event's payload."""
    telemetry._send("export", telemetry_enabled=True, status="success", duration=1.0)
    telemetry._send(
        "export",
        telemetry_enabled=True,
        status="failure",
        detail="ValueError",
        duration=2.0,
    )

    assert httpx_post.call_count == 2
    first_props = httpx_post.call_args_list[0].kwargs["json"]["properties"]
    second_props = httpx_post.call_args_list[1].kwargs["json"]["properties"]

    assert first_props["status"] == "success"
    assert first_props["duration"] == pytest.approx(1.0)
    assert "detail" not in first_props

    assert second_props["status"] == "failure"
    assert second_props["detail"] == "ValueError"
    assert second_props["duration"] == pytest.approx(2.0)

    # The cached defaults must not have been polluted by either call.
    assert "status" not in event_defaults["properties"]
    assert "duration" not in event_defaults["properties"]
    assert "detail" not in event_defaults["properties"]


def test_send_drops_unknown_kwargs(event_defaults, httpx_post):
    """Unknown kwargs must not land in the posted payload."""
    telemetry._send("export", telemetry_enabled=True, foo="bar", secret="leak")
    httpx_post.assert_called_once()
    props = httpx_post.call_args.kwargs["json"]["properties"]
    assert "foo" not in props
    assert "secret" not in props


def test_send_drops_none_kwargs(event_defaults, httpx_post):
    """None-valued kwargs for allowed keys are omitted from the posted payload."""
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
    httpx_post.assert_called_once()
    props = httpx_post.call_args.kwargs["json"]["properties"]
    assert props["status"] == "success"
    assert props["build_duration"] == pytest.approx(0.05)
    assert "detail" not in props
    assert "compile_duration" not in props
    assert "zip_duration" not in props


def test_prepare_event_merges_properties(event_defaults):
    """``properties`` payloads are merged into the event properties."""
    event = telemetry._prepare_event(
        "compile",
        properties={"pages_count": 7, "trigger": "initial"},
    )

    assert event is not None
    assert event["event"] == "compile"
    props: dict = event["properties"]  # pyright: ignore[reportAssignmentType]
    assert props["pages_count"] == 7
    assert props["trigger"] == "initial"
    # Existing default keys are preserved.
    assert props["user_os"] == "Test OS"


def test_prepare_event_does_not_mutate_cached_defaults(event_defaults):
    """``_prepare_event`` must not mutate the @once_unless_none cached defaults."""
    cached_props_snapshot = dict(event_defaults["properties"])

    telemetry._prepare_event("init", template="my-template")
    telemetry._prepare_event(
        "compile",
        properties={"pages_count": 3, "duration_ms": 42},
    )

    assert event_defaults["properties"] == cached_props_snapshot
    assert "template" not in event_defaults["properties"]
    assert "pages_count" not in event_defaults["properties"]
    assert "duration_ms" not in event_defaults["properties"]


def test_prepare_event_properties_override_kwargs(event_defaults):
    """If both kwargs and properties supply the same key, properties wins."""
    event = telemetry._prepare_event(
        "init",
        template="from-kwarg",
        properties={"template": "from-properties"},
    )

    assert event is not None
    props: dict = event["properties"]  # pyright: ignore[reportAssignmentType]
    assert props["template"] == "from-properties"
