The `db` extra now installs `aiosqlite`, the async SQLite driver, so `reflex[db]` works with SQLAlchemy's async engine and sessions on the default SQLite database without a separate install.
