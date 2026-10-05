# Published tooling exploration

`probe.py` passed four real release-workflow generations (19, 20, 24 and 25
packages) and `sync --check`. Per-package booleans remain through 24 packages,
plus the prerelease input; 25 packages switch to text and remain below the
GitHub input limit. YAML is parsed and counts asserted, rather than inspecting
a string template alone. All four docgen metadata variants pass: ordinary LF,
UTF-8 BOM, leading whitespace and CRLF combinations.

Ten hosting scenarios use an actual localhost HTTP API through the installed
SDK and public CLI. Start/stop success, API refusals, missing deletion,
noninteractive rejected tokens, preserved stored credentials, post-auth expiry
guidance and multi-page JSON logs were exercised. Both vmtypes and regions
actually reach their listing endpoints and fail nonzero on a refusal.
`cli_entry.py` redirects only credential-file paths; no user token file is read
or written. `results.json` retains requests, exit codes and complete output.

One boundary is tracked in the central findings: initial token rejection omits
the login hint that appears after authentication succeeds. A missing app's
delete command returns a structured `deleted:false` JSON result and exits
nonzero; it is different from a generic refused request, which produces no
JSON. The test retains that distinction rather than silently flattening it.

The extended CLI campaign is documented under
[components/hosting](../components/hosting/REPORT.md); all 17 scenarios pass for the new history,
inspect, token-expiry, secret-update, project permission and project-ID
contracts with local fixtures, never a real cloud account.

`event_typing.py` independently models inventory callbacks with zero to four
arguments, complete/partial calls using both literals and State Vars, and
assignments to regular `Callable` types. Published `ty==0.0.84` reports
**All checks passed** against the alpha environment. The script was copied to
a neutral directory so resolution used isolated site-packages. No suppression
or checkout typechecking was used. `event-typing.log` is saved.

Rerun `probe.py --output <json>` through `uv --no-config run --no-project
--python <published-alpha-venv>/bin/python python <absolute script path>` from
a neutral directory. Install published PyYAML, docgen, release and hosting
packages into that venv. Run the typing fixture through published ty with
`check --project <neutral directory> --python <venv> <copied fixture>`.

Real cloud deploy, signed upload URLs, live watch cancellation, visual terminal
table widths and paid/free badge enforcement remain untested. No mock result
is described as a successful real deployment.
