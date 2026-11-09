Runs can wait and repeat: a step returns `wait_for(step, timeout=..., on_timeout=...)` to
park until `deliver(...)` hands it an event, or `every(step, schedule)` to run again on an
interval or a `Cron("0 9 * * MON-FRI", "America/Los_Angeles")` expression.
