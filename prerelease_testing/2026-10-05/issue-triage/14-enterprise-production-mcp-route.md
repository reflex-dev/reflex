On the public full-stack production server, the MCP plugin's documented/default `POST /_reflex/mcp` endpoint returns **405 Method Not Allowed before authentication**, while `POST /_reflex/mcp/` reaches MCP authentication. Development redirects the bare endpoint with 307 and then returns the expected 401.

This reproduces with published enterprise **0.9.7a2 and 0.9.7a3**, using otherwise identical 104-package Reflex `0.10.0a1` graphs. It is preexisting in this tested a2/core-alpha combination, not an a3 regression. A stable Reflex production control was not run.

### Reproduce

Use the saved [minimal MCP app/config and public CLI adapter](https://github.com/reflex-dev/reflex/tree/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/components/routing/source/app), [comparison driver](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/components/routing/source/compare.py) and [full account-fixture/startup instructions](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/components/REPORT.md#reuse). Copy fixtures into a neutral app directory; install only published PyPI packages into fresh isolated UV environments.

The app has an ordinary counter State with a `@rxe.event` increment, `rxe.App()`, and:

```python
config = rxe.Config(
    app_name="mcp_probe",
    frontend_port=3131,
    backend_port=3131,
    api_url="http://localhost:3131",
    plugins=[rxe.MCPPlugin()],
)
```

Run the public production CLI. The recorded repro uses an existing Bun 1.4.2 path and a disposable local HTTP account endpoint supplying fictional Pro identity data to the official hosting SDK. CI/harness/offline bypasses are disabled; no real account is modified. The fixture only redirects credentials/account API traffic and records guard contexts.

Probe the production origin:

```sh
curl -i -X POST http://localhost:3131/_reflex/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"local-qa","version":"1"}}}'
curl -i -X POST http://localhost:3131/_reflex/mcp/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"local-qa","version":"1"}}}'
```

| Probe | Expected | Actual, both a2 and a3 |
| --- | --- | --- |
| `POST /_reflex/mcp`, no bearer | Reach MCP auth, directly or through the normal slash redirect | 405 `Method Not Allowed`, no Location |
| Same path, fabricated bearer | Authentication rejection | 405, before auth |
| `POST /_reflex/mcp/`, no/fabricated bearer | Authentication rejection | 401 `invalid_token` / Authentication required |
| `POST /_reflex/auth/token` | Issue anonymous session token | 200 |

Using issued tokens against the slash endpoint passes complete MCP mutation/computed-read, independent-session, custom-resource and router-redaction assertions. Session A increments to 4/doubled 8 while B stays 0/0. The slash variant is a diagnostic, **not** a passing result for the documented default route. Against the development backend, the default route redirects and passes the same checks.

### Environment and evidence

- macOS arm64, CPython 3.12.1, Bun 1.4.2; Reflex/base and component packages 0.10.0a1.
- [a2 frozen graph](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/components/requirements-a2-baseline.txt), [a3 graph](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/components/requirements-lock.txt) and per-version provenance under `routing/{a2,a3}/`. The only graph difference is enterprise a2 to a3.
- [Raw status/body/location comparison](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/components/routing/comparison.json), [per-version logs, network audits and contexts](https://github.com/reflex-dev/reflex/tree/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/components/routing).
- [Initial failing production default-route test](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/components/evidence/prod-default-endpoint/logs/mcp-http.json) and [complete component report](https://github.com/reflex-dev/reflex/blob/5e949cac0af6ee10ed89f625a7395793a7a66a4b/prerelease_testing/2026-10-05/enterprise/a3/components/REPORT.md).

The static frontend catch-all shadowing the backend slash redirect is an inference from responses and installed source, not a confirmed root cause. No framework or generated code was modified.
