# Scaling State

Large Reflex applications are easiest to maintain when each piece of state has one clear owner. Prefer several flat, feature-owned State classes over one application-wide State or a deep inheritance tree, and use inheritance only when the parent and child must always be loaded together.

Reflex State runs on the server and synchronizes changes to the browser. It is not a direct equivalent of React `useState` or Svelte component-local state. Choosing a State structure therefore affects ownership, loading, serialization, and how features depend on each other. See [How Reflex Works](/docs/advanced-onboarding/how-reflex-works) for the full runtime model.

```md alert info
# Recommended default

Organize a large application by feature. Give each page or workflow an independent State class that directly inherits from `rx.State`, keep application-wide State small, and access other State classes on demand instead of inheriting from them for convenience.
```

## Choose the Smallest Scope

Use the following table before adding a Var or State class.

| Need | Default | Why |
| --- | --- | --- |
| Reusable UI with no independently changing data | A component function with values and event handlers passed as arguments | Keeps shared UI independent of application State |
| Data and events owned by one page or feature | A class that directly inherits from `rx.State` | Creates a flat, independently loaded State branch |
| A small amount of per-user data used across features | A small application-defined session State | Gives cross-page data one owner without making all feature data global |
| One value from another State inside an event | `await self.get_var_value(OtherState.value)` | Makes the single-value dependency explicit and returns that value |
| Several values, or a mutation in another State | `await self.get_state(OtherState)` | Loads the other State explicitly and on demand |
| Several independently mutable instances of one reusable widget | [`rx.ComponentState`](/docs/state-structure/component-state) | Gives every statically created component instance its own State |
| Reusing ordinary Python or business logic | A helper, service, or repository function | Does not add Vars, inheritance, or loading relationships |
| Reusing Vars and event handlers across State classes | A narrow [State mixin](/docs/state-structure/mixins) | Copies reactive behavior into each concrete State; it does not create a shared State instance |
| Organizing many handlers without changing State ownership | [Decentralized event handlers](/docs/events/decentralized-event-handlers) | Splits code by feature while preserving the same State boundary |
| Parent data must be loaded with every child event | An inherited child State | Makes the runtime loading relationship explicit |
| Data intentionally synchronized across clients | [`rx.SharedState`](/docs/state-structure/shared-state) | Provides explicit cross-client synchronization |

Persistent domain data normally belongs in a database, object store, or external service. State should hold the per-user projection needed by the UI, identifiers and filters for loading it, and the progress or errors for the current workflow.

## Prefer Feature-Owned State

For a small app, keeping the page, State, and components in one module is convenient. As a feature grows, split that module into a feature package instead of creating top-level packages containing every page, every State, and every event in the application.

```text
support_app/
├── support_app.py
├── core/
│   ├── session.py
│   ├── permissions.py
│   └── database.py
├── features/
│   ├── tickets/
│   │   ├── page.py
│   │   ├── state.py
│   │   ├── service.py
│   │   ├── components.py
│   │   └── tests/
│   ├── customers/
│   └── reports/
└── shared/
    └── components/
```

This layout keeps the code that changes together close together:

- `state.py` owns the feature's Vars, computed vars, and event handlers.
- `service.py` contains database queries, external API calls, and business logic that does not need to be reactive.
- `components.py` binds feature-local UI to the feature State.
- `shared/components` contains reusable UI that accepts values and event handlers rather than importing a feature State.
- `core/session.py` owns only genuinely cross-feature per-user data, such as the current user, organization, or preferences.

All modules containing decorated pages must still be imported by the application package so Reflex discovers them. See [Project Structure](/docs/advanced-onboarding/code-structure) for page discovery and application setup.

### One Owner per Var

Choose an owner based on which feature changes the value, not on how many pages display it. Any page may render a Var by importing its State class. An event handler that needs its runtime value should use `get_var_value` or `get_state`.

```python
import reflex as rx


class PreferencesState(rx.State):
    rows_per_page: int = 25


class TicketsState(rx.State):
    page: int = 0
    ticket_ids: list[int] = []

    @rx.event
    async def load_page(self):
        rows_per_page = await self.get_var_value(PreferencesState.rows_per_page)
        self.ticket_ids = await load_ticket_ids(
            offset=self.page * rows_per_page,
            limit=rows_per_page,
        )
```

`TicketsState` does not need to inherit from `PreferencesState`. The dependency exists only in the event that needs the preference, so unrelated ticket events do not need to load the preferences State.

If an event needs several values or must update another State, load that State explicitly:

```python
class ProfileState(rx.State):
    display_name: str = ""


class OnboardingState(rx.State):
    @rx.event
    async def finish(self, display_name: str):
        profile = await self.get_state(ProfileState)
        profile.display_name = display_name
```

Cross-State mutation creates stronger coupling than a read. Keep it inside a clearly named workflow event and avoid using `get_state` as a general-purpose service locator. Shared domain operations usually belong in a service called by both States.

## State Inheritance Is a Loading Decision

Python inheritance may look like a convenient way to share methods, but State inheritance also creates a runtime State tree. When an event runs, Reflex loads the State containing the handler along with its parents and children. A large or highly connected parent can therefore make unrelated events more expensive.

Use an inherited child State only when all of the following are true:

1. The child logically specializes the parent.
2. The child needs the parent's data for most of its events.
3. Loading the parent and child together matches their intended lifetime.

Otherwise, keep both classes directly under `rx.State` and access the other State on demand. See [State Structure](/docs/state-structure/overview) for the loading and computed-var implications.

```python
# Prefer independent feature States for unrelated workflows.
class SearchState(rx.State):
    query: str = ""


class CheckoutState(rx.State):
    cart_id: str = ""


# Inherit only when the child is genuinely part of the same State tree.
class DocumentState(rx.State):
    document_id: str = ""


class DocumentHistoryState(DocumentState):
    revisions: list[str] = []
```

## Mixins Reuse Behavior, Not State Instances

A mixin contributes its Vars, computed vars, backend vars, and handlers to every concrete State that inherits it. Each concrete State owns its own resulting Vars. A mixin does not provide one shared value that several States read or update.

Prefer a plain helper or service when the reused code does not need to declare reactive Vars or event handlers. Use a mixin when at least two concrete States need the same small, cohesive reactive capability, such as pagination behavior.

```python
class PaginationMixin(rx.State, mixin=True):
    page: int = 0
    page_size: int = 25

    @rx.event
    def next_page(self):
        self.page += 1

    @rx.event
    def previous_page(self):
        self.page = max(0, self.page - 1)


class TicketsState(PaginationMixin, rx.State):
    ticket_ids: list[int] = []


class CustomersState(PaginationMixin, rx.State):
    customer_ids: list[int] = []
```

Avoid a broad mixin that combines authentication, loading, errors, forms, database access, and feature data. Composing enough mixins into one concrete State recreates a monolithic State while hiding where each Var came from. Keep mixins shallow, document required members, and test each concrete consumer. See [State Mixins](/docs/state-structure/mixins) for syntax and limitations.

## ComponentState Owns a Component Instance

Use `rx.ComponentState` when a reusable widget is instantiated a known number of times and each instance must change independently. Examples include multiple editors, counters, or filter panels placed explicitly on a page.

`ComponentState` is still server-side Reflex State. Use it for component-instance ownership, not to avoid a server event round trip for ephemeral browser interactions.

Do not use `ComponentState` merely to shorten a page State, and do not use it for items produced by `rx.foreach`. `ComponentState` currently creates one shared instance for all iterations of a `foreach`, so repeated rows would affect each other.

For a dynamic collection, keep the editing identity and drafts in the owning feature State and render each row as a stateless component:

```python
class TicketsState(rx.State):
    editing_ticket_id: int | None = None
    title_drafts: dict[int, str] = {}

    @rx.event
    def start_editing(self, ticket_id: int, title: str):
        self.editing_ticket_id = ticket_id
        self.title_drafts[ticket_id] = title

    @rx.event
    def update_title_draft(self, ticket_id: int, title: str):
        self.title_drafts[ticket_id] = title
```

The [Component State guide](/docs/state-structure/component-state) covers static instances, props, and access through the generated `.State` attribute.

## Keep Shared Components Stateless

A component used only inside one feature may import and bind directly to that feature's State. A component shared between features should normally receive the values and event handlers it needs. This keeps the shared component reusable and prevents feature import cycles.

```python
class TicketSearchState(rx.State):
    query: str = ""


def search_input(value, on_change) -> rx.Component:
    return rx.input(
        value=value,
        on_change=on_change,
        placeholder="Search",
    )


def ticket_toolbar() -> rx.Component:
    return search_input(TicketSearchState.query, TicketSearchState.set_query)
```

Passing a State class itself through several component layers usually hides ownership. Pass the smallest value or event interface that the component needs.

## Separate Schema from Large Handler Sets

Keeping handlers on a State class is the simplest option and should remain the default while the class is readable. When one feature has many handlers, use decentralized event handlers to split them into the feature's `events.py` module without creating another State boundary.

```python
class TicketsState(rx.State):
    selected_ticket_id: int | None = None


@rx.event
def select_ticket(state: TicketsState, ticket_id: int):
    state.selected_ticket_id = ticket_id
```

The type annotation makes the owning State explicit. Keep the handler in the same feature package as its State and page.

## Refactor a Monolithic State

Refactor in small, testable steps rather than rewriting the application around a new hierarchy.

1. **Inventory ownership.** Group Vars and handlers by page, workflow, component instance, and cross-page session data.
2. **Extract non-reactive logic.** Move database queries, API clients, validation helpers, and domain operations into services.
3. **Create flat feature States.** Move one feature at a time to a class that directly inherits from `rx.State`.
4. **Replace convenience inheritance.** Use `get_var_value` for one cross-State value and `get_state` for explicit multi-value access or mutation.
5. **Extract reusable widgets carefully.** Use a component function first, then `ComponentState` only when instances need independent mutable State.
6. **Introduce mixins last.** Extract a mixin only after the same reactive capability exists in multiple concrete States.
7. **Verify routes and behavior.** Test page loading, navigation, multiple clients, background work, and every cross-State workflow after each extraction.

Do not start by creating a shared `AppState` parent for every page. That makes access convenient but couples the State loading tree and provides an easy place for unrelated Vars to accumulate.

## Test State Boundaries

State classes are created and managed by Reflex. Do not construct them directly in application tests. Keep most domain logic in plain functions and services that can be unit tested without the Reflex runtime, then test State wiring through the application.

For every new State boundary, cover the behavior that made the boundary necessary:

- Open the same workflow as two clients and verify their private State remains isolated.
- Navigate away from and back to a page and verify its intended reset or persistence behavior.
- Exercise `on_load`, async events, and [background events](/docs/events/background-events) through their real event triggers.
- Verify that a cross-State event changes only the intended owner and that the consuming UI updates.
- Create multiple `ComponentState` instances and verify their values remain independent.
- Test every concrete State that consumes a mixin, including member-name conflicts and required members.
- Compile an application that imports every decorated page so missing page registrations and circular imports fail in CI.

When refactoring a monolithic State, keep the existing end-to-end tests passing after each extraction. Add a regression test for the new ownership boundary before removing the old Var or handler.

## Performance Checklist

- Keep most feature States as direct subclasses of `rx.State`.
- Put only data rendered by the browser in frontend Vars. Use [backend-only Vars](/docs/vars/base-vars#backend-only-vars) for per-session server data that should not be synchronized.
- Store persistent records in the database and synchronize only the UI projection needed by the current page.
- Use `get_var_value` when an event needs one value from a large State.
- Keep computed vars out of broad ancestor States unless all descendants depend on them.
- Keep `SharedState` minimal because updates may affect many linked clients.
- Use stable identifiers rather than duplicating large objects across several State classes.
- Measure event latency and synchronized payloads when changing a State boundary; a smaller source file does not necessarily mean a smaller runtime State.

## Review Checklist

Before adding or moving State, answer these questions:

1. Which feature owns the value?
2. Is the value persistent domain data, per-user UI State, component-instance State, or cross-client State?
3. What creates and resets it?
4. Which events may mutate it?
5. Does another State need one value, the full State, or only a shared service operation?
6. Would inheritance make unrelated events load this data?
7. Would a helper or decentralized handler solve the organization problem without changing State ownership?
8. Is a mixin sharing behavior, or accidentally hiding a monolith?
9. Is `ComponentState` being used inside `rx.foreach`?
10. Can a shared component accept values and events instead of importing feature State?

If the answers are unclear, keep the State boundary local to the feature until a concrete sharing requirement appears.
