A component `id` written as an f-string around a Var gets the same ref name in every run: `format_ref` replaces the marker holding the Var's hash with a digest of its expression and type.
