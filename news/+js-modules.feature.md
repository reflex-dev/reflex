Import functions from a `.js` or `.ts` file in your app's package like a Python module, and call them from event triggers and event handlers. The module is bundled with the app, its npm imports are installed, and the compile fails with the fix when you use a name it does not export as a function; see [JavaScript Modules](https://reflex.dev/docs/api-reference/browser-javascript/#javascript-modules).

```python
from my_app.scripts.party import celebrate

rx.button("🎉", on_click=celebrate(200, "results"))
```
