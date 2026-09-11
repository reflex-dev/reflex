Keep explicit `bundle_library()` registrations across compiler resets and registration-context forks without duplicates. Passing a component prebundles its rendered library imports before initial rendering, including subpaths without an unused package root; explicit subpath strings also work without registering the package root.

Invalid `bundle_library()` arguments now raise a clear `TypeError` directing callers to pass a library name string or a prototype component instance.
