# Campaign state (compact context) — <pass name> on the reflex <NEW> train (<date>)

Copy to `runs/<run>/CAMPAIGN_STATE.md` and fill in. Agents read this before anything else, so keep it short and
factual; link to the history / fixture READMEs instead of repeating them.

## What is under test
- **reflex <NEW> + reflex-base <NEW>**, released from `<pre-release branch>` at `<commit>` (tag `v<NEW>`). Which other
  train packages were re-released, and which stayed on earlier versions. Output of
  `uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref v<NEW>`: <N/N OK>.
- Published-wheel facts from preflight: exact `reflex-base` pin; every changed source file byte-identical between the tag
  and the installed venv (`git diff --name-only v<PREV>..v<NEW>` → `diff` against `$SB/envs/new/.../site-packages`);
  `.pyi` audit result.
- **reflex-enterprise <ENT_VERSION>** (offline wheel or PyPI + `CI=true`).

## What changed since <PREV> (`git log --oneline v<PREV>..v<NEW>`, plus every CHANGELOG.md top entry)
| PR | Change | Risk (what to hunt) |
|---|---|---|
| #… | … | … |

## Findings to re-verify (from `REGISTRY.md`; run the ORIGINAL repro, positive control FIRST)
| id | what | broken on (control venv) | fixture | item |
|---|---|---|---|---|
| … | … | `ctrl-…` | `fixtures/<area>/…` | … |

Known and filed (do NOT re-report unless changed): list the open/filed IDs from `REGISTRY.md` relevant to this pass.

## Items and ports
| item | covers | ports |
|---|---|---|
| preflight (orchestrator) | publish, wheel contents, `.pyi` audit, changelog/docs, blank-app smoke | 3100-3119 / 8100-8119 |
| … | … | … |

## Environment
- `SB=<scratch dir>`; venvs `new`, `prev`, `ctrl-<X>…`, `driver`, `new-ent`, `prev-ent` (see `scripts/bootstrap_envs.sh`).
- Disk / CPU budget notes; Chromium `/opt/pw-browsers/chromium`; reflex-examples commit; enterprise wheel location.
- Artifacts: `prerelease-testing/runs/<run>/<item>/` on branch `testing/prerelease` (the orchestrator commits).
