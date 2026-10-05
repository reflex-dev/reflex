# Existing application upgrades

Both copied applications come from `reflex-dev/reflex-examples` commit `ebe19ff00dfee36f9d67a9a584840c6745950b05`. The original sources are retained under `source/`. They were copied into neutral `/private/tmp` app directories and never installed as packages. Their Python files and `rxconfig.py` were unchanged throughout testing.

The baseline installed `reflex==0.9.12`, `reflex-base==0.9.12` and exact stable component versions. The same Python 3.13 virtual environment was then upgraded with `uv pip install --python … --index-url https://pypi.org/simple -r ../inventory/alpha-requirements.txt`. Existing app directories, `.web`, `reflex.lock` and SQLite database were retained. Each alpha app received a cold `reflex export --no-zip` production build before running the same browser flow in development mode. Both cold builds succeeded. Lock/manifests changed during the rebuild, as expected; source hashes and interpreter path remained identical. [Exact graphs, hashes and comparison](evidence/upgrade-comparison.json) accompany the per-phase environment records.

The complete reproducible published dependency graphs are frozen in [stable requirements](stable-requirements.txt) and [alpha requirements](alpha-requirements.txt).

| App | Stable browser flow | In-place alpha browser flow |
|---|---|---|
| `basic_crud` | Passed | Passed |
| `overkey` | Timer/scoring passed; reset input failed | Same result |

`basic_crud` uses actual SQLModel/SQLite persistence and custom FastAPI endpoints. The browser created a product, read it, updated its label and quantity, deleted it, and observed each refreshed listing. A baseline row survived the upgrade with id `1` and unchanged created/updated timestamps (`2026-10-05T23:03:20.183221`). Both phases had no page errors, failed requests or HTTP failures. Console messages were ordinary development tooling notices. See [stable](evidence/basic_crud-stable.json) and [alpha](evidence/basic_crud-alpha.json).

`overkey` combines backend timer state with shared client state and real keyboard input. Both phases completed a five-second typing round with `100.00% accuracy`. Clicking Reset restored the language/time controls but left the client input populated (`course end` on stable, `into how b` on alpha). This is a stable-reproducing example defect. The later language-switch assertion did not run after the reset assertion failed. Both phases had no browser page errors or failed requests. See [stable](evidence/overkey-stable.json) and [alpha](evidence/overkey-alpha.json). This example does not use a third-party hotkey/auth library; external OAuth was not covered.

Replay with the retained original app files, an isolated published environment and the same database setup:

```sh
env -u PYTHONPATH uv run --no-project --python /private/tmp/ENV/bin/python reflex run --frontend-port 3122 --backend-port 8122
env -u PYTHONPATH uv run --no-project --python /private/tmp/ENV/bin/python python browser_flows.py basic_crud alpha http://localhost:3122 http://localhost:8122 evidence
env -u PYTHONPATH uv run --no-project --python /private/tmp/ENV/bin/python python browser_flows.py overkey alpha http://localhost:3122 http://localhost:8122 evidence
```

Run from the respective copied app directory. Initialize the CRUD fixture table through its original `Product.metadata.create_all(rx.model.get_engine())` before the baseline flow. Full server/build logs and screenshots are in `evidence/`.
