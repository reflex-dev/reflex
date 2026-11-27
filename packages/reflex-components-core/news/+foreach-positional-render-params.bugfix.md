`rx.foreach` validates and names its render function's parameters by the positional ones only, so a bound method, a keyword-only parameter or `**kwargs` no longer counts as the index parameter.
