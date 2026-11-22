Import functions from a `.js`, `.ts`, `.jsx` or `.tsx` file in your app's package like a Python module, and call them from event triggers and event handlers; the module is bundled with the app and its npm imports are installed. A name the module does not export as a function fails the compile, or, if first used inside an event handler, is reported in the browser; see [JavaScript Modules](https://reflex.dev/docs/api-reference/browser-javascript/#javascript-modules).

```python
import reflex as rx

from my_app.scripts.party import celebrate

rx.button("🎉", on_click=celebrate(200, "results"))
```
