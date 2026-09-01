---
title: "Example: A Complete App"
---

_New in reflex-enterprise v0.9.1._

# Example: A Complete App

This page builds one small, complete app with `rxe.AuthPlugin`: **Team Notes**,
a shared team notepad with a public landing page, a login-protected dashboard,
and one admin-only action. It shows the full pattern — configuration, checks,
state, pages — in about 100 lines of code, applying the practices from
[secure by default](/docs/enterprise/auth/secure-by-default/).

If you have not set up the plugin before, read the
[overview](/docs/enterprise/auth/overview/) first.

## Authentication and authorization

The plugin separates two questions, and the design of your app follows from
keeping them apart:

- **Authentication** answers *"who is this user?"* The plugin owns it
  completely: it runs the OIDC flow against your identity provider and
  registers `/login`, `/logout`, `/callback`, and `/forbidden`. You never write
  a login form, an OAuth redirect, or a token exchange.
- **Authorization** answers *"what may this user do?"* You own it, and you
  express it with the `auth=` argument on events, fields, computed vars, and
  the plugin itself. An authorization check runs only after authentication
  succeeds, so a check always has a resolved user to reason about.

Pick the `auth=` value from the question you are answering:

| You want | Write | Kind |
| --- | --- | --- |
| Any logged-in user may use it | nothing — the secure default | authentication |
| Anyone may use it, logged in or not | `auth=False` | opt-out |
| Only some logged-in users may use it | `auth=my_check` | authorization |

```md alert warning
# Do not build authorization out of `if` statements in handlers
A role check written inside a handler body protects that one handler, silently, and only if every future edit remembers it. A check attached with `auth=` is enforced by the framework on every call, fails closed when it raises, and is visible at the definition site. Put policy in `auth=`, not in control flow.
```

## What we will build

| Surface | Route / name | `auth=` | Who reaches it |
| --- | --- | --- | --- |
| Landing page | `/` | `False` | everyone |
| Dashboard page | `/notes` | default (`True`) | logged-in users |
| `add_note`, `join_team_board` events | — | default (`True`) | logged-in users |
| `clear_all_notes` event | — | `is_admin` | the `admins` group |
| `dismiss_promo` event | — | `False` | everyone |
| `show_promo` field | — | `False` | everyone |
| `notes` field, `note_count` var | — | default (`True`) | logged-in users |

The project has three files:

```text
team_notes/
├── rxconfig.py             # plugin + provider configuration
└── team_notes/
    ├── authz.py            # the authorization checks
    └── team_notes.py       # state, pages, app
```

The notes live in an `rx.SharedState` linked to one team token, so every
signed-in user reads and writes the same board and edits propagate live. A real app would also persist the notes to a
database — shared state is memory-resident — but nothing about the auth
pattern changes.

## Step 1: Configure the plugin

Add `rxe.AuthPlugin()` to `rxconfig.py`. The provider is configured entirely
through the `OIDC_*` environment variables — set them in your deployment
environment, or default them here for local work:

```python
# rxconfig.py
import os

import reflex_enterprise as rxe

os.environ.setdefault("OIDC_ISSUER_URI", "https://idp.example.com")
os.environ.setdefault("OIDC_CLIENT_ID", "team-notes")
os.environ.setdefault("OIDC_CLIENT_SECRET", "change-me")  # optional with PKCE

config = rxe.Config(
    app_name="team_notes",
    plugins=[
        rxe.AuthPlugin(
            # The is_admin check reads the ``groups`` claim, so request it.
            extra_scopes=["groups"],
        ),
    ],
)
```

Placeholder values are enough to import, compile, and preview the app. OIDC
discovery runs only when a user first logs in, so the app builds before any
real identity provider exists. See
[providers](/docs/enterprise/auth/providers/) for named and multi-provider
setups.

## Step 2: Write the authorization checks

Keep every check in one module, and name each one for the question it answers.
A check receives a context object and returns a bool; read the user's claims
from `ctx.auth_user_state.userinfo`:

```python
# team_notes/authz.py
"""Authorization checks for Team Notes. Attach them with ``auth=``."""

from reflex_enterprise.auth import AuthContext


def is_admin(ctx: AuthContext) -> bool:
    """Allow only members of the ``admins`` group."""
    return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])
```

Annotating `ctx` with the `AuthContext` union makes `is_admin` usable on any
surface — an event, a field, a var, or the plugin's global default. A check
never runs for an anonymous caller, and a check that raises fails closed. See
[authorization checks](/docs/enterprise/auth/secure-by-default/#authorization-checks)
for async checks and the per-surface context types, and
[testing](/docs/enterprise/auth/testing/) for how to unit-test them.

## Step 3: The state

The plugin protects every field, computed var, and event handler by default.
That default does most of the work: you only annotate the exceptions —
the public surfaces (`auth=False`) and the admin-only action
(`auth=is_admin`).

```python
# team_notes/team_notes.py
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState, User

from team_notes.authz import is_admin


class UserExtras(AuthUserState):
    """Project the ``groups`` claim onto the frontend, for rendering only."""

    @rx.var
    def is_admin_user(self) -> bool:
        return "admins" in (self.userinfo.get("groups") or [])


class SiteState(rx.State):
    # Public: the landing page reads and writes this before anyone logs in.
    show_promo: rx.Field[bool] = rxe.field(True, auth=False)

    @rxe.event(auth=False)
    def dismiss_promo(self):
        self.show_promo = False


class NotesState(rx.SharedState):
    # Protected by default: withheld from the client until login.
    notes: rx.Field[list[str]] = rx.field([])

    # Protected by default; the placeholder shows until the user is resolved.
    @rxe.var(initial_value=0)
    def note_count(self) -> int:
        return len(self.notes)

    @rxe.event  # default auth=True: only signed-in users join the board
    async def join_team_board(self):
        if not self._linked_to:
            await self._link_to("team-notes")

    @rxe.event  # default auth=True: anonymous callers are sent to /login
    async def add_note(self, form_data: dict):
        user = await User.current() or {}
        author = user.get("name") or user.get("sub") or "someone"
        text = (form_data.get("text") or "").strip()
        if text:
            self.notes = [*self.notes, f"{text} — {author}"]

    @rxe.event(auth=is_admin)  # authorization: only admins may clear the board
    def clear_all_notes(self):
        self.notes = []
```

Four things to notice:

- **The notes are genuinely shared.** `NotesState` is an
  [`rx.SharedState`](/docs/state-structure/shared-state/): every signed-in
  user links to the same `"team-notes"` token, so an added or cleared note
  propagates to everyone on the dashboard. The protected `join_team_board` event does the linking, and the
  page guard guarantees a resolved user before it runs.
- **`UserExtras` exists for the UI, not for security.** The common claims
  (`name`, `email`, `sub`, `picture`) are already frontend Vars on `User`; any
  other claim you want to *render* — here, whether to show the admin button —
  needs a computed var on an `AuthUserState` substate. The enforcement is the
  `auth=is_admin` on the handler, never the rendering.
- **`await User.current()`** returns the claims dict inside any event handler,
  or `None` when anonymous. Because `add_note` requires login, the user is
  always resolved there.
- **Protected computed vars get an `initial_value`.** The placeholder is baked
  into the frontend bundle and shown until the real value arrives after login,
  so a logged-out visitor sees `0` instead of a broken widget.

## Step 4: The pages

Mark the landing page public with `auth=False`. Leave the dashboard on the
default, which requires login: anonymous visitors are redirected to `/login`
and returned to `/notes` afterward.

```python
def navbar() -> rx.Component:
    return rx.hstack(
        rx.heading("Team Notes", size="5"),
        rx.spacer(),
        rx.cond(
            User.sub != "",
            rx.hstack(
                rx.avatar(src=User.picture, fallback="U", size="2"),
                rx.text(User.name),
                rx.link("Sign out", href="/logout"),
                align="center",
                spacing="3",
            ),
            rx.link("Log in", href="/login"),
        ),
        width="100%",
        padding="1em",
    )


@rxe.page(route="/", title="Team Notes", auth=False)
def index() -> rx.Component:
    """Public landing page: opted out of secure-by-default on purpose."""
    return rx.vstack(
        navbar(),
        rx.cond(
            SiteState.show_promo,
            rx.hstack(
                rx.text("New: notes now update live for the whole team."),
                rx.button("Dismiss", on_click=SiteState.dismiss_promo, size="1"),
                align="center",
                spacing="3",
            ),
        ),
        rx.heading("Keep your team's notes in one place."),
        rx.link("Open the dashboard", href="/notes"),
        align="center",
        spacing="4",
    )


@rxe.page(route="/notes", title="Notes", on_load=NotesState.join_team_board)
def notes() -> rx.Component:
    """Protected dashboard: anonymous visitors are redirected to /login."""
    return rx.vstack(
        navbar(),
        rx.heading(f"Team notes ({NotesState.note_count})"),
        rx.foreach(NotesState.notes, rx.text),
        rx.form(
            rx.hstack(
                rx.input(name="text", placeholder="Write a note"),
                rx.button("Add", type="submit"),
            ),
            on_submit=NotesState.add_note,
            reset_on_submit=True,
        ),
        rx.cond(
            UserExtras.is_admin_user,
            rx.button(
                "Clear all notes",
                on_click=NotesState.clear_all_notes,
                color_scheme="red",
            ),
        ),
        align="center",
        spacing="4",
    )


app = rxe.App()
```

The module ends with `rxe.App()`, not `rx.App()`. The enterprise app class is
what enforces the plugin's protection; with the plugin registered, a plain
`rx.App()` raises a `ConfigError` at startup.

```md alert warning
# Hiding a control is not enforcement
The `rx.cond` hides the **Clear all notes** button from non-admins, which is good UX — but any client can dispatch the event directly. The `auth=is_admin` on `clear_all_notes` is what actually refuses the call, with an "Action not allowed" toast. Always pair a hidden control with a check on its handler.
```

Pages accept only a bool for `auth=`. To put a role check in front of whole
pages, make the check the app-wide baseline with `AuthPlugin(auth=is_admin)` —
authenticated visitors who fail it are redirected to `/forbidden`. See
[the global default](/docs/enterprise/auth/secure-by-default/#the-global-default).

## Step 5: Run it

```bash
reflex run
```

Open the app: the landing page renders for everyone, and anyone — signed in
or not — can dismiss the promo banner. Click **Open the dashboard** and you
are redirected to `/login`; the plugin renders a button for the configured
provider. To complete a real login, register the app's
callback URL (`http://localhost:3000/callback` in local dev) as an allowed
redirect URI in your identity provider, and point the `OIDC_*` variables at
it. See [deploying to production](/docs/enterprise/auth/deployment/) for
production callback URLs and HTTPS.

After login: the notes and the count appear, and `add_note` signs entries
with your name. Sign in from a second browser and the two dashboards show the
same board — a note added in one appears in the other, because both sessions
linked to the shared `"team-notes"` state. The clear button appears only if
your IdP puts you in the `admins` group — and refuses everyone else even if
they dispatch the event by hand.

## The rules this app follows

1. **Never hand-roll authentication.** No login form, no password column, no
   OAuth redirect, no session cookie code. The plugin and the identity
   provider own all of it; your app links to `/login` and `/logout`.
2. **Express authorization with `auth=`, in one place.** Checks live in
   `authz.py`, named for the question they answer, and attach at the surface
   they protect. Handlers contain business logic, not policy.
3. **Opt public surfaces out deliberately.** Every `auth=False` in the app is
   a decision you can point at: the landing page, the promo banner's field,
   its dismiss event. Everything else is protected because you did nothing.
4. **Give protected values presentable placeholders.** Declared defaults and
   `initial_value` are what logged-out visitors see. Make them look
   intentional (`0`, an empty list, a "log in to see this" string), not
   broken.
5. **Render from claims, enforce with checks.** Frontend claim vars
   (`User.name`, `UserExtras.is_admin_user`) decide what to *show*; `auth=`
   decides what is *allowed*.

## Common mistakes

- **Using `rx.App()` instead of `rxe.App()`.** With the plugin registered,
  `rx.App()` raises a `ConfigError` at startup. Without the plugin registered,
  the app runs with **no protection at all** — nothing fails, every surface is
  public. Both halves are required: the plugin in `rxconfig.py`, and
  `rxe.App()` in the app module.
- **Everything looks blank or empty when logged out.** That is
  secure-by-default working: protected fields render their declared defaults
  and protected vars their `initial_value` until login. Mark truly public
  surfaces `auth=False`, and give the rest placeholders that read as
  intentional.
- **`redirect_uri_mismatch` at the IdP.** The exact callback URL (scheme,
  host, and path) is not registered with the identity provider. Register the
  full URL for each environment. See
  [deploying to production](/docs/enterprise/auth/deployment/).
- **Writing the auth routes yourself.** The plugin owns `/login`, `/logout`,
  `/callback`, and `/forbidden`. Customize what they *render* via the plugin's
  page arguments ([custom pages](/docs/enterprise/auth/custom-pages/)); never
  add your own routes at those paths.
- **Calling `register_auth_endpoints`.** That is the pre-plugin API. It is
  deprecated and will be removed in 1.0 — the plugin registers the endpoints
  itself. The [providers](/docs/enterprise/auth/providers/) page covers
  migrating off it.

## Related

- [Overview](/docs/enterprise/auth/overview/): plugin setup and the login
  flow, end to end.
- [Secure by default](/docs/enterprise/auth/secure-by-default/): the full
  enforcement model, the `auth=` wrappers, and the context objects.
- [Providers](/docs/enterprise/auth/providers/): environment variables,
  scopes, and multi-provider setups.
- [Testing](/docs/enterprise/auth/testing/): unit-testing checks and
  mock-IdP flow tests.
- [Deploying to production](/docs/enterprise/auth/deployment/): HTTPS,
  callback URLs, and troubleshooting.
