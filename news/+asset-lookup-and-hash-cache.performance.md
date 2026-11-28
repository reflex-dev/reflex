`rx.asset` hashes an asset file only when it changed since the last call, and a shared asset finds its calling module without `inspect.stack()`, which read the source of every frame on the stack.
