"""Cold-process compatibility regressions for optional serializers."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_script(
    script: str,
    *,
    cwd: Path | None = None,
    timeout: int = 15,
) -> None:
    """Run an isolated script and report its captured failure output.

    Args:
        script: The Python source to execute in a fresh interpreter.
        cwd: The working directory for a temporary application fixture.
        timeout: The maximum subprocess lifetime in seconds.
    """
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=cwd,
        env={**os.environ, "REFLEX_TELEMETRY_ENABLED": "false"},
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("custom_type", [None, "SQLModel", "Team", "object"])
@pytest.mark.parametrize("compatibility_import", [False, True])
def test_sqlmodel_relationships_from_cold_state(
    custom_type: str | None, compatibility_import: bool
) -> None:
    """Direct SQLModel usage preserves queried relationships and overrides.

    Args:
        custom_type: The model type to override, or None to use the default.
        compatibility_import: Whether to import the historical public serializer.
    """
    pytest.importorskip("sqlmodel")
    if compatibility_import:
        pytest.importorskip("alembic")
    script = """
import json
import pickle
import reflex as rx
from typing import Any, get_type_hints
from sqlalchemy.orm import selectinload
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select
from reflex_base.utils import serializers
from reflex_base.utils.format import json_dumps

class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    heroes: list["Hero"] = Relationship()

class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    team_id: int | None = Field(default=None, foreign_key="team.id")

engine = create_engine("sqlite://")
SQLModel.metadata.create_all(engine)
with Session(engine) as session:
    session.add(Team(id=1, name="Avengers", heroes=[Hero(id=2, name="Thor", team_id=1)]))
    session.commit()
    teams = list(session.exec(select(Team).options(selectinload(Team.heroes))))

CUSTOM_REGISTRATION

if COMPATIBILITY_IMPORT:
    from reflex.model import serialize_sqlmodel
    assert serialize_sqlmodel(m=teams[0])["heroes"][0].name == "Thor"
    assert get_type_hints(serialize_sqlmodel)["m"] is SQLModel
    assert get_type_hints(serialize_sqlmodel)["return"] == dict[str, Any]
    assert pickle.loads(pickle.dumps(serialize_sqlmodel)) is serialize_sqlmodel
    assert pickle.loads(b"creflex.model\\nserialize_sqlmodel\\n.") is serialize_sqlmodel

app = rx.App()

class State(rx.State):
    teams: list[Team] = []

    @rx.event
    def load(self):
        self.teams = teams

state = State(_reflex_internal_init=True)
State.load.fn(state)
payload = json_dumps(state.get_delta())
assert "Thor" in payload, "loaded SQLModel relationship missing from state delta"
assert "Avengers" in payload
if CUSTOM_ENABLED:
    assert serializers.get_serializer(Team) is custom
    assert '"custom":true' in payload.replace(" ", "")
else:
    assert serializers.get_serializer_type(Team) == dict[str, Any]
json.loads(payload)
engine.dispose()
"""
    custom_registration = (
        """
@rx.serializer(overwrite=True)
def custom(value: CUSTOM_TYPE) -> dict:
    return {
        **value.model_dump(),
        "heroes": [hero.name for hero in value.heroes],
        "custom": True,
    }
""".replace("CUSTOM_TYPE", custom_type)
        if custom_type
        else ""
    )
    _run_script(
        script
        .replace("CUSTOM_REGISTRATION", custom_registration)
        .replace("COMPATIBILITY_IMPORT", repr(compatibility_import))
        .replace("CUSTOM_ENABLED", repr(custom_type is not None)),
        timeout=30,
    )


def test_custom_serializer_in_optional_dependency_namespace(tmp_path: Path) -> None:
    """A user package named pandas must support its own serialized classes.

    Args:
        tmp_path: The isolated directory containing the user package.
    """
    package = tmp_path / "pandas"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "application.py").write_text(
        """
import reflex as rx

class Label:
    def __init__(self, text="Ready"):
        self.text = text

@rx.serializer
def serialize_label(value: Label) -> str:
    return value.text

class State(rx.State):
    label: Label = Label()

    @rx.event
    def update(self):
        self.label = Label("Updated")
"""
    )
    _run_script(
        """
from pandas.application import State
from reflex_base.utils.format import json_dumps

state = State(_reflex_internal_init=True)
State.update.fn(state)
assert "Updated" in json_dumps(state.get_delta())
""",
        cwd=tmp_path,
    )


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires fork")
@pytest.mark.parametrize(
    ("operation", "import_target"),
    [
        ("lookup", "plotly.graph_objs.layout._template"),
        ("serialize", "plotly.io._json"),
        ("serialize", "orjson"),
    ],
)
def test_optional_lookup_after_fork_during_import(
    operation: str, import_target: str
) -> None:
    """Optional serializer use cannot strand an import lock in a forked child.

    Args:
        operation: Whether to resolve a serializer or serialize a real figure.
        import_target: The dependency whose initial import overlaps the fork.
    """
    pytest.importorskip("plotly")
    if import_target == "orjson":
        pytest.importorskip("orjson")
    _run_script(
        """
import importlib.abc
import importlib.machinery
import os
import select
import signal
import sys
import threading
import warnings

entered = threading.Event()
release = threading.Event()

class PauseLoader(importlib.abc.Loader):
    def __init__(self, inner):
        self.inner = inner

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        if threading.current_thread().name == "optional-first-use":
            entered.set()
            assert release.wait(10)
        self.inner.exec_module(module)

class PauseFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == IMPORT_TARGET:
            spec = importlib.machinery.PathFinder.find_spec(name, path, target)
            spec.loader = PauseLoader(spec.loader)
            return spec

sys.meta_path.insert(0, PauseFinder())
from reflex_base.utils import serializers
from plotly.graph_objects import Figure

figure = Figure() if OPERATION == "serialize" else None
errors = []

def use_serializer():
    if OPERATION == "serialize":
        result = serializers.serialize(figure)
        assert isinstance(result, dict)
        assert "data" in result
    else:
        assert serializers.get_serializer(Figure) is serializers.serialize_figure

def first_use():
    try:
        use_serializer()
    except Exception as error:
        errors.append(str(error))

thread = threading.Thread(target=first_use, name="optional-first-use", daemon=True)
thread.start()
# Implementations that do not import Template need not reach the pause.
entered.wait(0.5)
read_fd, write_fd = os.pipe()
# A pre-fork synchronization hook may wait for the active import to finish.
timer = threading.Timer(0.5, release.set)
timer.start()
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    pid = os.fork()
if pid == 0:
    os.close(read_fd)
    use_serializer()
    os.write(write_fd, b"OK")
    os._exit(0)

os.close(write_fd)
try:
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert not errors, errors
    ready, _, _ = select.select([read_fd], [], [], 3)
    assert ready, "forked child hung during optional serializer lookup"
    assert os.read(read_fd, 2) == b"OK"
finally:
    release.set()
    timer.join(5)
    os.close(read_fd)
    finished, _ = os.waitpid(pid, os.WNOHANG)
    if not finished:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
""".replace("OPERATION", repr(operation)).replace("IMPORT_TARGET", repr(import_target)),
        timeout=30,
    )


def test_custom_metaclass_import_does_not_deadlock_registration() -> None:
    """An import from a type hash can coexist with a lookup in that import."""
    _run_script(
        """
import importlib.abc
import importlib.util
import os
import sys
import threading
from reflex_base.utils import serializers

module_entered = threading.Event()
hash_entered = threading.Event()
errors = []

class Loader(importlib.abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module_entered.set()
        assert hash_entered.wait(5)
        serializers.get_serializer(int)
        module.done = True

class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "serializer_held_import":
            return importlib.util.spec_from_loader(name, Loader())

sys.meta_path.insert(0, Finder())

class Meta(type):
    def __hash__(cls):
        hash_entered.set()
        import serializer_held_import
        return type.__hash__(cls)

class Target(metaclass=Meta):
    pass

def custom(value: Target) -> str:
    return "custom"

def run(action):
    try:
        action()
    except Exception as error:
        errors.append(str(error))

importer = threading.Thread(target=run, args=(lambda: __import__("serializer_held_import"),), daemon=True)
importer.start()
assert module_entered.wait(5)
registrar = threading.Thread(target=run, args=(lambda: serializers.serializer(custom),), daemon=True)
registrar.start()
registrar.join(3)
importer.join(0.5)
if registrar.is_alive() or importer.is_alive():
    print("serializer registration deadlocked with an import", flush=True)
    os._exit(1)
assert not errors, errors
assert serializers.serialize(Target()) == "custom"
"""
    )


@pytest.mark.parametrize("raising_hash_call", [2, 4])
def test_optional_lookup_hash_failure_preserves_unrelated_serializers(
    raising_hash_call: int,
) -> None:
    """A user type hash failure cannot remove unrelated serialization behavior.

    Args:
        raising_hash_call: The hash invocation that raises during optional lookup.
    """
    pytest.importorskip("pandas")
    _run_script(
        """
from reflex_base.utils import serializers
from pandas import DataFrame

armed = False

class Meta(type):
    calls = 0

    def __hash__(cls):
        if armed:
            Meta.calls += 1
            if Meta.calls == RAISING_HASH_CALL:
                raise RuntimeError("custom metaclass hash failed")
        return type.__hash__(cls)

class Fragile(metaclass=Meta):
    pass

class Stable:
    pass

@serializers.serializer
def fragile(value: Fragile) -> str:
    return "fragile"

@serializers.serializer
def stable(value: Stable) -> str:
    return "stable"

armed = True
try:
    serializers.get_serializer(DataFrame)
except RuntimeError:
    pass
finally:
    armed = False

assert serializers.serialize(Stable()) == "stable"
assert serializers.get_serializer_type(Stable) is str
""".replace("RAISING_HASH_CALL", str(raising_hash_call))
    )


def test_reentrant_plugin_serializer_registration_survives_optional_lookup() -> None:
    """Importing a serializer plugin from a type hash preserves its registration."""
    pytest.importorskip("pandas")
    _run_script(
        """
import importlib.abc
import importlib.util
import sys
from reflex_base.utils import serializers
from pandas import DataFrame

armed = False

class Late:
    pass

def late(value: Late) -> str:
    return "late"

class Loader(importlib.abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        serializers.serializer(late)
        module.done = True

class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "serializer_plugin":
            return importlib.util.spec_from_loader(name, Loader())

sys.meta_path.insert(0, Finder())

class Meta(type):
    def __hash__(cls):
        if armed:
            import serializer_plugin
        return type.__hash__(cls)

class Trigger(metaclass=Meta):
    pass

@serializers.serializer
def trigger(value: Trigger) -> str:
    return "trigger"

armed = True
serializers.get_serializer(DataFrame)
# A lookup that does not touch unrelated hashes may leave the plugin unloaded.
import serializer_plugin
assert serializers.serialize(Late()) == "late"
assert serializers.get_serializer_type(Late) is str
"""
    )
