"""#7440: reflex WITHOUT the db extra + sqlmodel/sqlalchemy WITHOUT greenlet.

Expected on 0.10.1a1: `import reflex.model`, `rx.Model`, `rx.session` (sync create/insert/select) work;
`rx.asession` / `get_async_engine` raise a helpful ImportError. On 0.10.0 `import reflex.model` itself fails.
Usage: <venv>/bin/python -I nogreenlet_probe.py <venv-name>   (run from a neutral cwd with a config-less dir)
"""

import importlib.metadata as md
import json
import os
import sys
import tempfile
import traceback

EXPECT = sys.argv[1]
os.environ.setdefault("REFLEX_TELEMETRY_ENABLED", "false")
work = tempfile.mkdtemp(prefix="nogreenlet-")
os.chdir(work)
out = {"venv": EXPECT, "steps": {}}


def step(name, fn):
    try:
        out["steps"][name] = {"ok": True, "result": fn()}
    except BaseException as e:  # noqa: BLE001
        out["steps"][name] = {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "tb_tail": traceback.format_exc().strip().splitlines()[-3:],
        }


def versions():
    v = {}
    for d in ("reflex", "reflex-base", "sqlalchemy", "sqlmodel", "greenlet", "alembic"):
        try:
            v[d] = md.version(d)
        except md.PackageNotFoundError:
            v[d] = None
    return v


out["versions"] = versions()
assert out["versions"]["greenlet"] is None, "greenlet must NOT be installed for this probe"

import reflex as rx  # noqa: E402

assert f"/envs/{EXPECT}/" in rx.__file__, rx.__file__


def import_model():
    import reflex.model as m

    return [n for n in ("Model", "session", "asession", "get_engine", "get_async_engine") if hasattr(m, n)]


step("import reflex.model", import_model)


def define_model():
    class Note(rx.Model, table=True):
        text: str

    out["Note"] = Note
    return Note.__tablename__


step("rx.Model subclass", define_model)


def sync_session():
    from reflex_base.config import get_config

    # sqlite file in the temp dir; rx.session needs the db_url from config
    cfg = get_config()
    cfg.db_url = f"sqlite:///{work}/probe.db"
    Note = out["Note"]
    import sqlmodel

    rx.Model.create_all()
    with rx.session() as s:
        s.add(Note(text="hello"))
        s.commit()
    with rx.session() as s:
        rows = s.exec(sqlmodel.select(Note)).all()
    return [r.text for r in rows]


step("rx.session create/insert/select", sync_session)


def async_session():
    import asyncio

    async def go():
        async with rx.asession() as s:
            return str(s)

    return asyncio.run(go())


step("rx.asession (expect helpful ImportError)", async_session)


def async_engine():
    from reflex.model import get_async_engine

    return str(get_async_engine(None))


step("get_async_engine (expect ImportError)", async_engine)
out.pop("Note", None)
print(json.dumps(out, indent=1, default=str))
