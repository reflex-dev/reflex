# Enterprise release references

Repository: https://github.com/reflex-dev/reflex-enterprise

Release branch: `refs/heads/r/pre-2026.10.05`

Read-only observed commit: `40aa7b33af419a6dc354e33873f6cd1270d28205`.
The GitHub API response is saved in `source-ref.json`.

`CHANGELOG.md` was fetched at that exact commit. `CHANGELOG-head.md` saves the
0.9.7a2 and 0.9.7a1 sections describing the Free-tier badge/export change,
AG Grid 36.2 / integrated Charts 14.2 upgrade, Google font helper, and audit
hook typing. The published tested package is PyPI `reflex-enterprise==0.9.7a2`;
no package from this branch was installed or executed.

Read-only implementing PR descriptions are preserved in `pr-241.json`,
`pr-239.json`, and `pr-238.json`. The AG Grid changelog links an orphan slug
`https://github.com/reflex-dev/reflex-enterprise/issues/ag-grid-36`, which
returns 404 (saved in `ag-grid-36-link-response.*`). Its implementing PR is
[238](https://github.com/reflex-dev/reflex-enterprise/pull/238).

Earlier demo/source references in this directory were used to construct the
campaign apps and compare public behavior. Framework execution always used
the isolated exact published PyPI graph documented in the report.
