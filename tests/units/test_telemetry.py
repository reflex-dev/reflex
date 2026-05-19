import pytest
from packaging.version import parse as parse_python_version
from pytest_mock import MockerFixture

from reflex.utils import telemetry


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


@pytest.mark.parametrize("event", ["init", "reinit", "run-dev", "run-prod", "export"])
def test_send(mocker: MockerFixture, event):
    httpx_post_mock = mocker.patch("httpx.post")

    # Mock _get_event_defaults to return a complete valid response
    mock_defaults = {
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
    mocker.patch(
        "reflex.utils.telemetry._get_event_defaults", return_value=mock_defaults
    )

    telemetry._send(event, telemetry_enabled=True)
    httpx_post_mock.assert_called_once()


def _make_mock_defaults():
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


def test_prepare_event_merges_properties(mocker: MockerFixture):
    mocker.patch(
        "reflex.utils.telemetry._get_event_defaults",
        return_value=_make_mock_defaults(),
    )

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


def test_prepare_event_does_not_mutate_cached_defaults(mocker: MockerFixture):
    """``_prepare_event`` must not mutate the @once_unless_none cached defaults."""
    cached = _make_mock_defaults()
    mocker.patch(
        "reflex.utils.telemetry._get_event_defaults",
        return_value=cached,
    )

    cached_props_snapshot = dict(cached["properties"])

    telemetry._prepare_event("init", template="my-template")
    telemetry._prepare_event(
        "compile",
        properties={"pages_count": 3, "duration_ms": 42},
    )

    assert cached["properties"] == cached_props_snapshot
    assert "template" not in cached["properties"]
    assert "pages_count" not in cached["properties"]
    assert "duration_ms" not in cached["properties"]


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
def init_environment_cwd(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Chdir into a clean tmp dir and let the caller stage dependency files.

    Returns:
        The temporary directory now serving as the working directory.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_get_init_environment_reports_dependency_files(
    init_environment_cwd, venv_state
):
    (init_environment_cwd / "pyproject.toml").write_text("")
    venv_state(prefix="/tmp/venv", base_prefix="/usr", virtual_env=None)

    assert telemetry.get_init_environment() == {
        "in_virtualenv": True,
        "has_pyproject_toml": True,
        "has_requirements_txt": False,
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
    }


def test_get_init_environment_empty_directory(init_environment_cwd, venv_state):
    venv_state(prefix="/usr", base_prefix="/usr", virtual_env=None)

    assert telemetry.get_init_environment() == {
        "in_virtualenv": False,
        "has_pyproject_toml": False,
        "has_requirements_txt": False,
    }


def test_prepare_event_properties_override_kwargs(mocker: MockerFixture):
    """If both kwargs and properties supply the same key, properties wins."""
    mocker.patch(
        "reflex.utils.telemetry._get_event_defaults",
        return_value=_make_mock_defaults(),
    )

    event = telemetry._prepare_event(
        "init",
        template="from-kwarg",
        properties={"template": "from-properties"},
    )

    assert event is not None
    props: dict = event["properties"]  # pyright: ignore[reportAssignmentType]
    assert props["template"] == "from-properties"
