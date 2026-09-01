`rx.Singleton(mode="skip")` now enforces "one active run per key" inside the admitting transaction, so concurrent starts can no longer both be admitted.
