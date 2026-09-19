# Cluster `up_examples_b` — upgrade regression, batch B (db, auth, third-party packages)

Follow `UPGRADE_PROTOCOL.md` (same directory) for each app, in this order:
1. `form-designer` — uses `reflex[db]` + `reflex-local-auth>=0.5.0`: register a user, log in,
   create a form with 2 fields, preview/fill it, log out, log back in; keep the sqlite db across
   the upgrade (alembic migrations must still apply).
2. `twitter` — `reflex[db]`, its own login/registration; post a tweet, follow, view feed; keep
   the db across the upgrade.
3. `basic_crud` — `reflex[db]` + fastapi (mounted API): create/update/delete items via the UI
   AND via the API with curl; check the API still mounts (api_transformer) after the upgrade.
4. `reflexle` — uses `reflex-global-hotkey>=1.2.2`: type letters with the keyboard, submit a
   guess, check the hotkey package still works after the upgrade (it imports internal names —
   grep its installed source for `reflex.` imports and check each still resolves).
5. `data_visualisation` — `reflex[db]` + pandas (psycopg2 not needed: force sqlite via
   `rx.Config(db_url=...)` if the app hardcodes postgres); load the table, add a row, check the
   pandas-backed chart renders (on-demand pandas serializer, #7049).
Third-party import surface: for `reflex-local-auth` and `reflex-global-hotkey`, list every
`from reflex...`/`import reflex...` line in their installed sources and probe each name on
0.9.12a1 in a guarded script — a removed name is a downstream breaking change worth reporting
even if the example app happens not to hit it.
