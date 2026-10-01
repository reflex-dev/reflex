`reflex_workflow.wake` no longer returns while a step the worker took is still running, so a host that suspends when it returns does not stop that step midway.
