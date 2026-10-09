"""Dump table row counts + alembic head + a content digest of a sqlite DB (read-only).
Usage: dbdump.py <db> [--rows]"""
import hashlib
import sqlite3
import sys

db = sys.argv[1]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()
tabs = [r[0] for r in cur.execute("select name from sqlite_master where type='table' order by name")]
for t in tabs:
    n = cur.execute(f'select count(*) from "{t}"').fetchone()[0]
    h = hashlib.sha256(repr(cur.execute(f'select * from "{t}" order by 1').fetchall()).encode()).hexdigest()[:12]
    print(f"{t}\trows={n}\tdigest={h}")
    if "--rows" in sys.argv and t != "alembic_version":
        for r in cur.execute(f'select * from "{t}" order by 1 limit 20'):
            print("   ", repr(r)[:200])
print("alembic_version:", cur.execute("select * from alembic_version").fetchall() if "alembic_version" in tabs else None)
