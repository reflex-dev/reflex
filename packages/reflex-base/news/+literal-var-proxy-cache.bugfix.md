Fix a `TypeError` when an event handler is called with a proxied state value (such as `self.other(self.items)`) after one was called with a proxied value of a different kind, such as a dict.
