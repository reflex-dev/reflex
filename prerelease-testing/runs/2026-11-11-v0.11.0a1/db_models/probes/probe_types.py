import sys
import reflex
assert sys.argv[1] in reflex.__file__, reflex.__file__
import reflex as rx
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class M(Base):
    __tablename__ = "m"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    d1: Mapped[dict] = mapped_column(JSON, default_factory=dict)
    d2: Mapped[dict | None] = mapped_column(JSON, default=None)
    d3: Mapped[dict[str, str] | None] = mapped_column(JSON, default=None)
    s: Mapped[str | None] = mapped_column(default=None)


class S(rx.State):
    m: M | None = None
    ms: list[M] = []
    plain: dict | None = None


for name in ["d1", "d2", "d3", "s"]:
    v = getattr(S.m, name)
    print(name, v._var_type, type(v).__name__)
for expr in ["S.m.d1['city']", "S.m.d2['city']", "S.m.d3['city']", "S.plain['city']"]:
    try:
        print(expr, "->", eval(expr))
    except Exception as e:
        print(expr, "-> ERR", type(e).__name__, e)
