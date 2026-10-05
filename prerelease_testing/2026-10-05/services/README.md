# Redis pools, duration configuration and migrations

`probe.py` uses the installed framework and a real disposable Redis service on
localhost:9141. All eight duration/configuration scenarios and the pool checks
pass. Unit suffixes, bare seconds, deprecated millisecond/second names, and new
name precedence retain the expected values. Deprecation messages point to the
real script. A cap of three handles 100 simultaneous pings; a blocked request
recovers when a held connection is released, and a full pool times out after
about 0.20 seconds for `200ms`. Invalid caps/wait times fail clearly.

`migrations.py` drives the public `reflex db` CLI in disposable SQLite apps. It
creates an existing row, adds datetime or UUID callable-default columns, runs
makemigrations/migrate, and inserts new rows through both the ORM and raw SQL.
Both alpha cases pass. Both previous-stable cases fail with the original
`CompileError`; see `migrations-{alpha,stable}.json` for commands and revisions.
ORM-created UUIDs remain fresh. A generated SQL server default is a constant
evaluated during migration generation, as the changelog describes; subsequent
raw SQL inserts use that constant.

`migrations.py --unique` additionally tries a named unique UUID constraint with
two existing rows. Alpha generates the migration but applying it fails with a
UNIQUE constraint error because the backfill is one constant UUID for both
rows. Stable fails earlier with CompileError. This remaining factory/backfill
limit is tracked as finding 10. The first unnamed variant failed SQLite's
constraint-name requirement; separate evidence preserves that observation,
while the named constraint isolates the default behavior. No library or
generated migration was patched.

Rerun from a neutral app directory copied from this folder, with a published
PyPI venv and Redis already listening on 9141:

```sh
uv --no-config run --no-project --python <venv>/bin/python python /absolute/path/to/services/probe.py --output /private/tmp/services.json
uv --no-config run --no-project --python <venv>/bin/python python /absolute/path/to/services/migrations.py --output /private/tmp/migrations.json
```

The migration runner needs the published `reflex[db]` extra in each compared
venv. It owns its temporary schema and never modifies a repository database.
The independent [Redis app campaign](../core_state/redis/README.md) additionally
covers actual state recovery, ComponentState, background changes, and lock
notifications. PostgreSQL dialects and sustained load were not measured.
