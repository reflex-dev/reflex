Awaiting an event handler in an API route or other request code outside `app.modify_state` now raises `EventHandlerTypeError` instead of running it on one state shared by every caller.
