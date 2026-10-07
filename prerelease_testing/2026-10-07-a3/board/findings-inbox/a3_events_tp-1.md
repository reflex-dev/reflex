ITEM: a3_events_tp
KIND: reverify
REF: N-024
TITLE: N-024 now documented and every claim of the new guide section holds on a3 (dev+prod), but the guide and changelog cover only *calling inherited handlers*; a direct write of an inherited var (or a same-state handler writing one) outside `async with self`, which 0.9.12 silently allowed, also raises `ImmutableStateError` on 0.10 and is not mentioned
SEVERITY: low
STATUS: changed
REGRESSION_VS_0.9.12: yes (behaviour change; the new behaviour is the safer one and matches docs/events/background_events.md, but code that worked on 0.9.12 now raises)
REGRESSION_VS_0.10.0a2: no (a2 == a3 for every case)
REPRO: |
  SB=<scratch>; W=$SB/apps/a3_events_tp/events  (copy of prerelease_testing/2026-10-07-a3/a3_events_tp/events: src driver tools bin)
  bash $W/bin/start.sh a3 dev n024_a3 n024doc && bash $W/bin/wait_up.sh http://localhost:3474/
  cd $W/driver && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_n024.py http://localhost:3474 $W/out/n024/n024_a3.json $W/logs/n024_a3.log
  bash $W/bin/stop.sh n024_a3      # repeat with venv `stable` (0.9.12) and `alpha2`; prod: `start.sh a3 prod ... n024doc`, base http://localhost:8477
  App: src/n024doc/n024doc/n024doc.py = the guide's own sample (Parent.count/bump, Child(Parent).work / work_locked, verbatim) + probes.
  Results (a3 dev = a3 prod = a2 dev; 0.9.12 dev = 0.9.12 prod):
    guide sample 1 `self.bump()` outside the lock ............ a3: ImmutableStateError, count unchanged | 0.9.12: no error, count+1 (unlocked write)   -> claim TRUE
    guide sample 2 `async with self: self.bump()` ............ a3: works | 0.9.12: works                                                       -> TRUE
    read-only inherited handler (`peek`) outside the lock .... a3: runs (type(self)=StateProxy) | 0.9.12: runs                                  -> TRUE
    inside the lock: type(self) / self.__class__ / isinstance  a3: StateProxy / Parent / True | 0.9.12: Parent / Parent / True                  -> TRUE (self.__class__ is the DECLARING class Parent, same as a foreground call and as 0.9)
    same-state handler writing its OWN var outside the lock .. a3: ImmutableStateError | 0.9.12: ImmutableStateError                          -> "already called through that proxy" TRUE
    NOT IN THE GUIDE:
    `self.count += 1` (inherited scalar var) directly in a Child background task outside the lock: a3/a2 ImmutableStateError | 0.9.12: no error, written without the lock
    a handler declared on Child itself that writes the inherited `count`, called outside the lock: a3/a2 ImmutableStateError | 0.9.12: no error, written
    (`self.seen.append(...)` on an inherited list raised on both versions; own vars raised on both)
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_events_tp/events/out/n024/{n024_a3_dev3,n024_alpha2_dev3,n024_stable_dev3,n024_a3_prod,n024_stable_prod}.json (key `after_reload.results`: direct_write:inherited, outside_call:write_inherited, outside_call:own_write); server logs events/logs/n024_*.log; guide text `git show 555b667c1:docs/changelog/upgrading/upgrading-to-0-10.md` lines 57-89, CHANGELOG.md v0.10.0a3 first breaking-change bullet. Also the evapp suite row bind.instance_access_and_inheritance is identical on a2/a3 dev+prod (bg_outside=ImmutableStateError, bump:self=StateProxy).
ROOT_CAUSE_GUESS: 0.9.12 `reflex/state.py` BaseState.__getattribute__ (~:1934) returns inherited vars via getattr(parent_state, name) and 0.9.12's StateProxy.__setattr__ path let the write of an inherited var land on the unproxied parent; 0.10 (#7312) routes inherited vars/handlers through the proxy. Docs fix only: extend the "Calling inherited handlers from background tasks" section (and the changelog bullet) to say that any write to an inherited var outside `async with self` - direct, or from a handler declared on the same state - now raises too.
