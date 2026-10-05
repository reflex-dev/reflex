"""Run actual Reflex SQLite migrations with only SQLAlchemy and Alembic."""

import importlib.metadata
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import reflex as rx

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = Path(sys.argv[2])
RESULTS = {
    "modules": {
        name: importlib.util.find_spec(name) is not None
        for name in ("sqlalchemy", "alembic", "sqlmodel", "pydantic")
    },
    "versions": {
        name: importlib.metadata.version(name)
        for name in ("reflex", "reflex-base", "sqlalchemy", "alembic")
    },
    "commands": [],
}
assert RESULTS["modules"] == {
    "sqlalchemy": True,
    "alembic": True,
    "sqlmodel": False,
    "pydantic": False,
}


def run_command(label: str, *args: str) -> str:
    """Execute one isolated CLI command and preserve output.

    Args:
        label: Its evidence name.
        *args: The CLI arguments or Python expression.

    Returns:
        The command's combined output.
    """
    process = subprocess.run(
        [
            "/Users/masenf/.local/bin/uv",
            "run",
            "--no-project",
            "--python",
            sys.executable,
            *args,
        ],
        capture_output=True,
        text=True,
        env={name: value for name, value in os.environ.items() if name != "PYTHONPATH"},
        check=False,
    )
    output = process.stdout + process.stderr
    (OUT / f"db-{label}.log").write_text(output)
    RESULTS["commands"].append({
        "command": list(args[:4]),
        "label": label,
        "returncode": process.returncode,
    })
    assert process.returncode == 0, output
    assert "Traceback" not in output, output
    return output


try:
    shutil.copyfile(SOURCE / "plain_db.py", "plain_db/plain_db.py")
    run_command("init", "reflex", "db", "init")
    connection = sqlite3.connect("plain.sqlite")
    columns = [row[1] for row in connection.execute("pragma table_info(plain_records)")]
    assert columns == ["id", "label"], columns
    connection.close()
    run_command(
        "insert",
        "python",
        "-c",
        "from plain_db.plain_db import Record; from reflex.model import sqla_session; from sqlalchemy import select; session=sqla_session(); session.add(Record(label='persisted alpha row')); session.commit(); rows=session.scalars(select(Record)).all(); assert [(row.id,row.label) for row in rows]==[(1,'persisted alpha row')]; session.close(); print('SQLAlchemy-only Reflex session inserted and selected row')",
    )
    shutil.copyfile(SOURCE / "plain_db_v2.py", "plain_db/plain_db.py")
    run_command(
        "makemigrations",
        "reflex",
        "db",
        "makemigrations",
        "--message",
        "bare sqlalchemy evolve",
    )
    status = run_command("status-before", "reflex", "db", "status")
    assert "bare sqlalchemy evolve" in status
    run_command("migrate", "reflex", "db", "migrate")
    run_command("status-after", "reflex", "db", "status")
    run_command(
        "updated-session",
        "python",
        "-c",
        "from plain_db.plain_db import Record,Note; from reflex.model import sqla_session,ModelRegistry; from sqlalchemy import select; assert set(ModelRegistry.get_metadata().tables)=={'plain_records','plain_notes'}; session=sqla_session(); row=session.scalars(select(Record)).one(); assert (row.id,row.label,row.status)==(1,'persisted alpha row',None); row.status='ready'; session.add(Note(content='second registry')); session.commit(); assert session.scalars(select(Note.content)).one()=='second registry'; session.close(); print('Two bare registries migrated; original row retained; native mapped CRUD passed')",
    )
    connection = sqlite3.connect("plain.sqlite")
    RESULTS["columns_after"] = [
        row[1] for row in connection.execute("pragma table_info(plain_records)")
    ]
    RESULTS["rows_after"] = connection.execute(
        "select id,label,status from plain_records"
    ).fetchall()
    RESULTS["notes_after"] = connection.execute(
        "select id,content from plain_notes"
    ).fetchall()
    assert RESULTS["columns_after"] == ["id", "label", "status"]
    assert RESULTS["rows_after"] == [(1, "persisted alpha row", "ready")]
    assert RESULTS["notes_after"] == [(1, "second registry")]
    connection.close()
    model_error = None
    try:

        class MissingSqlModel(rx.Model, table=True):
            """Trigger the documented guidance while SQLModel remains absent."""

            value: str

    except ImportError as error:
        model_error = str(error)
    assert model_error is not None, "rx.Model unexpectedly declared without SQLModel"
    assert "reflex[db]" in model_error
    RESULTS["rx_model_without_sqlmodel"] = model_error
    RESULTS["status"] = "passed"
finally:
    (OUT / "db-results.json").write_text(json.dumps(RESULTS, indent=2))
