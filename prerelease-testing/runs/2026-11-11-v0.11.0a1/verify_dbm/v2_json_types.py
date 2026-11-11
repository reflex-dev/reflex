"""v2: JSON column typing on DeclarativeBase vs rx.Model. Usage: <venv>/bin/python -I v2_json_types.py <venv-path>."""
import sys

import reflex

assert sys.argv[1] in reflex.__file__, reflex.__file__
import reflex as rx
import sqlmodel
from sqlalchemy import JSON, Column, String
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class Plain(DeclarativeBase):  # non-dataclass declarative base
    pass


class M(Base):
    __tablename__ = "m"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    d: Mapped[dict] = mapped_column(JSON, default_factory=dict)
    dn: Mapped[dict | None] = mapped_column(JSON, default=None)
    l: Mapped[list[str]] = mapped_column(JSON, default_factory=list)
    s: Mapped[str] = mapped_column(String(10), default="x")


class P(Plain):
    __tablename__ = "p"
    id: Mapped[int] = mapped_column(primary_key=True)
    d: Mapped[dict] = mapped_column(JSON)


class R(rx.Model, table=True):
    d: dict = sqlmodel.Field(default_factory=dict, sa_column=Column(JSON))


class S(rx.State):
    m: M | None = None
    mm: M = M()
    if "--no-plain" not in sys.argv:
        p: P | None = None
    r: R | None = None


SKIP = "--no-plain" in sys.argv
for expr in ["S.mm.d", "S.mm.l", "S.mm.s", "S.m.d", "S.m.dn", "S.p.d", "S.r.d"]:
    if SKIP and expr.startswith("S.p"):
        continue
    print(f"{expr:10} type={eval(expr)._var_type}")
for expr in ["S.mm.d['city']", "S.m.d['city']", "S.mm.l[0]", "S.p.d['city']", "S.r.d['city']", "S.m.d.to(dict)['city']"]:
    if SKIP and expr.startswith("S.p"):
        continue
    try:
        print(f"{expr:24} -> OK {eval(expr)}")
    except Exception as e:
        print(f"{expr:24} -> ERR {type(e).__name__}: {e}")
