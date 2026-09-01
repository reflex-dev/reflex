Fixes four more defects found by adversarial audit, including a handler that let `CancelledError` escape killing the worker, and a redelivered webhook cancelling the very run it deduplicated to.
