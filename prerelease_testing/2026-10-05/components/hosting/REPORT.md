# Hosting CLI JSON contracts

All 17 independent cases passed through the public installed CLI and real HTTP requests to a local fixture server. Tested packages: `reflex==0.10.0a1`, `reflex-base==0.10.0a1`, `reflex-hosting-cli==0.1.73a1`, `reflex-build-sdk==0.0.5`; optional envfile dependency `python-dotenv==1.2.1`. [Results](results.json) include exact arguments, exit codes, stdout/stderr, decoded JSON and endpoint request bodies. All imported framework paths are in the temporary environment's `site-packages`.

| Contract | Verified boundaries |
|---|---|
| App history | Full/null/empty records; URL retained; ISO timestamp; VM display name; null description becomes empty string |
| App inspect | UUID serialization; nested `timestamp`, `persist`, `last_updated` wire aliases; VM name; no deployment/null backend URL |
| Create token | Server-selected name and clamped expiration; null expiration; invalid duration exits 2 without authenticating |
| Secrets update | Sorted names-only JSON; human success/no-reboot wording; debug output contains no fixture values; empty value and embedded `=` retained; envfile overrides CLI values and omits bare keys; forbidden response exits 1 with empty stdout |
| Secrets list | Empty human response says the app has no secrets |
| Role permissions | Objects from the API become permission names; null list becomes `[]` |
| Deploy project | Whitespace/braced UUID canonicalized before lookup; missing project refuses before any app/build request; malformed string is looked up and refused before build |

`normalize_project_id` intentionally preserves stripped non-UUID strings. The malformed-ID check therefore verifies server lookup/refusal, not a stricter local UUID rule. Only authentication and project lookup requests occurred in the deploy refusal cases; no app, archive, build or deployment endpoint was reached.

Credential files were redirected to disposable fixture files, and their stored token remained unchanged. A Python audit hook blocked all nonlocal socket connections. No cloud service was contacted or deployed to.

```sh
env -u PYTHONPATH uv run --no-project --python /private/tmp/ENV/bin/python python extended.py --output results.json --deploy-app /private/tmp/INITIALIZED_APP
```

Run from a neutral directory with the exact published alpha graph. The deploy app must already have an initialized `.web` directory; the fixture never supplies a successful project/deployment response.
