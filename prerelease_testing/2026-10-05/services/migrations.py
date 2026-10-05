"""Run real migration commands against tables containing existing rows."""

import argparse
import importlib.metadata
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import reflex

UV = os.environ.get("QA_UV") or shutil.which("uv") or "/Users/masenf/.local/bin/uv"
MODEL = '''"""A user app with callable defaults on newly added columns."""
import datetime
import uuid
import reflex as rx
from sqlmodel import Field
from sqlalchemy import UniqueConstraint

class Note(rx.Model, table=True):
    """A note stored in the app database."""
    label: str
{fields}

app = rx.App()
app.add_page(lambda: rx.text("Migration fixture"), route="/")
'''


def command(root: Path, *args: str) -> dict:
    """Invoke the installed database CLI from a disposable app directory.

    Args:
        root: App directory.
        *args: Database command arguments.

    Returns:
        Exit code and output evidence.
    """
    settings = dict(
        os.environ,
        REFLEX_TELEMETRY_ENABLED="false",
        CI="true",
        UV_CACHE_DIR="/private/tmp/reflex-pre-uv-cache",
    )
    settings.pop("PYTHONPATH", None)
    result = subprocess.run(
        [UV, "run", "--no-project", "--python", sys.executable, "reflex", "db", *args],
        cwd=root,
        env=settings,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "args": list(args),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def scenario(root: Path, fields: str, existing_rows: int = 1) -> dict:
    """Initialize, populate, evolve and migrate a real application schema.

    Args:
        root: Fresh fixture directory.
        fields: Newly added model columns.
        existing_rows: Existing records to backfill during migration.

    Returns:
        Generated revision and persisted row evidence.
    """
    root.mkdir()
    package = root / "notes"
    package.mkdir()
    (package / "__init__.py").touch()
    app_source = package / "notes.py"
    app_source.write_text(MODEL.format(fields=""))
    (root / "rxconfig.py").write_text(
        'import reflex as rx\nconfig = rx.Config(app_name="notes", db_url="sqlite:///notes.db")\n'
    )
    commands = [command(root, "init")]
    assert commands[-1]["returncode"] == 0, commands
    with sqlite3.connect(root / "notes.db") as connection:
        connection.executemany(
            "INSERT INTO note(label) VALUES (?)",
            [(f"Existing before migration {index}",) for index in range(existing_rows)],
        )
    app_source.write_text(MODEL.format(fields=fields))
    commands.append(
        command(root, "makemigrations", "--message", "add-callable-defaults")
    )
    if commands[-1]["returncode"]:
        return {"fields": fields, "commands": commands, "success": False}
    commands.append(command(root, "migrate"))
    if commands[-1]["returncode"]:
        return {"fields": fields, "commands": commands, "success": False}
    code = """import reflex as rx
from notes.notes import Note
with rx.session() as session:
    session.add(Note(label="Created through ORM"))
    session.commit()
"""
    orm = subprocess.run(
        [UV, "run", "--no-project", "--python", sys.executable, "python", "-c", code],
        cwd=root,
        env=dict(
            os.environ,
            CI="true",
            REFLEX_TELEMETRY_ENABLED="false",
            UV_CACHE_DIR="/private/tmp/reflex-pre-uv-cache",
        ),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert orm.returncode == 0, orm.stderr
    with sqlite3.connect(root / "notes.db") as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute("SELECT * FROM note")]
        connection.execute(
            "INSERT INTO note(label) VALUES (?)", ("Created after migration",)
        )
        rows_after = [dict(row) for row in connection.execute("SELECT * FROM note")]
    revisions = {
        path.name: path.read_text() for path in (root / "alembic/versions").glob("*.py")
    }
    return {
        "fields": fields,
        "commands": commands,
        "success": True,
        "orm_insert": {
            "returncode": orm.returncode,
            "stdout": orm.stdout,
            "stderr": orm.stderr,
        },
        "rows": rows,
        "rows_after": rows_after,
        "revisions": revisions,
    }


def main() -> None:
    """Compare schema evolution involving timestamp, UUID and scalar defaults."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--unique",
        action="store_true",
        help="Explore callable UUID defaults on a unique column with existing rows.",
    )
    args = parser.parse_args()
    assert Path(reflex.__file__).is_relative_to(Path(sys.prefix)), reflex.__file__
    with tempfile.TemporaryDirectory(prefix="reflex-migrations-") as scratch:
        root = Path(scratch)
        result = {
            "python": sys.executable,
            "reflex": reflex.__file__,
            "version": importlib.metadata.version("reflex"),
            "cases": [
                scenario(
                    root / "uuid-unique",
                    "    uid: uuid.UUID = Field(default_factory=uuid.uuid4)\n    __table_args__ = (UniqueConstraint('uid', name='uq_note_uid'),)",
                    existing_rows=2,
                )
            ]
            if args.unique
            else [
                scenario(
                    root / "datetime",
                    "    created: datetime.datetime = Field(default_factory=datetime.datetime.now)\n    score: int = Field(default=7)",
                ),
                scenario(
                    root / "uuid",
                    "    uid: uuid.UUID = Field(default_factory=uuid.uuid4)",
                ),
            ],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "version": result["version"],
                "successes": [case["success"] for case in result["cases"]],
            }
        )
    )


if __name__ == "__main__":
    main()
