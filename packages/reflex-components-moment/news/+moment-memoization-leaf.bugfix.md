Make `rx.moment` a `MemoizationLeaf` so a stateful date child is not memo-wrapped, which react-moment parsed like `moment({})` (today at midnight).
