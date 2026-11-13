Fixed a client's events stalling for good after a long backlog of its queued events (over about a thousand) was cancelled at once; the backlog is now skipped without hitting Python's recursion limit.
