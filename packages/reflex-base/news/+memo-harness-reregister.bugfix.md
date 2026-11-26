Fix `@rx.memo` definitions from a module shared by several `AppHarness` apps in one test process going missing from later apps, which left their imports unresolved at runtime.
