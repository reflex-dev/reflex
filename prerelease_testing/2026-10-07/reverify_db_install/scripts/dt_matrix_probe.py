"""Datetime round-trip matrix across sqlmodel 0.0.47 (reflex[db]==0.9.12 today) and 0.0.44 (reflex[db]==0.10.0a1).

Usage: <venv>/bin/python -I dt_matrix_probe.py <expect_venv_substring> <db_path> write|read

Three tables, each written with three values that are the SAME instant or wall time:
  plain  : SQLModel `at: datetime`                       (sqlmodel decides the column type)
  rxplain: rx.Model `created_at: datetime`               (what a typical reflex app declares)
  rxtz   : rx.Model `created_at` with sa_column=Column(DateTime(timezone=True))  (explicit type)
values: aware UTC 17:00Z, aware +02:00 19:00 (== 17:00Z), naive 17:00.
"""
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import reflex as rx
import sqlalchemy
import sqlmodel
from reflex_base.utils.serializers import serialize
from sqlmodel import Column, DateTime, Field, Session, SQLModel, create_engine, select

assert sys.argv[1] in sys.executable, sys.executable
assert sys.argv[1] in rx.__file__, rx.__file__
DB, MODE = sys.argv[2], sys.argv[3]
TAG = f"reflex {rx.__version__ if hasattr(rx, '__version__') else '?'} / sqlmodel {sqlmodel.__version__}"
try:
    from importlib.metadata import version

    TAG = f"reflex {version('reflex')} / sqlmodel {version('sqlmodel')} / pydantic {version('pydantic')}"
except Exception:  # noqa: BLE001
    pass


class Plain(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    label: str
    at: datetime


class RxPlain(rx.Model, table=True):
    label: str
    created_at: datetime


class RxTz(rx.Model, table=True):
    label: str
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))


TABLES = [(Plain, "at"), (RxPlain, "created_at"), (RxTz, "created_at")]
VALUES = {
    "awareUTC": datetime(2026, 10, 6, 17, 0, tzinfo=timezone.utc),
    "aware+02": datetime(2026, 10, 6, 19, 0, tzinfo=timezone(timedelta(hours=2))),
    "naive": datetime(2026, 10, 6, 17, 0),
}
engine = create_engine(f"sqlite:///{DB}")
print(f"### {MODE} with {TAG}")
for model, col in TABLES:
    print(f"  {model.__tablename__:8} column type: {model.__table__.c[col].type!r}")

if MODE == "write":
    SQLModel.metadata.create_all(engine)
    for model, col in TABLES:
        for name, value in VALUES.items():
            label = f"{name}@{sqlmodel.__version__}"
            try:
                with Session(engine) as s:
                    s.add(model(label=label, **{col: value}))
                    s.commit()
                print(f"  write {model.__tablename__:8} {label:16}: accepted")
            except Exception as e:  # noqa: BLE001
                print(f"  write {model.__tablename__:8} {label:16}: REJECTED {type(e).__name__}: {str(e).splitlines()[0][:110]}")

raw = sqlite3.connect(DB)
for model, col in TABLES:
    with Session(engine) as s:
        rows = s.exec(select(model).order_by(model.id)).all()
    rawrows = dict(
        (r[0], r[1:])
        for r in raw.execute(f"select label, typeof({col}), {col}, hex({col}) from {model.__tablename__}")
    )
    for row in rows:
        v = getattr(row, col)
        kind = "AWARE" if v.utcoffset() is not None else "naive"
        try:
            cmp = f"OK({v < datetime.now(timezone.utc)})"
        except TypeError as e:
            cmp = f"TypeError({e})"
        try:
            cmpn = f"OK({v < datetime.now()})"
        except TypeError:
            cmpn = "TypeError"
        t, stored, hx = rawrows[row.label]
        print(
            f"  read {model.__tablename__:8} {row.label:16} -> {kind:5} {v.isoformat():26} serialize()={serialize(v)!r:28}"
            f" | < aware now: {cmp} | < naive now: {cmpn} | sqlite {t} {stored!r}"
        )
# filter on the column with an aware bound, as an app would (`where(created_at > now - 1d)`)
cut = datetime(2026, 10, 6, 0, 0, tzinfo=timezone.utc)
for model, col in TABLES:
    try:
        with Session(engine) as s:
            n = len(s.exec(select(model).where(getattr(model, col) > cut)).all())
        print(f"  where {model.__tablename__:8} {col} > aware 2026-10-06T00:00Z -> {n} rows")
    except Exception as e:  # noqa: BLE001
        print(f"  where {model.__tablename__:8} {col} > aware cutoff -> {type(e).__name__}: {str(e).splitlines()[0][:110]}")
    try:
        with Session(engine) as s:
            n = len(s.exec(select(model).where(getattr(model, col) > cut.replace(tzinfo=None))).all())
        print(f"  where {model.__tablename__:8} {col} > naive 2026-10-06T00:00  -> {n} rows")
    except Exception as e:  # noqa: BLE001
        print(f"  where {model.__tablename__:8} {col} > naive cutoff -> {type(e).__name__}: {str(e).splitlines()[0][:110]}")
