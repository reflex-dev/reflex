Assigning over a state var's field through its state class raises `TypeError`; change its default with the field's `set_default` instead, such as `State.__fields__["count"].set_default(10)`.
