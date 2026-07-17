```python exec
import reflex as rx
```

# Internationalization (i18n)

Reflex supports translating your app into multiple languages through the
[`reflex-i18n`](https://pypi.org/project/reflex-i18n/) package. It covers the
two kinds of text in an app:

- **Static content** — literal strings in your components (labels, buttons,
  headings), translated on the client with `rx.t(...)`.
- **Dynamic content** — strings produced by your state (messages, formatted
  values), translated on the server with `gettext`.

Only the visitor's active language is ever sent to the browser, so adding more
locales does not bloat what each user downloads.

## Installation

```bash
pip install reflex-i18n
```

Then enable it by adding the `I18nPlugin` to your `rxconfig.py`, listing the
locales you support:

```python
import reflex as rx
from reflex_i18n import I18nPlugin

config = rx.Config(
    app_name="myapp",
    plugins=[
        I18nPlugin(locales=["en", "de", "fr"], default_locale="en"),
    ],
)
```

`default_locale` is the language your source strings are written in. Translations
live in `.po` files under `locales/` (configurable with `catalog_dir=`).

## Static content with `rx.t`

Wrap literal component strings in `rx.t`. The text you pass is the message in
your default locale; at runtime it is looked up in the active locale's catalog,
falling back to the original text when a translation is missing.

```python
def index():
    return rx.vstack(
        rx.heading(rx.t("Welcome")),
        rx.button(rx.t("Sign in")),
    )
```

### Interpolating values

Use `{name}` placeholders and pass the values as keyword arguments. Values may
be plain data **or state vars** — they interpolate on the client, so they stay
reactive:

```python
class State(rx.State):
    name: str = "Ada"


def greeting():
    return rx.text(rx.t("Hello, {name}!", name=State.name))
```

### Plurals

Pass a `plural` form and a `count`. The correct form is chosen using the active
locale's plural rules, and `count` is also available as the `{count}`
placeholder:

```python
class CartState(rx.State):
    items: int = 1


def cart_label():
    return rx.text(rx.t("{count} item", plural="{count} items", count=CartState.items))
```

### Disambiguating with context

When the same source text needs different translations in different places,
give it a `context`:

```python
rx.t("Open", context="verb")  # "to open something"
rx.t("Open", context="status")  # "currently open"
```

## Dynamic content with `gettext`

For text generated in your state, import `gettext` (conventionally aliased `_`)
and call it wherever you build the string. It translates into the current
visitor's locale.

The best place is a **computed var**: it re-runs and re-sends the translated
string automatically when the locale changes.

```python
from reflex_i18n import gettext as _


class DashboardState(rx.State):
    unread: int = 0

    @rx.var
    def status(self) -> str:
        return _("You have {n} new messages").format(n=self.unread)
```

You can also translate at the moment you produce a one-off message, such as in
an event handler:

```python
from reflex_i18n import gettext as _, ngettext


class OrderState(rx.State):
    message: str = ""

    @rx.event
    def checkout(self):
        self.message = _("Order confirmed")

    @rx.event
    def summarize(self, n: int):
        self.message = ngettext("{n} order", "{n} orders", n).format(n=n)
```

`ngettext(singular, plural, n)` handles plurals and `pgettext(context, message)`
handles context, mirroring `rx.t`.

Note: translate at render time (in a computed var) or at the moment you emit a
message. A translated string stored in a plain var earlier will not
re-translate on its own when the locale changes.

## Detecting and switching the locale

On a visitor's first load, the locale is negotiated from their browser's
`Accept-Language`, falling back to `default_locale`. Once they pick a language
it is remembered in a cookie.

Switch languages with `rx.i18n.set_locale`, which updates both static and
dynamic content:

```python
def language_switcher():
    return rx.hstack(
        rx.button("English", on_click=rx.i18n.set_locale("en")),
        rx.button("Deutsch", on_click=rx.i18n.set_locale("de")),
    )
```

Static (`rx.t`) content updates instantly; dynamic (state) content updates on
the next server round-trip.

## Translation catalogs

Translations are standard gettext `.po` files, one per locale, under `locales/`:

```text
locales/
  en.po
  de.po
  fr.po
```

A catalog entry pairs the source text (`msgid`) with its translation
(`msgstr`):

```po
msgid "Welcome"
msgstr "Willkommen"

msgid "{count} item"
msgid_plural "{count} items"
msgstr[0] "{count} Artikel"
msgstr[1] "{count} Artikel"
```

You don't write these by hand — the CLI generates and maintains them.

## The `reflex i18n` CLI

Once the plugin is configured, three commands manage your catalogs:

```bash
# Scan the app for rx.t and gettext calls and update every locale's .po file
# (new messages added, translations preserved, removed ones marked obsolete).
reflex i18n extract

# Create a fresh catalog for a new locale.
reflex i18n init es

# Fail (non-zero exit) if any locale has untranslated or fuzzy messages.
# Useful as a CI check.
reflex i18n check
```

A typical workflow: run `reflex i18n extract` after adding or changing strings,
fill in the `msgstr` values in each locale's `.po` file, and add
`reflex i18n check` to CI to catch missing translations.

## How it works

- `rx.t` compiles to a client-side lookup. At build time Reflex generates one
  small JavaScript catalog per locale, and the browser loads **only the active
  language** on demand.
- `gettext` runs on the server against the locale resolved for the current
  client, so no translation data for other languages is sent to the browser.
- Missing translations always fall back to the source text, so an incomplete
  catalog degrades gracefully rather than showing blank strings.
