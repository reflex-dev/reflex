RFC: delta flushes take a `LockedRoot` capability minted only by `mint_locked_root`, making a flush without token-lock ownership a `TypeError` at the call site instead of a silent lost update.
