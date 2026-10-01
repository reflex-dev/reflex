In a background task on a substate, in-place changes to a mutable var inherited from a parent state (like `self.items.append(...)`) are now sent to the client and persisted.
