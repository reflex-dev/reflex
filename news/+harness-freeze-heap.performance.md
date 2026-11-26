`AppHarness` freezes the objects the started app built, so a full garbage collection during an integration test no longer walks the whole compiled app and stalls the backend for seconds.
