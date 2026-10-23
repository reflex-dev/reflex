# cloud_cli — agent report (verbatim summary)

Findings (both low, neither a regression):
- CC-1 `reflex deploy` hides the new #7463 scaling-retry progress lines and its own success line unless `--loglevel debug`
  (export_for_deploy sets the console level to `subprocess_level()` = WARNING by default). Repro: NOTES.md, logs/r01-scaling-retry2.*.
- CC-2 A symlink pointing outside the app dir crashes `reflex export` / `reflex deploy` with `ValueError ... is not in the subpath`
  (reflex/utils/build.py `_zip`); same on 0.10.0. A dir symlink inside the app writes duplicate zip entries on both versions.

Passed: #7340, #7390, #7434/#7546, #7452, #7463 (retries + bounds), #7450 (sidecars STORED, -26 % zip time), build-sdk
`default_transport`, reflex-release 0.2.1a1 + towncrier 26.9.0 byte-identical to 0.2.0 + towncrier 25.8.0.
Re-verified: CLI-28 fixed; CLI-11 still fixed.
Note: the reflex wheel requires only `reflex-hosting-cli>=0.2.0`, so an existing env upgrading reflex does not pick up
the 0.2.1 fixes unless hosting-cli is upgraded explicitly.
Not covered: real cloud, GCP deploy flags, `cloud config --json`, interactive login success, GitHub-writing release commands.
