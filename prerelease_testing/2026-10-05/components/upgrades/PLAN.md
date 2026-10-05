# Existing application upgrade checks

Upstream: `reflex-dev/reflex-examples`, commit `ebe19ff00dfee36f9d67a9a584840c6745950b05`.

Copy `overkey` and `basic_crud` into neutral temporary app directories; never install the upstream checkout. Use one exact published stable graph with Reflex `0.9.12`, run each app and its unchanged browser flow, stop servers, then upgrade that same venv to the published alpha pins. Preserve each app's `.web`, `reflex.lock`, local assets, source and database; force a fresh frontend build on the upgraded version. Run the same browser script again with isolated browser contexts and capture console, failed network requests, HTTP errors and server logs.

Overkey exercises real keyboard input, shared client state, memoized reset/time-up components, dataclass language options, computed Vars, and background countdown events. Basic CRUD exercises SQLite/SQLModel, a FastAPI `api_transformer`, browser request editing, API create/read/update/delete and background refresh of displayed model records.
