# State and Event Name Minification

Reflex identifies every state and every event handler on the wire by its full
dotted name. A click on a button bound to `CartState.clear` in an app called
`demo` sends:

```text
reflex___state____state.demo___demo____cart_state.clear
```

Those names are also baked into the compiled frontend — as React context names,
as the keys of every state delta, and as the event name in every handler
closure. In an app with many substates they add up in the bundle, in every
websocket frame, and in the initial state document.

Minification replaces them with short ids drawn from a checked-in
`minify.json`, so the same event becomes:

```text
a.b.b
```

It is **opt-in and off by default**. Turning it on requires a `minify.json` in
the app directory and two environment variables, and the frontend build and the
backend process must agree on both.

```md alert warning
# Minified names are not a security boundary.

Anyone can read `minify.json` from your repository, and `reflex minify lookup`
turns a minified name back into a module and class in one command. Minification
makes names shorter, not secret.
```

## Quick start

From the app directory (the one containing `rxconfig.py`):

```bash
reflex minify init
```

This imports your app, walks the state tree, and writes `minify.json`. Commit
that file — it is the shared contract between the frontend bundle and the
backend, and it must be identical in both.

```bash
git add minify.json
git commit -m "add minify.json"
```

Then build and run with both modes enabled:

```bash
REFLEX_MINIFY_STATES=1 REFLEX_MINIFY_EVENTS=1 reflex run --env prod
```

The same two variables must be set for whatever compiles the frontend *and* for
the backend process.

## The `minify.json` file

`minify.json` is read from the current working directory of the process, so
every command — `reflex minify`, `reflex run`, `reflex export`, and the backend
server — must be started from the app directory.

```json
{
  "events": {
    "demo.demo.State.CartState": {
      "add_item": "a",
      "clear": "b",
      "setvar": "c"
    }
  },
  "states": {
    "demo.demo.State.CartState": {
      "id": "b",
      "parent": "reflex.state.State"
    },
    "reflex.state.State": {
      "id": "a",
      "parent": null
    }
  },
  "version": 1
}
```

- `version` — the schema version, currently `1`. A file with any other version
  is rejected.
- `states` — maps a state's **full path** to its entry. The full path is the
  defining module followed by the class hierarchy from the root state down,
  e.g. `demo.demo.State.CartState`. Each entry has an `id` (the minified name)
  and a `parent` (the full path of the parent state, or `null` for a root
  state).
- `events` — maps a state's full path to `{handler name: minified name}`.

Framework states are included too: `reflex.state.State` and its internal
substates carry entries just like your own states.

Ids use the alphabet `a-z`, `A-Z`, `$` and `_` (the characters that are legal in
a JavaScript identifier), counting `a`, `b`, … `z`, `A`, … `_`, `ba`, `bb`, ….
A state id must be unique **among its siblings**, and must differ from its
parent's id — otherwise a relative path like `a.a` would be ambiguous. Two
states under different parents may both be `"b"`. An event id must be unique
**within its state**.

The file is written sorted and with a stable layout, so regenerating it produces
no spurious diffs. It is hand-editable — every field is validated on load and a
malformed file is rejected with an explicit error — but in practice let the CLI
maintain it.

### `parent` and reserved ids

An entry keeps its `parent` even after the class it names is deleted. That is
what keeps the deleted state's id reserved inside its sibling group, so a state
added later never inherits an id that an already-served frontend still uses for
something else.

## Environment variables

| Variable | Default |
|---|---|
| `REFLEX_MINIFY_STATES` | off |
| `REFLEX_MINIFY_EVENTS` | off |

Both are ordinary boolean env vars, so `1`, `true` and `yes` turn them on and
`0`, `false` and `no` turn them off. The two are independent: you can minify
state names, event handler names, or both. Neither has any effect without a
`minify.json`.

Both variables are read at **compile time** and at **run time**, and both places
must see the same values:

- The process that compiles the frontend (`reflex run`, `reflex compile`,
  `reflex export`) bakes the resolved names, and a digest of the whole scheme,
  into the generated bundle.
- The backend process resolves incoming event names through the same
  configuration.

In a split deployment — a statically hosted frontend and a separately deployed
backend — set both variables in the build environment and in the backend's
environment, and deploy the same `minify.json` to both.

## CLI reference

```bash
$ reflex minify --help
Usage: reflex minify [OPTIONS] COMMAND [ARGS]...

  Manage state and event name minification.

Commands:
  init      Initialize minify.json with IDs for all states and events.
  list      Print the state tree with IDs and minified names.
  lookup    Lookup a state or event handler by its minified path.
  sync      Synchronize minify.json with the current codebase.
  validate  Validate minify.json against the current codebase.
```

Every subcommand imports and compiles your app so that dynamically created
states (such as `rx.ComponentState` instances) are registered before the state
tree is walked. They read the config rather than apply it, so their output does
not depend on whether `REFLEX_MINIFY_*` is set in the shell running them.

### `reflex minify init`

Creates `minify.json` from the current state tree, numbering each sibling group
from `a`. It refuses to overwrite an existing file — use `sync` to update one,
or delete the file to start over.

```bash
$ reflex minify init
Info: Created minify.json with 7 states and 15 events.
```

### `reflex minify sync`

Adds entries for states and event handlers that are in your code but not yet in
the file, leaving existing ids untouched.

```bash
$ reflex minify sync
Info: Updated minify.json:
Info:   States: 7 -> 8
Info:   Events: 15 -> 17
```

Two flags change ids that clients may already be using:

- `--prune` removes entries for states and handlers that no longer exist in the
  code, freeing their ids for reuse.
- `--reassign-deleted` fills the gaps left by removed entries instead of
  continuing past the highest id in use.

```md alert warning
# `--prune` and `--reassign-deleted` can hand an old id to a new state.

A browser that is still running a frontend built against the previous file would
then resolve that id to the wrong state. Use them only when every client will
reload — for example in development, or as part of a release where the frontend
URL changes.
```

### `reflex minify validate`

Checks the file against the current code. Exits non-zero when there is anything
to fix, which makes it a useful CI step.

```bash
$ reflex minify validate
Warning: Missing entries (in code but not in config):
Warning:   - state:demo.demo.State.SecondNewState
Warning:   - event:demo.demo.State.SecondNewState.setvar
```

It reports:

- **errors** — duplicate state ids within a sibling group, a state that reuses
  its parent's id, or duplicate event ids within a state (exit code 1);
- **missing entries** — states or handlers in the code with no entry, which
  silently keep their long names (exit code 1);
- **warnings** — entries for states or handlers that no longer exist, and
  entries whose recorded `parent` no longer matches the code (exit code 0).

### `reflex minify list`

Prints the whole state tree with the id assigned to each state and handler. It
works without a `minify.json`, in which case it just prints the tree.

```bash
$ reflex minify list
State Tree (minify.json loaded)
`-- State -> "a"
    |-- Event Handlers:
    |   |-- hydrate -> "a"
    |   |-- set_is_hydrated -> "b"
    |   `-- setvar -> "c"
    |-- CartState -> "b"
    |   `-- Event Handlers:
    |       |-- add_item -> "a"
    |       |-- clear -> "b"
    |       `-- setvar -> "c"
    `-- SettingsState -> "c"
```

`--json` writes the same tree as a JSON document on stdout; logs and anything
your app prints while it loads go to stderr, so the output can be piped into
another tool.

### `reflex minify lookup`

Turns a minified name — copied from a browser devtools network frame, or from a
backend log line — back into the module, class and handler it refers to.

```bash
$ reflex minify lookup a.b.b
demo.demo.CartState
demo.demo.CartState.clear
```

The path is resolved segment by segment from the root state, and the leading
root state segment is optional and may be given either minified (`a`) or in full
(`reflex___state____state`) — so a name copied verbatim from the frontend
resolves as-is. On its own that segment looks the root state itself up. Because
states and event handlers are numbered independently,
the last segment is matched against the handlers of the state resolved so far as
well as against its substates; when a segment is ambiguous, both readings are
printed. Unminified segments are accepted too, so a partially minified name
still resolves.

`--json` prints the full resolution — `kind`, `module`, `class`, `handler` and
`full_path` for each segment — on stdout, again with logs on stderr.

## Frontend and backend must agree

A compiled frontend and the backend it talks to must resolve names the same way.
The frontend therefore carries a short digest of the scheme it was built with —
computed from the contents of `minify.json` together with the two mode
variables — and sends it when it opens its websocket. Uploads carry the same
digest in a `Reflex-Scheme` header, since they travel over HTTP rather than the
socket.

If the backend's digest differs, the backend:

1. logs a warning naming both digests;
2. sends a `scheme_mismatch` notice to that client;
3. ignores every event that client sends, and rejects its uploads with `409`.

The page stops sending events and tells the viewer it is out of date, offering a
reload.

This happens whenever the two sides diverge:

- the backend was deployed with a `minify.json` the frontend was not built
  against (or the other way round);
- one side has `REFLEX_MINIFY_STATES` or `REFLEX_MINIFY_EVENTS` set differently
  from the other;
- a browser is still running a bundle from before a deploy that changed
  `minify.json`.

The digest covers the state ids and the event map, so any edit that changes an
id invalidates every previously served bundle — including one that only adds
entries. Edits that change nothing a client can observe do not: a `parent` field
is not hashed, and a map whose `REFLEX_MINIFY_*` mode is off contributes nothing.
Plan deploys accordingly: ship the frontend and the backend together, and expect
open tabs to need a reload after an id changes.

## Deploy workflow

A typical loop when the state tree changes:

1. Add or rename states and event handlers as usual.
2. Run `reflex minify sync` and commit the updated `minify.json` alongside the
   code change.
3. Optionally run `reflex minify validate` in CI so a forgotten `sync` fails the
   build rather than silently shipping long names.
4. Build the frontend and run the backend with the same `REFLEX_MINIFY_*`
   values and the same `minify.json`.

States and handlers with no entry in the file keep their full names; this is not
an error, it just means those names are not shortened. Compiling with
minification enabled warns about them and points at `reflex minify sync`.

## Debugging a minified app

Backend logs, tracebacks and OpenTelemetry spans report the resolved (minified)
names, because that is what the event carried. `reflex minify lookup` maps them
back:

```bash
reflex minify lookup a.b.b
```

If you want readable names while reproducing a problem, unset the two
environment variables and rebuild; `minify.json` on its own changes nothing.

## Limitations

- **Run from the app directory.** `minify.json` is looked up in the process's
  current working directory, and the name scheme has to be installed before your
  state classes are imported. A backend started from anywhere else does not find
  the file, resolves names the default way, and rejects every client with a
  scheme mismatch.
- **In-process test harnesses.** A test process that imports Reflex before the
  app directory exists (for example `AppHarness` running in-process) must run
  with `REFLEX_MINIFY_STATES=0`.
- **`rx.ComponentState` instances are numbered by creation order.** Each
  `create()` call produces its own state class, named `Counter_n1`, `Counter_n2`
  and so on, and each gets its own `minify.json` entry. Inserting or reordering
  a `create()` call renames every instance after it, which moves their entries.
  Pass `_state_key` to give an instance a stable name — see
  [Component State](/docs/state-structure/component-state/#naming-the-state).
