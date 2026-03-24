# Other Methods

* `reset`: set all Vars to their default value for the given state (including substates).
* `get_value`: returns the value of a Var **without tracking changes to it**. This is useful
   for serialization where the tracking wrapper is considered unserializable.
* `dict`: returns all state Vars (and substates) as a dictionary. This is
  used internally when a page is first loaded and needs to be "hydrated" and
  sent to the client.

## Special Attributes

* `dirty_vars`: a set of all Var names that have been modified since the last
  time the state was sent to the client. This is used internally to determine
  which Vars need to be sent to the client after processing an event.
