`rx.step(name, fn, ...)` records substep results durably inside a durable handler, so retries and crash recoveries replay completed side effects instead of repeating them.
