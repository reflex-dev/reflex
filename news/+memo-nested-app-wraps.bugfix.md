Fix `@rx.memo` components dropping the app wraps their body requires. Providers
requested by a nested child, or through var data as `rx.upload`'s
`UploadFilesProvider` is, now reach the app root — so a provider-backed
component behaves the same inside a memo as inlined into the page.
