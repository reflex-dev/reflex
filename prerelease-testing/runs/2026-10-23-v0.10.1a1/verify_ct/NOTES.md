# verify_ct — verification of CT-6 and CT-1 (orchestrator, Opus; the Fable verifier was stopped by the spend limit)

## CT-6 — `[None]` for empty id'd checkbox groups
`./run.sh new` / `./run.sh prev` (dev, 3720/8720; app `ctform/`: three identical forms — dict handler, `TypedDict`
handler with `list[str]` fields, `rx.form.FormData` handler — each with an empty `checkbox_group` by id only, by name
only, by id + name, an id-only `checkbox_cards`, `rx.select` / `rx.radio_group` / text input by id, nothing selected).

| handler | 0.10.0 (`out/ctform-prev.json`) | 0.10.1a1 (`out/ctform-new.json`) |
|---|---|---|
| dict | `g_id: null, g_both: null, rad_id: null, txt_id: ""` | same + **`cards_id: null`** (checkbox_cards is a form control since #7345) |
| TypedDict `g_id/g_both: list[str]` | no coercion: `null` | **`[None]`** (a `None` inside `list[str]`) |
| FormData `getlist` | n/a | `g_id: [None], g_both: [None], cards_id: [None], rad_id: [None]` |
| name-only `g_name` | absent | absent (correct: nothing submitted) |

Verdict: CONFIRMED and narrowed. Not a regression for dict handlers (the `null` id-ref values existed on 0.10.0; only
`cards_id` is a new key). In the NEW API, an empty checkbox group with an `id` — including the non-deprecated
`id` + `name` combination — yields `[None]` for a `list[str]` TypedDict field and in `getlist()`; the changelog says such a
field "collects every value of its name", so the expected value is `[]` (or the key absent). User code like
`", ".join(form_data["toppings"])` raises TypeError. Severity low (new feature, empty-selection edge case, but the
`id` + `name` form is the documented style). Source: the id ref value (`null` from an empty group) is appended as an
entry when the name was submitted at most once (state.js getFormData).

## CT-1 — `radio_cards(as_child=True)`
Python probe (`str(rx.radio_cards.root(..., as_child=True))`): 0.10.1a1 compiles `css: {["asChild"]: true}`, exactly
like any unknown prop (`foo_bar=1` → `fooBar`); 0.10.0 compiled the real `asChild: true` prop, which crashed the page.
Verdict: CONFIRMED, low, not a regression — generic unknown-prop behaviour after the prop's removal; a crash became a
no-op. Optional: a compile-time warning for the removed prop.
