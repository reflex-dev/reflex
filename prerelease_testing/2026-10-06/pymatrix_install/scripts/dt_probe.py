"""Probe how an rx.Model datetime column stores/returns naive and aware values.

Usage: <venv>/bin/python dt_probe.py <expected-venv-substring> <workdir>
"""
import datetime as dt
import json
import os
import sys

import importlib.metadata as _md

import reflex as rx

assert sys.argv[1] in rx.__file__, rx.__file__
os.chdir(sys.argv[2])
import sqlalchemy
import sqlmodel

DB = os.path.join(sys.argv[2], f"probe-{_md.version("reflex")}.db")
if os.path.exists(DB):
    os.remove(DB)
engine = sqlalchemy.create_engine(f"sqlite:///{DB}")


class Event(rx.Model, table=True):
    """A row with a datetime column."""

    label: str
    at: dt.datetime


rx.Model.metadata.create_all(engine)
out = {
    "reflex": _md.version("reflex"),
    "sqlmodel": sqlmodel.__version__,
    "python": sys.version.split()[0],
    "column_type": repr(Event.__table__.c.at.type),
    "rows": [],
}
plus2 = dt.timezone(dt.timedelta(hours=2))
values = {
    "naive": dt.datetime(2026, 10, 6, 12, 0, 0),
    "aware_utc": dt.datetime(2026, 10, 6, 12, 0, 0, tzinfo=dt.timezone.utc),
    "aware_plus2": dt.datetime(2026, 10, 6, 12, 0, 0, tzinfo=plus2),
}
for label, value in values.items():
    rec = {"label": label, "input": value.isoformat()}
    try:
        with sqlmodel.Session(engine) as s:
            s.add(Event(label=label, at=value))
            s.commit()
        rec["insert"] = "ok"
    except Exception as e:  # noqa: BLE001
        rec["insert"] = f"{type(e).__name__}: {str(e).splitlines()[0][:160]}"
    out["rows"].append(rec)
with sqlmodel.Session(engine) as s:
    for row in s.exec(sqlmodel.select(Event)).all():
        for rec in out["rows"]:
            if rec["label"] == row.label:
                rec["read_back"] = row.at.isoformat()
                rec["read_back_tz"] = str(row.at.tzinfo)
with engine.connect() as c:
    for label, raw in c.execute(sqlalchemy.text("select label, at from event")):
        for rec in out["rows"]:
            if rec["label"] == label:
                rec["raw_sqlite"] = raw
# query-filter with naive vs aware parameter
for label, value in (("naive_filter", values["naive"]), ("aware_filter", values["aware_utc"])):
    try:
        with sqlmodel.Session(engine) as s:
            n = len(s.exec(sqlmodel.select(Event).where(Event.at == value)).all())
        out[label] = f"ok matches={n}"
    except Exception as e:  # noqa: BLE001
        out[label] = f"{type(e).__name__}: {str(e).splitlines()[0][:160]}"
# serialization through reflex (state var / JSON) of the read-back value
from reflex_base.utils.format import json_dumps

with sqlmodel.Session(engine) as s:
    first = s.exec(sqlmodel.select(Event)).first()
    out["reflex_json_dumps_model"] = json_dumps(first) if first else None
print(json.dumps(out, indent=1))
