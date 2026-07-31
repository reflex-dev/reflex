import asyncio
import importlib.metadata
import threading
import uuid
from types import SimpleNamespace

import pytest
from packaging.version import parse as parse_python_version
from pytest_mock import MockerFixture

from reflex.utils import telemetry


@pytest.fixture(autouse=True)
def _drain_telemetry_executor():
    """Drain any queued telemetry work so jobs never leak across tests.

    Most tests mock ``telemetry.send`` and never touch the worker pool, but the
    ones exercising the real ``send`` path enqueue work on the shared executor.
    Flushing on teardown keeps a slow or failed job from running against the
    next test's mocks.

    Yields:
        Control to the test, flushing the telemetry executor afterwards.
    """
    yield
    telemetry._flush()


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
            # Post-conversion defaults carry UUID-string identifiers (the hex
            # forms of 12345 and 78285505863498957834586115958872998605).
            "distinct_id": "00000000-0000-0000-0000-000000003039",
            "distinct_app_id": "3ae53d70-56b0-b52a-f645-37040fb802cd",
            "user_os": "Test OS",
            "user_os_detail": "Mocked Platform",
            "reflex_version": "0.8.0",
            "python_version": "3.8.0",
            "node_version": None,
            "bun_version": None,
            "reflex_enterprise_version": None,
            "reflex_package_version": {},
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


def test_get_reflex_package_versions_real_environment():
    """The first-party reflex subpackages are discovered with string versions."""
    versions = telemetry.get_reflex_package_versions()

    assert isinstance(versions, dict)
    # reflex-base is a declared dependency, so it is always installed in the env.
    assert "reflex-base" in versions
    # Only reflex subpackages are reported, each with a string version.
    for name, value in versions.items():
        assert name.startswith("reflex-")
        assert isinstance(value, str)
    # The main reflex package is reported separately via get_reflex_version.
    assert "reflex" not in versions


def test_get_reflex_package_versions_reports_only_first_party(mocker: MockerFixture):
    """Only reflex's own subpackage dependencies are reported, by installed version.

    Third-party ``reflex-*`` packages a user happens to have installed are not in
    reflex's declared dependencies, so they must never be reported.
    """
    mocker.patch(
        "importlib.metadata.requires",
        return_value=[
            "reflex-base>=0.9.4",
            "reflex-components-radix>=0.9.2",
            "reflex-hosting-cli>=0.1.66",
            "httpx<1.0,>=0.26",
            'pydantic>=2.12.0; extra == "db"',
        ],
    )
    installed = {
        "reflex-base": "0.9.4",
        "reflex-components-radix": "0.9.2",
        # reflex-hosting-cli is a declared dependency but is not installed here.
        "httpx": "0.27.0",
        "pydantic": "2.12.0",
        # A third-party reflex-* package installed separately by the user.
        "reflex-enterprise": "1.2.3",
    }

    def fake_version(name: str) -> str:
        try:
            return installed[name]
        except KeyError as exc:
            raise importlib.metadata.PackageNotFoundError(name) from exc

    mocker.patch("importlib.metadata.version", side_effect=fake_version)

    assert telemetry.get_reflex_package_versions() == {
        "reflex-base": "0.9.4",
        "reflex-components-radix": "0.9.2",
    }


def test_get_reflex_package_versions_handles_missing_reflex_metadata(
    mocker: MockerFixture,
):
    """An empty dict is returned when the reflex distribution metadata is absent."""
    mocker.patch(
        "importlib.metadata.requires",
        side_effect=importlib.metadata.PackageNotFoundError,
    )

    assert telemetry.get_reflex_package_versions() == {}


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


@pytest.fixture
def venv_state(monkeypatch: pytest.MonkeyPatch):
    """Force a deterministic `is_in_virtualenv` reading.

    Returns:
        A callable that overrides `sys.prefix`, `sys.base_prefix`, and the
        `VIRTUAL_ENV` env-var for the duration of the test.
    """

    def configure(*, prefix: str, base_prefix: str, virtual_env: str | None) -> None:
        monkeypatch.setattr(telemetry.sys, "prefix", prefix)
        monkeypatch.setattr(telemetry.sys, "base_prefix", base_prefix)
        if virtual_env is None:
            monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        else:
            monkeypatch.setenv("VIRTUAL_ENV", virtual_env)

    return configure


def test_is_in_virtualenv_detects_pep_405_venv(venv_state):
    venv_state(prefix="/tmp/venv", base_prefix="/usr", virtual_env=None)
    assert telemetry.is_in_virtualenv() is True


def test_is_in_virtualenv_falls_back_to_virtual_env_var(venv_state):
    venv_state(prefix="/usr", base_prefix="/usr", virtual_env="/tmp/venv")
    assert telemetry.is_in_virtualenv() is True


def test_is_in_virtualenv_returns_false_for_system_python(venv_state):
    venv_state(prefix="/usr", base_prefix="/usr", virtual_env=None)
    assert telemetry.is_in_virtualenv() is False


@pytest.fixture
def patch_telemetry_config(mocker: MockerFixture):
    """Patch ``telemetry.get_config`` with a stub of a chosen ``telemetry_enabled``.

    Returns:
        A callable ``patch(enabled)`` that installs the mock on demand.
    """

    def patch(*, enabled: bool) -> None:
        mocker.patch(
            "reflex.utils.telemetry.get_config",
            return_value=SimpleNamespace(telemetry_enabled=enabled),
        )

    return patch


@pytest.fixture
def init_environment_cwd(
    tmp_path, monkeypatch: pytest.MonkeyPatch, patch_telemetry_config
):
    """Chdir into a clean tmp dir and force telemetry-enabled config.

    Returns:
        The temporary directory now serving as the working directory.
    """
    monkeypatch.chdir(tmp_path)
    patch_telemetry_config(enabled=True)
    return tmp_path


def test_get_init_environment_reports_dependency_files(
    init_environment_cwd, venv_state
):
    (init_environment_cwd / "pyproject.toml").write_text("")
    (init_environment_cwd / "uv.lock").write_text("")
    (init_environment_cwd / "reflex.lock").mkdir()
    venv_state(prefix="/tmp/venv", base_prefix="/usr", virtual_env=None)

    assert telemetry.get_init_environment() == {
        "in_virtualenv": True,
        "has_pyproject_toml": True,
        "has_requirements_txt": False,
        "has_uv_lock": True,
        "has_reflex_lock": True,
    }


def test_get_init_environment_reports_requirements_txt(
    init_environment_cwd, venv_state
):
    (init_environment_cwd / "requirements.txt").write_text("")
    venv_state(prefix="/usr", base_prefix="/usr", virtual_env="/tmp/venv")

    assert telemetry.get_init_environment() == {
        "in_virtualenv": True,
        "has_pyproject_toml": False,
        "has_requirements_txt": True,
        "has_uv_lock": False,
        "has_reflex_lock": False,
    }


def test_get_init_environment_empty_directory(init_environment_cwd, venv_state):
    venv_state(prefix="/usr", base_prefix="/usr", virtual_env=None)

    assert telemetry.get_init_environment() == {
        "in_virtualenv": False,
        "has_pyproject_toml": False,
        "has_requirements_txt": False,
        "has_uv_lock": False,
        "has_reflex_lock": False,
    }


def test_get_init_environment_short_circuits_when_telemetry_disabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch, patch_telemetry_config
):
    """When telemetry is disabled the env snapshot is skipped entirely.

    A pyproject.toml is staged so a non-short-circuiting implementation would
    surface ``has_pyproject_toml: True`` instead of an empty dict.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("")
    patch_telemetry_config(enabled=False)

    assert telemetry.get_init_environment() == {}


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


def test_encode_distinct_id_round_trips_losslessly():
    """A legacy 128-bit integer id encodes to UUID without losing precision."""
    legacy_id = 78285505863498957834586115958872998605
    encoded = telemetry._encode_distinct_id(legacy_id)

    assert isinstance(encoded, str)
    assert encoded == str(uuid.UUID(int=legacy_id))
    # Full 128-bit fidelity is preserved, unlike the old float-truncated int.
    assert uuid.UUID(encoded).int == legacy_id


def test_encode_distinct_id_handles_uuid4_int_form():
    """A freshly generated uuid4 round-trips through its integer storage form."""
    generated = uuid.uuid4()
    assert telemetry._encode_distinct_id(generated.int) == str(generated)


def test_encode_distinct_id_pads_small_values():
    """Small integers still encode to a valid, zero-padded UUID string."""
    encoded = telemetry._encode_distinct_id(12345)
    assert encoded == "00000000-0000-0000-0000-000000003039"
    assert uuid.UUID(encoded).int == 12345


@pytest.fixture
def stub_event_default_sources(mocker: MockerFixture):
    """Stub the slow/host-specific inputs of ``_get_event_defaults``.

    Returns:
        A callable ``configure(installation_id, project_hash)`` that sets the
        stored identifier values feeding the default event payload.
    """
    mocker.patch.object(telemetry, "get_cpu_info", return_value=None)
    mocker.patch.object(telemetry, "get_node_version", return_value=None)
    mocker.patch.object(telemetry, "get_bun_version", return_value=None)

    def configure(*, installation_id: int | None, project_hash: int | None) -> None:
        mocker.patch.object(
            telemetry, "ensure_reflex_installation_id", return_value=installation_id
        )
        mocker.patch.object(telemetry, "get_project_hash", return_value=project_hash)

    return configure


def test_get_event_defaults_encodes_ids_as_uuid_strings(stub_event_default_sources):
    """distinct_id and distinct_app_id are sent as lossless UUID strings.

    Regression: previously these were raw 128-bit ints that PostHog truncated
    to floats, collapsing distinct installs/apps onto one identifier.
    """
    installation_id = 0xDEADBEEFDEADBEEFDEADBEEFDEADBEEF
    project_hash = 78285505863498957834586115958872998605
    stub_event_default_sources(
        installation_id=installation_id, project_hash=project_hash
    )

    defaults = telemetry._get_event_defaults()

    assert defaults is not None
    props: dict = defaults["properties"]  # pyright: ignore[reportAssignmentType]
    assert isinstance(props["distinct_id"], str)
    assert isinstance(props["distinct_app_id"], str)
    assert props["distinct_id"] == str(uuid.UUID(int=installation_id))
    assert props["distinct_app_id"] == str(uuid.UUID(int=project_hash))
    # Continuity: each encoded id decodes back to the original integer value.
    assert uuid.UUID(props["distinct_id"]).int == installation_id
    assert uuid.UUID(props["distinct_app_id"]).int == project_hash


def test_get_event_defaults_omits_distinct_app_id_without_project_hash(
    stub_event_default_sources,
):
    """No distinct_app_id is emitted when the project hash is unavailable."""
    stub_event_default_sources(installation_id=12345, project_hash=None)

    defaults = telemetry._get_event_defaults()

    assert defaults is not None
    assert "distinct_app_id" not in defaults["properties"]
    assert defaults["properties"]["distinct_id"] == str(uuid.UUID(int=12345))


def test_get_event_defaults_returns_none_without_installation_id(
    stub_event_default_sources,
):
    """A missing installation id short-circuits defaults (unchanged contract)."""
    stub_event_default_sources(installation_id=None, project_hash=12345)
    assert telemetry._get_event_defaults() is None


@pytest.fixture(autouse=True)
def _reset_alias_guard():
    """Reset the per-process alias guard so each test starts fresh."""
    telemetry._legacy_alias_attempted = False
    yield
    telemetry._legacy_alias_attempted = False


def test_maybe_alias_sends_create_alias_for_legacy_install(mocker: MockerFixture):
    """A legacy install (no semantics marker) aliases and then marks itself."""
    mocker.patch.object(telemetry, "ensure_reflex_installation_id", return_value=12345)
    mocker.patch.object(telemetry, "has_uuid_distinct_id_semantics", return_value=False)
    mark = mocker.patch.object(telemetry, "mark_uuid_distinct_id_semantics")
    send_mock = mocker.patch.object(telemetry, "send")

    telemetry._maybe_alias_legacy_distinct_id(telemetry_enabled=True)

    send_mock.assert_called_once_with(
        "$create_alias", True, properties={"alias": 12345}
    )
    mark.assert_called_once()


def test_maybe_alias_skips_for_uuid_native_install(mocker: MockerFixture):
    """An install already on UUID semantics sends no alias and is not re-marked."""
    mocker.patch.object(telemetry, "ensure_reflex_installation_id", return_value=12345)
    mocker.patch.object(telemetry, "has_uuid_distinct_id_semantics", return_value=True)
    mark = mocker.patch.object(telemetry, "mark_uuid_distinct_id_semantics")
    send_mock = mocker.patch.object(telemetry, "send")

    telemetry._maybe_alias_legacy_distinct_id(telemetry_enabled=True)

    send_mock.assert_not_called()
    mark.assert_not_called()


def test_maybe_alias_skips_without_installation_id(mocker: MockerFixture):
    """No installation id means no alias, no marker, and no semantics check."""
    mocker.patch.object(telemetry, "ensure_reflex_installation_id", return_value=None)
    has = mocker.patch.object(telemetry, "has_uuid_distinct_id_semantics")
    mark = mocker.patch.object(telemetry, "mark_uuid_distinct_id_semantics")
    send_mock = mocker.patch.object(telemetry, "send")

    telemetry._maybe_alias_legacy_distinct_id(telemetry_enabled=True)

    send_mock.assert_not_called()
    mark.assert_not_called()
    has.assert_not_called()


def test_maybe_alias_skips_when_telemetry_disabled(mocker: MockerFixture):
    """Disabled telemetry does no work and leaves the marker unwritten."""
    ensure = mocker.patch.object(telemetry, "ensure_reflex_installation_id")
    send_mock = mocker.patch.object(telemetry, "send")

    telemetry._maybe_alias_legacy_distinct_id(telemetry_enabled=False)

    ensure.assert_not_called()
    send_mock.assert_not_called()


def test_maybe_alias_runs_at_most_once_per_process(mocker: MockerFixture):
    """The guard prevents a second alias attempt within the same process."""
    mocker.patch.object(telemetry, "ensure_reflex_installation_id", return_value=7)
    mocker.patch.object(telemetry, "has_uuid_distinct_id_semantics", return_value=False)
    mocker.patch.object(telemetry, "mark_uuid_distinct_id_semantics")
    send_mock = mocker.patch.object(telemetry, "send")

    telemetry._maybe_alias_legacy_distinct_id(telemetry_enabled=True)
    telemetry._maybe_alias_legacy_distinct_id(telemetry_enabled=True)

    send_mock.assert_called_once()


def test_maybe_alias_create_alias_payload(
    event_defaults, httpx_post, mocker: MockerFixture
):
    """The posted $create_alias pairs the new UUID distinct_id with the legacy int."""
    mocker.patch.object(telemetry, "has_uuid_distinct_id_semantics", return_value=False)
    mocker.patch.object(telemetry, "mark_uuid_distinct_id_semantics")
    legacy_id = 78285505863498957834586115958872998605
    mocker.patch.object(
        telemetry, "ensure_reflex_installation_id", return_value=legacy_id
    )

    telemetry._maybe_alias_legacy_distinct_id(telemetry_enabled=True)
    # The $create_alias is now sent on the telemetry worker thread; wait for it.
    telemetry._flush()

    httpx_post.assert_called_once()
    payload = httpx_post.call_args.kwargs["json"]
    assert payload["event"] == "$create_alias"
    props = payload["properties"]
    # The legacy integer is sent at full precision so PostHog re-coerces it to
    # the same lossy float as the historic events and merges the two persons.
    assert props["alias"] == legacy_id
    # distinct_id is the new UUID-string identity (from the event defaults).
    assert props["distinct_id"] == event_defaults["properties"]["distinct_id"]


def test_telemetry_executor_is_lazy_and_single_worker():
    """The telemetry executor is created once and runs exactly one worker."""
    executor = telemetry._get_telemetry_executor()
    # Cached: repeated lookups return the same lazily-created pool.
    assert executor is telemetry._get_telemetry_executor()
    assert executor._max_workers == 1


def test_process_event_aliases_then_sends(mocker: MockerFixture):
    """``_process_event`` runs the alias migration before delivering the event."""
    alias = mocker.patch.object(telemetry, "_maybe_alias_legacy_distinct_id")
    send = mocker.patch.object(telemetry, "_send")

    telemetry._process_event("init", True, properties={"x": 1}, template="t")

    alias.assert_called_once_with(True)
    send.assert_called_once_with("init", True, properties={"x": 1}, template="t")


def test_send_disabled_does_not_submit(mocker: MockerFixture):
    """Disabled telemetry queues no work and never spins up the worker pool."""
    submit = mocker.patch.object(telemetry, "_submit")

    telemetry.send("run-dev", telemetry_enabled=False)

    submit.assert_not_called()


def test_send_resolves_enabled_from_config(
    mocker: MockerFixture, patch_telemetry_config
):
    """With ``telemetry_enabled`` unspecified, ``send`` consults the config."""
    submit = mocker.patch.object(telemetry, "_submit")

    patch_telemetry_config(enabled=False)
    telemetry.send("run-dev")
    submit.assert_not_called()

    patch_telemetry_config(enabled=True)
    telemetry.send("run-dev")
    submit.assert_called_once()


def test_send_processes_event_off_caller_thread(mocker: MockerFixture):
    """``send`` collects and delivers the event on the worker, not the caller.

    Regression for #6618: telemetry collection (blocking syscalls/subprocess)
    and the synchronous HTTP post previously ran on the caller's thread — and,
    inside an event loop, on the loop thread via a task that never awaited —
    blocking the event loop. The work must now happen on a separate thread.
    """
    mocker.patch.object(telemetry, "_maybe_alias_legacy_distinct_id")
    seen: dict[str, threading.Thread] = {}

    def record(*_args, **_kwargs) -> bool:
        seen["thread"] = threading.current_thread()
        return True

    mocker.patch.object(telemetry, "_send", side_effect=record)

    telemetry.send("run-dev", telemetry_enabled=True)
    telemetry._flush()

    assert seen["thread"] is not threading.current_thread()
    assert seen["thread"] is not threading.main_thread()


async def test_send_within_event_loop_runs_off_loop_thread(mocker: MockerFixture):
    """Inside a running event loop, ``send`` offloads work to the worker thread.

    This is the core scenario from #6618: at runtime ``send`` is called from the
    asyncio event loop (e.g. backend error telemetry), and the blocking work
    must not execute on the loop thread.
    """
    loop_thread = threading.current_thread()
    mocker.patch.object(telemetry, "_maybe_alias_legacy_distinct_id")
    seen: dict[str, threading.Thread] = {}

    def record(*_args, **_kwargs) -> bool:
        seen["thread"] = threading.current_thread()
        return True

    mocker.patch.object(telemetry, "_send", side_effect=record)

    telemetry.send("error", telemetry_enabled=True)
    # Wait for the worker without blocking the event loop ourselves.
    await asyncio.to_thread(telemetry._flush)

    assert seen["thread"] is not loop_thread


def test_send_suppresses_worker_errors(mocker: MockerFixture):
    """A failed telemetry send is swallowed and never reaches the caller."""
    mocker.patch.object(telemetry, "_maybe_alias_legacy_distinct_id")
    mocker.patch.object(telemetry, "_send", side_effect=RuntimeError("boom"))

    # Neither queuing the event nor draining the failed job may raise.
    telemetry.send("run-prod", telemetry_enabled=True)
    telemetry._flush()


def test_flush_returns_true_when_queue_drains(mocker: MockerFixture):
    """``_flush`` reports success once the queued work has been processed."""
    mocker.patch.object(telemetry, "_maybe_alias_legacy_distinct_id")
    mocker.patch.object(telemetry, "_send", return_value=True)

    telemetry.send("run-dev", telemetry_enabled=True)

    assert telemetry._flush() is True


def test_flush_returns_false_when_worker_does_not_drain_in_time():
    """``_flush`` reports failure when the queue cannot drain within the timeout.

    A blocking job occupies the single worker so the flush sentinel cannot run;
    the bounded wait must surface the incomplete drain rather than swallow it.
    """
    release = threading.Event()
    # Bound the worker's wait so a failing assertion can never wedge the shared
    # executor (and the autouse drain fixture) indefinitely.
    blocker = telemetry._get_telemetry_executor().submit(release.wait, 10)
    try:
        assert telemetry._flush(timeout=0.05) is False
    finally:
        release.set()
        blocker.result(timeout=5)
