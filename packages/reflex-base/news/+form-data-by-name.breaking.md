Remove the `getRefValue` and `getRefValues` helpers from `$/utils/state`; forms no longer read control values through refs. Read `ref.current` directly in custom code that used them.
