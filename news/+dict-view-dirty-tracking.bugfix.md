Mutating a nested value reached through `dict.values()` or `dict.items()` on a state var now marks the var dirty, so the UI and cached vars depending on it update.
