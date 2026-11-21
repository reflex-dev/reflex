Import functions from a `.js` or `.ts` file in your app's package like a Python module, and call them from event triggers and event handlers. The module is bundled with the app and its npm imports are installed; see [JavaScript Modules](https://reflex.dev/docs/api-reference/browser-javascript/#javascript-modules).

```python
from my_app.scripts.party import celebrate

rx.button("🎉", on_click=celebrate(200, "results"))
```
