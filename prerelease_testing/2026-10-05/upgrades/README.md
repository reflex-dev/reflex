# Todo upgrade

The unmodified Todo example from `reflex-dev/reflex-examples` commit
`ebe19ff00dfee36f9d67a9a584840c6745950b05` passed a real browser flow with published
Reflex 0.9.12, then the same flow after an in-place upgrade to the announced
alphas. The original app, `.web` and `reflex.lock` were retained during the first
upgrade. A second run rebuilt `.web` from scratch while keeping the same app and
environment. Add text containing `#`, `%` and Unicode, verify the form clears,
then click the completion button: all three runs pass.

`stable-freeze.txt` and `alpha-freeze.txt` capture the graph. Saved generated
package manifests and server logs distinguish stable, retained-frontend alpha,
and cold-rebuild alpha. The reproducible browser driver is
`../lifecycle/browser_checks.py --todo`. The cold run has a screenshot and full
console/network evidence under `evidence/todo-alpha-cold`.

An initial fixture copy omitted the upstream package's `__init__.py`; copying it
restored the correct State namespace before the stable baseline. That startup
error is retained in the early log but is not a framework regression. An old
browser tab briefly reported a version mismatch during the upgrade; reload
removed it. Final alpha runs have no page errors or new console errors.

The independent [Overkey and CRUD upgrade campaign](../components/upgrades/REPORT.md)
kept its app source, frontend lockfiles, environment and SQLite data through an
in-place upgrade, then tested cold exports. CRUD persisted a sentinel record and
timestamps; Overkey passed typing/countdown/scoring while reproducing its
preexisting input-reset defect.

For another upgrade, copy `todo/` to a neutral directory, create a disposable
venv with published `reflex==0.9.12`, and run its dev server on 3141/8141. Drive
`browser_checks.py --todo --url http://localhost:3141 --output <evidence>`.
Stop the server, install only the exact published pins from
`alpha-requirements.txt` into that same venv, restart and repeat. Preserve the
frontend for the first upgrade comparison, then move `.web` aside and repeat a
fresh build. Execute every command through `uv --no-config run --no-project
--python <venv>/bin/python` from the neutral app directory, with `PYTHONPATH`
removed and telemetry disabled.
