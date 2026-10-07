ITEM: a3_upgrade
KIND: reverify
REF: F-014
TITLE: `reflex component` (and init/build/share/install/publish) now exits 1 with a pointer to the wrapping-React docs and the component template
SEVERITY: low
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: from a neutral dir: `$SB/envs/a3/bin/reflex component [init|build --loglevel debug|share|install|publish --token x]; echo $?` and
  `reflex component --help`, `reflex component init --help`, `reflex --help | grep -i component`; same with `$SB/envs/alpha2/bin/reflex` and `$SB/envs/stable/bin/reflex`.
  a3: every form prints to STDERR "`reflex component` was removed in Reflex 0.10. Wrap React components directly in your app
  (https://reflex.dev/docs/wrapping-react/overview/) and start reusable component packages from the component template:
  https://github.com/reflex-dev/component-template" and exits 1; `--help` (also after a subcommand) prints the same text as help, rc 0;
  the command stays hidden from `reflex --help`. a2: "No such command 'component'", rc 2 for every form. 0.9.12: the real command group
  (rc 1/2 depending on subcommand). Links: `docs/wrapping-react/overview.md` exists in the a3 tree (reflex.dev itself is blocked by the
  sandbox proxy), `git ls-remote https://github.com/reflex-dev/component-template` answers (HEAD 3314ffe).
EVIDENCE: a3_upgrade/logs/cli-component-{a3,alpha2,stable}.txt
ROOT_CAUSE_GUESS: fixed by #7497 (reflex/reflex.py `component` hidden command, `click.exceptions.Exit(1)`)
