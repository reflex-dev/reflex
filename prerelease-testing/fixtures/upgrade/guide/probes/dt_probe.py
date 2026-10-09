"""docs/database/tables.md "Datetimes and SQLModel upgrades" samples on the installed sqlmodel (sqlite in memory).

Usage: <venv>/bin/python dt_probe.py <expected-venv-name>
"""

import sys
from datetime import datetime, timezone
from importlib.metadata import version

import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
import sqlmodel  # noqa: E402
from pydantic import NaiveDatetime  # noqa: E402
from sqlalchemy import DateTime  # noqa: E402
from sqlmodel import Field, Session, SQLModel, create_engine, select  # noqa: E402

print(f"reflex {version('reflex')} sqlmodel {version('sqlmodel')} sqlalchemy {version('sqlalchemy')}")


class Post(rx.Model, table=True):  # the documented sample, verbatim
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_type=DateTime(timezone=False),
    )


class PlainPost(rx.Model, table=True):
    created_at: datetime


class NaivePost(rx.Model, table=True):
    created_at: NaiveDatetime


eng = create_engine("sqlite://")
SQLModel.metadata.create_all(eng)


def t(label, fn):
    try:
        print(f"{label:70} -> {fn()!r}"[:300])
    except Exception as e:  # noqa: BLE001
        print(f"{label:70} -> EXC {type(e).__name__}: {str(e)[:200]}")


def ins_read(model, value):
    with Session(eng) as s:
        s.add(model(created_at=value))
        s.commit()
    with Session(eng) as s:
        row = s.exec(select(model).order_by(model.id.desc())).first()
        return row.created_at, row.created_at.tzinfo


naive = datetime(2026, 10, 7, 12, 0, 0)
aware = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
t("sa_type=DateTime(timezone=False): naive insert/read", lambda: ins_read(Post, naive))
t("sa_type=DateTime(timezone=False): default_factory=datetime.now (no value given)", lambda: (lambda s: (s.add(Post()), s.commit(), s.exec(select(Post).order_by(Post.id.desc())).first().created_at.tzinfo)[2])(Session(eng)))
t("plain datetime: naive insert  [docs: rejected on >=0.0.45]", lambda: ins_read(PlainPost, naive))
t("plain datetime: aware insert/read  [docs: UTC-aware back]", lambda: ins_read(PlainPost, aware))
t("plain datetime: read-back compared with datetime.now()  [docs: TypeError]", lambda: ins_read(PlainPost, aware)[0] < datetime.now())
t("NaiveDatetime: naive insert/read  [docs: naive storage]", lambda: ins_read(NaivePost, naive))
t("type of PlainPost.created_at column", lambda: repr(PlainPost.__table__.c.created_at.type))
