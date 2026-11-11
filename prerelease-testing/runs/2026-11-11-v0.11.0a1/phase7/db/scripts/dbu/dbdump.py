"""dbdump.py <db> [seed]: print per-table row count + content digest (stdlib sqlite3 only). seed inserts QA rows."""
import hashlib
import sqlite3
import sys

con = sqlite3.connect(sys.argv[1])
if len(sys.argv) > 2 and sys.argv[2] == "seed":
    con.execute("insert into localuser (username, password_hash, enabled) values ('qa_verifier', x'00', 1)")
    uid = con.execute("select id from localuser where username='qa_verifier'").fetchone()[0]
    con.execute("insert into form (name, owner_id) values ('QA Verify Form', ?)", (uid,))
    fid = con.execute("select max(id) from form").fetchone()[0]
    con.execute("insert into field (name, type_, required, prompt, form_id) values ('qa_field', 'text', 0, 'QA prompt survives upgrade', ?)", (fid,))
    con.execute("insert into response (client_token, form_id, hidden) values ('tok', ?, 0)", (fid,))
    con.commit()
for (t,) in con.execute("select name from sqlite_master where type='table' order by name"):
    rows = con.execute(f'select * from "{t}" order by 1').fetchall()
    cols = [r[1] for r in con.execute(f'pragma table_info("{t}")')]
    print(f"{t}: rows={len(rows)} cols={len(cols)} digest={hashlib.sha256(repr((cols, rows)).encode()).hexdigest()[:12]}")
