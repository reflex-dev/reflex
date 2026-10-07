ITEM: verify_upgrade
KIND: verify
REF: A3-06 (a3_upgrade-5)
TITLE: CONFIRMED (docs gap): inherited-var writes outside `async with self` raise ImmutableStateError on a2/a3 and did not on 0.9.12 — but on 0.9.12 they only took effect with the in-memory state manager; with Redis they were silently discarded; in-place mutation of an inherited list already raised on 0.9.12
SEVERITY: low
STATUS: confirmed
REGRESSION_VS_0.9.12: yes (behaviour change; the new behaviour is the documented contract and turns a silent Redis-only write loss into an error)
REGRESSION_VS_0.10.0a2: no (a2 identical)
REPRO: Own app `prerelease_testing/2026-10-07-a3/a3_upgrade/verification/apps/bgt_{a3,a2,s912}` (Base(rx.State): count/items/inc; Mid(Base): level2; Worker(Mid): own, handlers;
  each background task catches the exception and reports it in `status`), `verification/probes/vu_run_bg.sh <venv> <app> <tag> [redis]` (dev, 3640/8640, redis 8649) + `vu_drive_bg.py`.
  outside the lock                      0.9.12 memory   0.9.12 Redis           a2/a3
  self.count += 10 (grandparent var)   ok 1->11        no error, LOST (1->1)  ImmutableStateError
  self.level2 += 10 (parent var)       ok 0->10        no error, lost         ImmutableStateError
  self.own += 10                       ImmutableState  ImmutableState         ImmutableStateError
  self.items.append("x") (inherited)   ImmutableState  ImmutableState         ImmutableStateError
  self.inc() (inherited handler)       ok +1           no error, lost         ImmutableStateError
  own handler writing count            ok +1000        no error, lost         ImmutableStateError
  own handler writing own              ImmutableState  ImmutableState         ImmutableStateError
  Docs at 555b667c1: upgrade guide covers inherited HANDLERS only; its sentence "A handler declared on the same state was already called through that proxy" is true but on 0.9.12
  that handler could still write inherited vars unlocked; a3 Breaking entry (#7312) is about handlers; a1 #7312 entries (shadowing, get_skip_vars removal, inherited mutable var
  "now sent to the client", descriptors) and background_events.md never mention inherited-var writes; background_events.md has always said writes outside the block raise.
  Explorer rerun (apps/guide/app + drive_guide.py, 3642/8642): 0.9.12 direct inherited write 14->114 no error; a3 all ImmutableStateError, 15/0/0. Reproduced.
  Suggested doc line: "Writing a var inherited from a parent state outside `async with self` — directly or through any handler — now raises ImmutableStateError. On 0.9 it raised nothing: with the in-memory state manager the write landed without the lock, with Redis it was silently lost."
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_upgrade/verification/out/bg/{s912-mem,s912-redis,s912-redis2,a3-mem,a2-mem}.json (+ .server.log tails), explorer_rerun/guide-{stable,a3}.json; NOTES.md "## VERIFICATION" A3-06
ROOT_CAUSE_GUESS: 0.9.12 reflex/istate/proxy.py:322-329 (`name in self.__wrapped__.get_skip_vars()` bypass) + reflex/state.py:1455-1456 (`set(cls.inherited_vars)`); the Redis loss is because the proxy's pre-lock wrapped state is a deserialized copy that `async with self` replaces. a3: reflex/istate/proxy.py:389-415 (only `_self_*`, lock held, `BaseState.__slots__` pass). Docs: docs/changelog/upgrading/upgrading-to-0-10.md "Calling inherited handlers from background tasks".
