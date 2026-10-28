# Experimental personal customization drafts

`reflex_components_internal.experimental.customization` is a headless prototype,
not a stable public component API. It adds no editor skin and is not exported at
the package root. The visual choice between the in-app canvas (A) and bounded
canvas (B) remains reversible. Existing components and business data are unchanged.

## Builder contract

A page owns a `Registry` of `Widget` definitions. A widget has one renderer,
allowlisted `Option` choices, and logical size limits. Register domain widgets
such as a revenue chart, tasks table, or search box, rather than arbitrary code or
business commands. Use the registered renderer for normal content, catalog
preview, and drag representation; pass presentation options and an explicit
render context in the eventual UI adapter. Resolve omitted options from the
builder's `Option.default` before rendering.

`Preferences` stores only widget instance order, logical geometry, explicit
options, and top/left navigation preference. `Registry.validate` rejects unknown
widgets/settings, invalid option values/types, duplicate instance IDs, overlaps,
and sizes outside page/widget bounds. Input collections are detached into
immutable tuples. Registry construction is builder-owned, not user-provided.

```python
from reflex_components_internal.experimental.customization import (
    Draft,
    Item,
    Option,
    Preferences,
    Registry,
    Widget,
)

registry = Registry((
    Widget(
        "revenue",
        render_revenue,
        (Option("legend", ("auto", "hidden"), "auto"),),
        min_width=4,
    ),
))
defaults = Preferences((Item("revenue-main", "revenue", width=8),))
draft = Draft(registry, saved_preferences, defaults)
draft.stage(candidate_preferences)  # Complete, atomic validated replacement.
draft.reset()  # Stages defaults; Cancel still restores saved.
snapshot = draft.save()  # No writes; the draft remains active.
try:
    personal_store.save(user_id, page_id, snapshot)
except OSError:
    show_retry_without_discarding_draft()
else:
    draft.confirm_save(snapshot)  # Closes only if the current draft still matches.
```

`cancel()` restores the initial saved layout and closes the transaction. Closed
drafts reject commands; begin a new `Draft` for the next edit session. A failed
validation leaves the previous draft intact. No command invokes widget renderers,
business handlers, or storage. Save returns an immutable snapshot; storage and
authorization remain the application's responsibility. After an asynchronous
save, `confirm_save` rejects a stale snapshot instead of closing newer edits.
This check cannot undo an external write that already happened. The UI adapter
must serialize Save with edits and Cancel (disable these commands while saving),
or use versioned compare-and-swap persistence with reconciliation. This module
does not provide atomic storage or concurrent-tab conflict resolution.

## Adapter acceptance criteria

- The builder decides whether to offer customization and where its entry appears.
  Defaults can be page-specific. Store preferences per authenticated user and page,
  never in shared business records. Label the action “Save my layout.”
- A nonmodal docked catalog reflows the available viewport. It is collapsible;
  rearrange and settings remain usable while it is closed. No backdrop. Top and
  left navigation remain recognizable during editing.
- The actual loaded widgets remain visible. Show skeletons only for loading or
  intentionally empty placeholders. Differentiate editing with shared surface,
  boundary, and hierarchy tokens, without introducing a separate visual theme.
- Use a dedicated grip for drag and visible size/settings commands. Preview,
  translucent actual-content drag image, and valid destination share identity.
  Highlight only valid destinations and clearly reject invalid drops.
- Provide keyboard Add, Move before/after, Size, and remove commands; Escape
  cancels a drag. The adapter maps these commands to the same validated candidate
  operation as pointer gestures. Do not rely on dragging alone.
- Preserve instance order and gaps. No implicit dense packing. Drawer reflow and
  viewport changes affect rendering only and must not stage or persist geometry.
  At laptop widths, collapse the catalog before crushing readable widget widths.
- While arranging, the integrating UI must disable business-write controls and
  guard their event handlers. This headless engine cannot suppress handlers in an
  arbitrary renderer. Preview renderers must be side-effect free. Keep read-only
  chart hover and inspection usable when they do not compete with edit gestures.
- Show pending/success/error states for personal storage. Failed Save retains the
  draft for retry. Reset changes only the draft until Save succeeds; Cancel can
  undo Reset. Disable edits, Reset, and Cancel while a Save request is pending,
  or supply versioned persistence and reconciliation. Apply application-specific
  revision checks for concurrent tabs. `confirm_save` alone cannot roll back an
  already completed personal-storage write.

## Research and tradeoffs

| Precedent | Useful pattern | Boundary for this prototype |
| --- | --- | --- |
| [Apple drag and drop HIG](https://developer.apple.com/design/human-interface-guidelines/drag-and-drop) | Content-linked drag representation and destination feedback | Requires non-drag commands and explicit rejection feedback; do not infer macOS-only controls for a web app. |
| [Grafana dashboard edit](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/create-dashboard/) | Contextual sidebar and persistent toolbar alongside real dashboard content | Docking consumes viewport width. Catalog collapse and minimum readable width need laptop verification. |
| [Home Assistant sections](https://www.home-assistant.io/dashboards/sections/) | Explicit edit mode, move controls, ordered cards and optional dense placement | Dense placement trades away ordering control; keep it off here. |
| [Home Assistant card resizing](https://www.home-assistant.io/dashboards/cards/#resizing-a-card) | Explicit row/column sizing and revert-to-default | Available sizes depend on the registered widget and available page width. |
| [Retool classic app IDE](https://docs.retool.com/classic-apps/concepts/ide) | Right inspector for selected component settings | Builder precedent, not authorization to expose app construction or business event wiring to end users. Retool now recommends its newer app builder. |

## Limits and next integration steps

No DOM drag/resize implementation, responsive solver, browser preference adapter,
serialization/migration format, authenticated storage, per-page placement UI, or
conflict resolver is provided. No browser screenshot or accessibility claim is
made for this headless module. It deliberately does not prescribe A/B geometry or
rebuild the user's Mac prototypes. Add a UI adapter only after visual feedback;
reuse actual renderers and run normal/edit/drag/laptop/top-nav/left-nav checks.

The overlap validator compares each pair of widgets, suitable for a small
dashboard MVP; no large-layout performance claim has been measured. Slot settings
are currently finite string, boolean, or integer choices. Numeric ranges, free
text, nested settings, widget dependencies, undo/redo, and cross-tab transactions
remain outside the prototype.
