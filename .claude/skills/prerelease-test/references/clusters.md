# Cutting the changelog into clusters

A cluster is one agent's assignment: a group of changelog entries that share a subsystem, so the
agent can build one or two apps that exercise all of them together and notice how they interact.

## How to cut them

Group by **where the change lives at runtime**, not by which PR shipped it. Entries that touch the
same subsystem belong together even when they came from unrelated PRs, because the interesting
bugs are in their interaction — and one app can cover them all.

Aim for 8–12 clusters of 2–6 changelog entries each. A cluster that needs more than two apps is
too big; one with a single trivial entry should be folded into a neighbour.

Each cluster brief should carry:
- the changelog lines verbatim (agents should not have to re-derive what shipped),
- the PR numbers, so the agent can read intent,
- concrete "combine it with" suggestions — this is what turns a checklist into exploration,
- anything the entry implies but does not state (a perf claim to measure, a behavior that should
  differ between dev and prod).

## Standing coverage checklist

Most Reflex releases touch some subset of these. Use it to check you have not left a shipped change
unassigned, and as a source of interaction ideas.

| Area | What to build | Interactions worth forcing |
|---|---|---|
| Routing / navigation | Multi-page app with dynamic (`[id]`), catchall (`[[...splat]]`) and static-sibling routes; slow `on_load` | Navigate away mid-`on_load`; two tabs on different dynamic values; browser back/forward; direct load vs client-side nav; prod mode |
| State & event loop | Counter hammered by clicks while a background task writes | Background task + foreground handler racing; `yield`-streaming handlers; `async with self`; abrupt disconnect mid-stream |
| Components / props | One page per changed component | Prop bound to a State var, to a `client_state` var, and inside `@rx.memo`; explicit `style=` merged with forwarded props |
| Memoization | `@rx.memo` component with state-bound props and an event-handler prop, plus render counters | Memo in `rx.foreach`; memo wrapping `ComponentState`; two memos sharing a name in different modules; dev vs prod |
| Typing / annotations | State vars using every annotation shape the entry mentions | Assign at runtime (not just compile); pass the handler *uncalled* to a trigger; run on the oldest and newest supported Python |
| Uploads | `rx.upload` with buffered and streamed handlers | Hostile filenames (traversal, unicode, all-dots, spaces); raw multipart via httpx alongside browser uploads |
| Logging / CLI | Run every CLI verb with and without the logging flags | Strict JSON-lines parsing of stdout; a user app that configures `logging` itself; missing optional sub-packages |
| Config / plugins | App with the config knob set, unset, and set via env var | Deprecated form alongside the new form; plugin explicitly enabled vs implicit |
| Build / prod / export | Multi-page app through `run --env prod`, `export`, `run --env preview` | Serve exported frontend statically with a backend-only server; inspect generated `.web/package.json`; custom component with a changed library |
| Registration / multi-app | Two apps in one process; `AppHarness` twice | Sequential and simultaneous; check for registration leakage between them |
| Optional dependencies | Bare install, each extra, and the upgrade path | Import the optional package's feature without the extra and judge the error message quality |
| DevTools / perf | App with nested substates, custom components, client-only wrappers | Walk React fibers for `displayName`; record navigation main-thread cost; verify perf claims rather than trusting them |

## Downstream and packaging clusters

Two clusters that are not feature-shaped but catch the highest-severity problems:

- **Breaking-change surface.** For every entry under "Breaking Changes" (and every removal you spot
  in the diff), ask what a downstream caller sees. Grep the published `reflex-enterprise` wheel and
  the popular third-party packages (`reflex-local-auth`, `reflex-global-hotkey`) for the removed
  names. A bare `AttributeError`/`ImportError` with no pointer to the replacement is a finding even
  when the removal itself was intended.
- **Packaging.** `.claude/skills/prerelease-test/scripts/audit_pyi.py`, plus a check that each package's declared dependency pins
  match what the changelog says and that installing from the sdist works.
