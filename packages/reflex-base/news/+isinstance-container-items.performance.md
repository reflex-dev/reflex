Validating a list, set, tuple or dict assigned to a state var is faster: items whose type is exactly the declared item type no longer go through the full type check one by one.
