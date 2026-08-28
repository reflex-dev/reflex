Fixed an edge in the new fatal-error interrupt handling where a task failing after the with-body raised its own exception could deliver a stray SIGINT to unrelated caller code.
