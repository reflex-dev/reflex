`format_prop` no longer raises `AttributeError` when given a dict (including a `Style`); it now formats the dict as a JavaScript object literal, rendering any nested vars as JavaScript.
