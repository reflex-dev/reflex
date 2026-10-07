"""Probe how a plain `datetime` SQLModel field round-trips across the sqlmodel versions a
reflex[db] user meets during the 0.9.12 -> 0.10.0a1 upgrade (0.9.12 resolves sqlmodel
0.0.47; reflex[db]==0.10.0a1 caps sqlmodel<0.0.45, i.e. 0.0.44).

Usage: <venv>/bin/python sqlmodel_datetime_probe.py <expect_venv_substring> <db_path> write|read
"""
import sys
from datetime import datetime, timezone

import sqlmodel
from sqlmodel import Field, Session, SQLModel, create_engine, select

assert sys.argv[1] in sys.executable, sys.executable
DB, MODE = sys.argv[2], sys.argv[3]


class Visit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    label: str
    at: datetime


engine = create_engine(f"sqlite:///{DB}")
print("sqlmodel", sqlmodel.__version__, "column type:", repr(Visit.__table__.c.at.type))
if MODE == "write":
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Visit(label=f"aware-utc@{sqlmodel.__version__}", at=datetime(2026, 10, 6, 17, 0, tzinfo=timezone.utc)))
        s.commit()
    try:
        with Session(engine) as s:
            s.add(Visit(label=f"naive@{sqlmodel.__version__}", at=datetime(2026, 10, 6, 17, 0)))
            s.commit()
        print("naive write: accepted")
    except Exception as e:  # noqa: BLE001
        print("naive write: REJECTED ->", type(e).__name__, str(e).splitlines()[0][:160])
with Session(engine) as s:
    for v in s.exec(select(Visit)).all():
        try:
            cmp = v.at < datetime.now(timezone.utc)
            cmp_s = f"compare-with-aware-now OK ({cmp})"
        except TypeError as e:
            cmp_s = f"compare-with-aware-now TypeError: {e}"
        print(f"read {v.label:28} -> {v.at!r} isoformat={v.at.isoformat()} | {cmp_s}")
import sqlite3  # noqa: E402
print("raw sqlite:", sqlite3.connect(DB).execute("select label, at from visit").fetchall())
