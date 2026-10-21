# reflex-i18n

Internationalization (i18n) for [Reflex](https://reflex.dev) apps.

- `rx.t(...)` — translate static component strings, resolved client-side from
  per-locale catalogs (only the active locale is shipped to the client).
- `gettext` / `ngettext` / `pgettext` — translate dynamic (state) content
  server-side; translated computed vars retranslate automatically on a locale
  switch.
- `I18nPlugin` — configure locales and wire compilation.

```python
import reflex as rx
from reflex_i18n import I18nPlugin, t, gettext as _


class State(rx.State):
    @rx.var
    def greeting(self) -> str:
        return _("Hello")


def index():
    return rx.text(t("Welcome"))


app = rx.App()
app.add_page(index)
```

```python
# rxconfig.py
config = rx.Config(
    app_name="myapp",
    plugins=[I18nPlugin(locales=["en", "de"], default_locale="en")],
)
```

Translations live in `locales/{locale}.po`.
