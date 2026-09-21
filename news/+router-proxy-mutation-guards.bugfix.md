Fix nested router mutations bypassing background-task locks and read-only state proxies. Writes through `self.router` now enforce the same mutation guards as direct state-field access.
