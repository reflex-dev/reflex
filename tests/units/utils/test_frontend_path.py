from pathlib import Path
from reflex.utils import prerequisites


def test_frontend_path_resolves_correctly(tmp_path, monkeypatch):
    """Ensure get_web_dir() resolves correctly to the .web directory."""

    # Simulate a Reflex project structure
    project_root = tmp_path / "my_app"
    frontend_dir = project_root / ".web"
    frontend_dir.mkdir(parents=True)

    # Replace REFLEX_WEB_WORKDIR with a mock that returns our test dir
    monkeypatch.setattr(
        prerequisites.environment,
        "REFLEX_WEB_WORKDIR",
        type("FakeVar", (), {"get": lambda _=None: frontend_dir})(),
    )

    # Call actual Reflex logic
    resolved_path = prerequisites.get_web_dir()

    # Verify that it matches expected frontend dir
    assert Path(resolved_path).resolve() == frontend_dir.resolve(), (
        f"Expected {frontend_dir}, got {resolved_path}"
    )
