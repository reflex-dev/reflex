```python exec
import reflex as rx
from pcweb.templates.docpage import definition
```

# Shared State

_New in version 0.8.23_.

Defining a subclass of `rx.SharedState` creates a special type of state that may be shared by multiple clients. Shared State is useful for creating real-time collaborative applications where multiple users need to see and interact with the same data simultaneously.

## Using SharedState

An `rx.SharedState` subclass behaves similarly to a normal `rx.State` subclass and will be private to each client until it is explicitly linked to a given token. Once linked, any changes made to the Shared State by one client will be propagated to all other clients sharing the same token.

```md alert info
# What should be used as a token?

A token can be any string that uniquely identifies a group of clients that should share the same state. Common choices include room IDs, document IDs, or user group IDs. Ensure that the token is securely generated and managed to prevent unauthorized access to shared state.
```

```md alert warning
# Linked token cannot contain underscore (_) characters.

Underscore characters are currently used as an internal delimiter for tokens and will raise an exception if used for linked states.

This is a temporary restriction and will be removed in a future release.
```

### Linking Shared State

An `rx.SharedState` subclass can be linked to a token using the `_link_to` method, which is async and returns the linked state instance. After linking, subsequent events triggered against the shared state will be executed in the context of the linked state. To unlink from the token, return the result of awaiting the `_unlink` method.

To try out the collaborative counter example, open this page in a second or third browser tab and click the "Link" button. You should see the count increment in all tabs when you click the "Increment" button in any of them.

```python demo exec
class CollaborativeCounter(rx.SharedState):
    count: int = 0

    @rx.event
    async def toggle_link(self):
        if self._linked_to:
            return await self._unlink()
        else:
            linked_state = await self._link_to("shared-global-counter")
            linked_state.count += 1  # Increment count on link

    @rx.var
    def is_linked(self) -> bool:
        return bool(self._linked_to)

def shared_state_example():
    return rx.vstack(
        rx.text(f"Collaborative Count: {CollaborativeCounter.count}"),
        rx.cond(
            CollaborativeCounter.is_linked,
            rx.button("Unlink", on_click=CollaborativeCounter.toggle_link),
            rx.button("Link", on_click=CollaborativeCounter.toggle_link),
        ),
        rx.button("Increment", on_click=CollaborativeCounter.set_count(CollaborativeCounter.count + 1)),
    )
```

```md alert info
# Computed vars may reference SharedState

Computed vars in other states may reference shared state data using `get_state`, just like private states. This allows private states to provide personalized views of shared data.

Whenever the shared state is updated, any computed vars depending on it will be re-evaluated in the context of each client's private state.
```

### Identifying Clients

Each client linked to a shared state can be uniquely identified by their `self.router.session.client_token`. Shared state events should _never_ rely on identifiers passed in as parameters, as these can be spoofed from the client. Instead, always use the `client_token` to identify the client triggering the event.

```python demo exec
import uuid

class SharedRoom(rx.SharedState):
    shared_room: str = rx.LocalStorage()
    _users: dict[str, str] = {}

    @rx.var
    def user_list(self) -> str:
        return ", ".join(self._users.values())

    @rx.event
    async def join(self, username: str):
        if not self.shared_room:
            self.shared_room = f"shared-room-{uuid.uuid4()}"
        linked_state = await self._link_to(self.shared_room)
        linked_state._users[self.router.session.client_token] = username

    @rx.event
    async def leave(self):
        if self._linked_to:
            return await self._unlink()


class PrivateState(rx.State):
    @rx.event
    def handle_submit(self, form_data: dict):
        return SharedRoom.join(form_data["username"])

    @rx.var
    async def user_in_room(self) -> bool:
        shared_state = await self.get_state(SharedRoom)
        return self.router.session.client_token in shared_state._users


def shared_room_example():
    return rx.vstack(
        rx.text("Shared Room"),
        rx.text(f"Users: {SharedRoom.user_list}"),
        rx.cond(
            PrivateState.user_in_room,
            rx.button("Leave Room", on_click=SharedRoom.leave),
            rx.form(
                rx.input(placeholder="Enter your name", name="username"),
                rx.button("Join Room"),
                on_submit=PrivateState.handle_submit,
            ),
        ),
    )
```

```md alert warning
# Store sensitive data in backend-only vars with an underscore prefix

Shared State data is synchronized to all linked clients, so avoid storing sensitive information (e.g., client_tokens, user credentials, personal data) in frontend vars, which would expose them to all users and allow them to be modified outside of explicit event handlers. Instead, use backend-only vars (prefixed with an underscore) to keep sensitive data secure on the server side and provide controlled access through event handlers and computed vars.
```

### Introspecting Linked Clients

An `rx.SharedState` subclass has two attributes for determining link status and peers, which are updated during linking and unlinking, and come with some caveats.

**`_linked_to: str`**

Provides the token that the state is currently linked to, or empty string if not linked.

This attribute is only set on the linked state instance returned by `_link_to`. It will be an empty string on any unlinked shared state instances. However, if another state links to a client's private token, then the `_linked_to` attribute will be set to the client's token rather than an empty string.

When `_linked_to` equals `self.router.session.client_token`, it is assumed that the current client is unlinked, but another client has linked to this client's private state. Although this is possible, it is generally discouraged to link shared states to private client tokens.

**`_linked_from: set[str]`**

A set of client tokens that are currently linked to this shared state instance.

This attribute is only updated during `_link_to` and `_unlink` calls. In situations where unlinking occurs otherwise, such as client disconnects, `self.reset()` is called, or state expires on the backend, `_linked_from` may contain stale client tokens that are no longer linked. These can be cleaned periodically by checking if the tokens still exist in `app.event_namespace.token_to_sid`.

## Guidelines and Best Practices

### Keep Shared State Minimal

When defining a shared state, aim to keep it as minimal as possible. Only include the data and methods that need to be shared between clients. This helps reduce complexity and potential synchronization issues.

Linked states are always loaded into the tree for each event on each linked client and large states take longer to serialize and transmit over the network. Because linked states are regularly loaded in the context of many clients, they incur higher lock contention, so minimizing loading time also reduces lock waiting time for other clients.

### Prefer Backend-Only Vars in Shared State

A shared state should primarily use backend-only vars (prefixed with an underscore) to store shared data. Often, not all users of the shared state need visibility into all of the data in the shared state. Use computed vars to provide sanitized access to shared data as needed.

```python
from typing import Literal

class SharedGameState(rx.SharedState):
    # Sensitive user metadata stored in backend-only variable.
    _players: dict[str, Literal["X", "O"]] = {}

    @rx.event
    def make_move(self, x: int, y: int):
        # Identify users by client_token, never by arguments passed to the event.
        player_token = self.router.session.client_token
        player_piece = self._players.get(player_token)
```

```md alert warning
# Do Not Trust Event Handler Arguments

The client can send whatever data it wants to event handlers, so never rely on arguments passed to event handlers for sensitive information such as user identity or permissions. Always use secure identifiers like `self.router.session.client_token` to identify the client triggering the event.
```

### Expose Per-User Data via Private States

If certain data in the shared state needs to be personalized for each user, prefer to expose that data through computed vars defined in private states. This allows each user to have their own view of the shared data without exposing sensitive information to other users. It also reduces the amount of unrelated data sent to each client and improves caching performance by keeping each user's view cached in their own private state, rather than always recomputing the shared state vars for each user that needs to have their information updated.

Use async computed vars with `get_state` to access shared state data from private states.

```python
class UserGameState(rx.State):
    @rx.var
    async def player_piece(self) -> str | None:
        shared_state = await self.get_state(SharedGameState)
        return shared_state._players.get(self.router.session.client_token)
```

### Use Dynamic Routes for Linked Tokens

It is often convenient to define dynamic routes that include the linked token as part of the URL path. This allows users to easily share links to specific shared state instances. The dynamic route can use `on_load` to link the shared state to the token extracted from the URL.

```python
class SharedRoom(rx.SharedState):
    async def on_load(self):
        # `self.room_id` is the automatically defined dynamic route var.
        await self._link_to(self.room_id.replace("_", "-") or "default-room")


def room_page(): ...


app.add_route(
    room_page,
    path="/room/[room_id]",
    on_load=SharedRoom.on_load,
)
```
