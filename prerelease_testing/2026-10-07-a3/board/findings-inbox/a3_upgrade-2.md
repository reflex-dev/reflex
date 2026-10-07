ITEM: a3_upgrade
KIND: reverify
REF: N-002, N-007, N-009, N-024, N-040 (docs items; "Upgrading to Reflex 0.10" guide, #7496)
TITLE: The 0.10 upgrade guide, the #7462 changelog entry and the base_vars/tables/self-hosting additions are accurate on the published a3: every sample runs as written and every checked statement holds (two small gaps noted)
SEVERITY: low
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: guide = `git show 555b667c1:docs/changelog/upgrading/upgrading-to-0-10.md`.
  Python level (neutral dir): `cd a3_upgrade/apps/guide && REFLEX_ENV_MODE=dev $SB/envs/<a3|alpha2|stable>/bin/python probes/guide_probe.py <a3|alpha2|stable>`
  (+ `REFLEX_ENV_MODE=prod` for a3), `$SB/envs/<a3|stable>/bin/python probes/dt_probe.py <a3|stable>`.
  End to end: `a3_upgrade/bin/seq_guide.sh` (app `apps/guide/app`: `/sample` = section 1 sample verbatim, `/bg` = section 3 Parent/Child verbatim + the documented
  fix + instrumented variants, `/defaults` = runtime `type(self).level = 77`; a3 dev, 0.9.12 dev, a2 dev, a3 prod + Redis with 9 workers) and `bin/seq_guide2.sh`.
  Per item:
  - N-002 FIXED: a3 CHANGELOG lists the sqlmodel-cap removal (#7462) under Breaking Changes with the `sa_type=DateTime(timezone=False)` / pin advice; the linked
    tables.md section is accurate on sqlmodel 0.0.48 + SQLAlchemy 2.1.4 (naive insert rejected with "Datetime values must have timezone information", aware read-back,
    `can't compare offset-naive and offset-aware datetimes`, the documented `sa_type` sample and `NaiveDatetime` keep naive values) — same on 0.9.12 + sqlmodel 0.0.47.
  - N-007 FIXED: guide documents `State.get_fields()["_items"].default_value()` as the portable read; it returns `['a', 'b']` on 0.9.12, a2 and a3, and on 0.9.12
    `State._items.default_value()` raises exactly the quoted `AttributeError: 'list' object has no attribute 'default_value'`. Sample 1 renders a, b and the ClassVar URL in Chromium (dev + prod).
  - N-009 FIXED (documented): mixin assignment affects only states created afterwards (`(before, after) = (1, 5)`); a runtime `type(self).level = 77` is seen by new sessions
    on the same worker (dev: 77) and not by sessions on the other 8 prod workers (all 20) — matches the guide/base_vars warnings.
  - N-024 FIXED (documented) for what it covers: a3 (and a2), dev and prod: the verbatim `Child.work` raises `ImmutableStateError` (traceback in the server log), the
    documented `async with self:` fix increments, a read-only inherited handler outside the lock runs, inside the lock `type(self)` is `StateProxy`, `self.__class__`
    is the state class and `isinstance(self, Parent)` is True; 0.9.12 writes without the lock as stated. BUT the guide misses a case: see a3_upgrade-5.
  - N-040 FIXED (documented): `_client = None` + class assignment of an object -> `TypeError: Invalid default for field '_client': expected <class 'NoneType'>`; a zero-arg
    function is called once at assignment then per new instance; a class (`int`) becomes a factory; a factory with a side effect returning the wrong type runs its side
    effect, raises, keeps the previous default; a live lock in `Any` / `Optional[...]` is accepted and the first read on a new instance raises exactly
    `TypeError: cannot pickle '_thread.lock' object`; `ClassVar` objects are shared (identity).
  Other guide statements verified true: class read returns `Field`; child -> `ChildrenTypeError`; f-string / `.format()` -> `BackendVarFormatError` whose text now names
  `default_value()` / `ClassVar` (N-006 message part); `!r`/`!s`/`str()` embed the Field text; instance reads unchanged; 0.9 class assignment replaced the attribute but new
  instances kept the declared default; 0.10 assignment keeps a Var, affects new instances and `reset()`, keeps stored values; wrong type -> `TypeError: Invalid default for field`;
  `is_background`/`supersedes` read once (late mark ignored, no warning); undeclared `self.typo = 1` raises in dev and is a plain attribute in prod; self-hosting
  "2 * cpu_count + 1 workers with Redis" (9 on 4 CPUs); state-store note (0.9.12 sessions load on a3; after a rollback 0.9.12 discards the a3-saved session silently, no crash).
  Gaps (low): (1) the prop case is not always the quoted `TypeError: Unsupported type ... for LiteralVar`: `rx.box(id=State._label)` gives
  `TypeError: expected string or bytes-like object, got 'Field'` (N-006, unchanged) and `rx.link(href=State._label)` gives `TypeError: Invalid var passed for prop ReactRouterLink.to ...`;
  (2) the state-store reset is per substate: after a3 -> 0.9.12 a session whose auth substate a3 only read (never re-pickled) stays logged in while a3-written substates reset,
  so "starts the session over" can be a partial reset (twr rollback run).
EVIDENCE: a3_upgrade/logs/guide-probe-{a3,alpha2,stable}-dev.txt, guide-probe-a3-prod.txt, guide-dt-{a3,stable}.txt, shots/guide/guide-{a3-dev,a3-prod,alpha2-dev,stable-dev}.json,
  shots/guide/guide3-{a3,stable}-dev.json, logs/guide-*.server.log, shots/twr/twr-rollback-prod.json, NOTES.md "Item 3"
ROOT_CAUSE_GUESS: n/a (documentation; fixed by #7496 and the #7462/#7494 changelog entries)
