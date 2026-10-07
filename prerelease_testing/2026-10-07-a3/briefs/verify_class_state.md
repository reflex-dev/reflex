# Item `verify_class_state` — independently verify a3_class_state findings 7, 8, 11 (and spot-check 9)

Ports: frontend 3600-3619, backend 8600-8619. Work dir: $SB/apps/verify_class_state/. Write into a3_class_state/NOTES.md a
`## VERIFICATION` section (append only) and one `KIND: verify` inbox file per finding (`board/findings-inbox/verify_class_state-<n>.md`).
Venvs: build your own from PyPI (a3: `'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' pytest pytest-mock`; the same for
0.10.0a2 and 0.9.12). Read ../AGENT_BRIEF.md (hard rules) and ../COORDINATION.md §4.

Reproduce each finding from its inbox file (`board/findings-inbox/a3_class_state-{7,8,9,11}.md`) and the written repro ALONE before
reading the explorer's notes or scripts; write your own minimal test first, then re-run theirs. Try to refute: API misuse, a pattern
the docs/changelog explicitly disclaim (read `git -C /home/user/reflex show 555b667c1:docs/vars/base_vars.md` and the
`docs/changelog/upgrading/upgrading-to-0-10.md` guide, the reflex-base 0.10.0a3 CHANGELOG entries for #7495), pre-existing on a2 or
0.9.12, or harmless. For each: CONFIRMED / NARROWED / REFUTED, severity you would assign, whether it is a regression vs 0.10.0a2,
whether it would plausibly hit a real user (search reflex-dev public repos / docs for the pattern if you can), and the exact code
location in the published reflex-base 0.10.0a3 wheel. Findings:
- 7: undo stack restores "latest entry" instead of "what was saved" — rejected `mock.patch.object(..., Var)` / `mocker.patch.object(..., rx.field())`,
  `monkeypatch.delattr`, and an assignment made inside a patch window lose a configured default or leak the patched value (regression vs a2 claimed).
- 8: assigning `None` to an `Optional[str]` storage var (or a non-str to a Union var) drops browser storage.
- 9: ComponentState + named storage var + `cls.x = initial`: instances share one browser key (claimed pre-existing on 0.9.12).
- 11: AppHarness: a second app in one pytest process rendering a state from a shared module crashes on first render on 0.10, 0.9.12 renders
  (claimed unrelated to #7495; compare with the filed reflex#7479 / N-041 / N-003 before calling it new).
