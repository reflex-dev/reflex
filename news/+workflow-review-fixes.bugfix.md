Fixed the remaining defects from an external review, each reproduced first.

An operator-supplied result now goes through the same strict serialization as a handler's. Memory kept a live `Decimal` no other store could hold, while SQLite raised a bare "not JSON serializable" from inside `json.dumps` — one input, three behaviours, none of them saying what to do. All three now refuse it identically, naming the fix.

CLI run-id prefixes are refused rather than guessed when the database holds more runs than a single scan covers. The resolver reads the newest 10,000 runs, so on a larger store a prefix could look unique while another run just outside the window shared it — and `cancel` or `complete` would then act on the wrong run.

`Retry(multiplier=...)` refuses `nan` and `inf`. Every comparison against `nan` is False, so the `< 1.0` guard let both through, and the backoff they produced scheduled a step for a moment that never arrives.

The cron search horizon now spans a skipped leap century: 2100 is not a leap year, so the gap from 2096 to 2104 is eight years and `0 0 29 2 *` reported no occurrence at all. A month and day-of-month pairing that no year can satisfy (`0 0 30 2 *`) is now a definition error instead of a schedule that parses and silently never fires — unless a weekday restriction gives the date a second way to match, which cron's OR rule allows.

Scheduled occurrences dropped past the catch-up cap are counted on `MetricsObserver` and the OpenTelemetry observer. They have no run to carry history, so a log line was their only trace, and "the nightly job silently stopped a week ago" is exactly what a counter is for.
