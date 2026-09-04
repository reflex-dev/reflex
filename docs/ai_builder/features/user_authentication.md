---
tags: AI Builder
description: Let people sign in to your app with their Reflex account, choose who is allowed in, and see who has signed up.
---

# User Authentication

Add sign-in to your app without building or hosting any of it. People sign in with their **Reflex account**, your app receives their identity, and you manage who is allowed in from the **Auth** tab.

Nothing is generated for you to maintain. Your app talks to Reflex as a standard OpenID Connect provider through the `reflex-enterprise` library, so there is no login form, session store, or password reset in your codebase to keep working.

```md alert info
# Plan availability
Sign-in itself is available on every plan. **Choosing who can sign in** requires the Pro or Enterprise plan: on lower plans an app signs in anyone with a Reflex account, and the other options are shown with a Pro badge. If they are marked unavailable on a plan that should carry them, [contact sales](https://reflex.dev/pricing/).
```

## Add sign-in to your app

Ask the agent:

```text
Let people sign in to this app with their Reflex account, and show their name once they do.
```

Or open the **Auth** tab and select **Add sign-in to this app**.

```python exec
import reflex as rx
```

```python eval
rx.image(
    src="https://web.reflex-assets.dev/app_auth_empty_state.webp",
    alt="The Auth tab of an app with no sign-in configured. A centred card shows a person icon, the heading 'No sign-in yet', explanatory text about letting people sign in with their Reflex account, and a primary button labelled 'Add sign-in to this app'.",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

Either route sets two environment variables on the app, `OIDC_ISSUER_URI` and `OIDC_CLIENT_ID`. Neither is a secret and both reach every browser that signs in, so they need none of the handling a credential does. There is no client secret to store.

Once it is on, the tab shows the app's issuer and client id, the callback addresses the app signs in at, and the sections below.

```md alert warning
# On the Free plan, anyone with a Reflex account can sign in
"Add sign-in" means the app knows who someone is, not that it admits only people you chose. Until you narrow the audience, every Reflex account is allowed in, so adding sign-in on its own does not make an app private. Narrowing it requires the Pro or Enterprise plan.
```

## Choose who can sign in

The **Who can sign in** setting decides which accounts the app will admit:

| Setting | Who gets in |
| --- | --- |
| **Anyone** | Anyone with a Reflex account |
| **Project members** | Anyone with access to this app's project, including teams granted access |
| **Invite only** | The addresses you invite, plus anyone who can edit the app |
| **Just the team** | Only people who can edit the app |

**Anyone** is what every app starts on. The other three require the Pro or Enterprise plan.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/app_auth_audience_picker.webp",
    alt="The open 'Who can sign in' menu, listing Anyone, Project members, Invite only and Just the team. Anyone is selected with a tick; the other three are dimmed and each carries a small Pro badge.",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

**Project members** and **Just the team** follow project access, so somebody removed from the project loses app access with it. Neither needs a list to maintain.

```md alert warning
# Narrowing signs everyone out
Changing to a narrower setting ends every session the app is currently serving, not only the sessions it now excludes. People the new setting still allows can sign straight back in without seeing a screen, because their earlier approval is remembered. Widening back to **Anyone** signs nobody out.
```

## Invite specific people

Under **Invite only**, add an address to the list and that person can sign in the next time they try. They do not need a Reflex account first: signing in creates one, and the invite is matched on the address.

The list shows when each invite was created and whether it has been taken up. Withdrawing an invite removes it and ends whatever session it admitted.

Withdrawing an invite withdraws only the invite. Somebody who is also a project member, or who can edit the app, keeps the access those give them. Blocking is what refuses a person regardless of how they qualify.

## See who has signed in

The **Users** section lists everyone who has signed in, with a count beside the heading:

- **Person** — their name and email.
- **First consented** — when they first approved this app.
- **Last active** — their most recent token activity, which is as often a silent refresh as a sign-in.
- **Status** — whether they are blocked.

Search by email to filter the list, and page through it when the app has more people than one page holds.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/app_auth_users_table.webp",
    alt="The Users section of the Auth tab showing a table of five signed-in people with Person, First consented, Last active and Status columns. Above it are a heading reading 'Users', a count of people, a search box with placeholder 'Search by email...', and an 'Export CSV' button.",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

**Export CSV** downloads the whole list, not just the page you are looking at. The file carries each person's email, name, the two timestamps, whether they are blocked, and their Reflex user id.

Neither timestamp means "signed in". A person appears here when they approve the app, which can happen without them completing a sign-in, and **Last active** moves on a token refresh as well as a login.

## Block someone

Blocking refuses a person whatever else would admit them, and ends the sessions they are holding. Unblocking lets them sign in again; it does not restore the old session.

Use it to remove somebody who is abusing an app. It is available on every plan, because being unable to revoke access is worse than being unable to configure it.

```md alert warning
# A block can take up to 30 minutes to reach a running session
Blocking ends the sessions Reflex knows about immediately, but an app re-checks who somebody is on a schedule, and that answer is cached for 30 minutes. Somebody actively using the app may keep working until their app next asks. Treat a block as prompt, not instant.
```

## Customise the sign-in page

People sign in on a Reflex-hosted page. The **Sign-in page** section decides what that page says about your app:

- **Display name** — defaults to the app's name.
- **Note** — optional, shown under the heading. Use it for something the person needs to know before they sign in, such as which address to use.
- **Logo** — shown beside the name.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/app_auth_sign_in_page.webp",
    alt="The 'Sign-in page' section of the Auth tab, with a Display name field defaulting to the app's name, a Note field showing the placeholder about using a work address, an empty logo drop area with an Upload logo button, and a Save button.",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## How long people stay signed in

Access expires after an hour and is renewed silently, so nobody is asked to sign in hourly.

```md alert warning
# A session lasts at most 7 days
The renewal credential is stored in a browser cookie that expires after 7 days, so a session survives at most a week without a fresh trip through the sign-in page, whatever the token lifetimes suggest. Do not promise your users a longer one.
```

Signing out of your app clears its own session only. It does not sign the person out of Reflex or out of any other app they are using, which is why a logout button in your app behaves the way people expect.

## Read the signed-in user in your app

Ask the agent for what you want and it will wire this up. Where you read the identity depends on what you are doing with it.

**To show it**, the common claims are Vars on `User`, usable anywhere in a component:

```python
from reflex_enterprise.auth import User

rx.hstack(rx.avatar(src=User.picture), rx.text(User.name))
```

`User.name`, `User.email`, `User.sub` and `User.picture` are all available.

**To act on it**, `await User.current()` returns the claims as a dictionary inside an event handler, or `None` when nobody is signed in:

```python
from reflex_enterprise.auth import User


@rxe.event
async def add_note(self, form_data: dict):
    user = await User.current() or {}
    owner = user.get("sub")
```

Key your data on `sub` rather than on the email address, so a person who changes their address keeps their data.

Any other claim you want to render needs a computed var on an `AuthUserState` subclass. See [Authentication](/docs/enterprise/auth/example-app/) for that and for authorizing handlers.

```md alert warning
# Decide what somebody may do in backend code, never in the browser
Knowing who a person is and deciding what they may see are two different things. Anything the browser sends can be changed by whoever is using it, so a check that runs in the frontend keeps a page out of sight without keeping the data out of reach. Read the identity server-side and filter there.

Ask for it in those terms:

    Only return the current user's own records, filtered on the server by
    their sub. Do not rely on the frontend to hide other people's rows.
```

## Remove sign-in

**Remove sign-in** in the Auth tab stops the app signing anyone in and signs out everyone who is. The user list is kept, so adding it again finds the same people rather than an empty list.

If your app has its own identity provider configured through an integration, the Auth tab says so and does not offer Reflex-account sign-in. An app has one sign-in, not two. Disconnect the provider from the **Integrations** tab if you would rather use Reflex accounts.

## Troubleshooting

**Somebody cannot sign in.** Check **Who can sign in** first. Under **Invite only**, their address has to be on the list, and the match is on the address they sign in with rather than one they forward from. Under **Project members** or **Just the team**, they need project access. Then check the Users section in case they are blocked.

**Somebody you blocked is still using the app.** Expected for up to 30 minutes, for the reason above. Their next token refresh is refused.

**Sign-in works in the builder preview but not on the deployed app, or the reverse.** There is nothing to configure for either: the addresses an app may return to are read from its live serving addresses each time somebody signs in, and the preview and the deployment are both on that list. What does change them is renaming the app or attaching a custom domain, which is why a link somebody bookmarked at an old address stops working.

**The tab says sign-in is configured but withdrawn.** The app holds the settings while the broker will not complete a login for it, which is what a half-finished removal leaves. Select **Repair**. Nothing is lost and the user list is untouched.

**The Auth tab offers nothing and says the app uses its own sign-in.** An identity provider is connected through an integration, and an app has one sign-in rather than two. Disconnect it from the **Integrations** tab if you would rather use Reflex accounts.

## Related

- [Secrets](/docs/ai/features/secrets/) — store credentials your app needs at runtime.
- [Managing project access](/docs/ai/organization/project-access/) — decide who counts as a project member.
- [Deploy your app](/docs/ai/app-lifecycle/deploy-app/) — sign-in works on the deployed app and in the builder preview.
