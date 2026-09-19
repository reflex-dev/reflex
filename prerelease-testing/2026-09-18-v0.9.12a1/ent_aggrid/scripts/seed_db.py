"""Seed the ag_grid demo sqlite DB with fake Friend rows (demo ships an empty DB)."""

import sys

sys.path.insert(0, ".")
import sqlite3

import faker

fake = faker.Faker()
con = sqlite3.connect("reflex.db")
cur = con.cursor()
cur.execute("select count(*) from friend")
print("existing rows:", cur.fetchone()[0])
rows = []
for _ in range(int(sys.argv[1]) if len(sys.argv) > 1 else 200):
    age = fake.random_int(min=18, max=80)
    yk = fake.random_int(min=0, max=age)
    rows.append(
        (
            fake.name(),
            age,
            yk,
            int(fake.pybool(20)),
            int(fake.pybool(60)),
            int(fake.pybool(30)),
            fake.date_time_between(start_date=f"-{yk + 1}y", end_date=f"-{yk}y").isoformat(sep=" "),
        )
    )
cur.executemany(
    "insert into friend (name, age, years_known, owes_me, has_a_dog, spouse_is_annoying, met)"
    " values (?,?,?,?,?,?,?)",
    rows,
)
con.commit()
cur.execute("select count(*) from friend")
print("rows now:", cur.fetchone()[0])
con.close()
