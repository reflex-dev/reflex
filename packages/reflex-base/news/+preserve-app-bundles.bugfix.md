Keep explicit `bundle_library()` registrations across compiler resets and registration-context forks without duplicates. Passing a component prebundles the rendered library imports of its entire tree, including children and component-valued props, before initial rendering. Subpaths are bundled without an unused package root; explicit subpath strings also work without registering the package root.

Invalid `bundle_library()` arguments now raise a clear `TypeError` directing callers to pass a library name string or a prototype component instance.

Preserve default exports when dynamic components use a bundled package root as well as a subpath.
