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

`default_locale` is the language your source strings are written in; pages are
prerendered in it, so it is also the `<html lang>` unless you set
`rx.App(html_lang=...)`. Translations live in `.po` files under `locales/`
(configurable with `catalog_dir=`, a path relative to the app root or an absolute
one, e.g. a directory inside your package). `rx.i18n.configured_locales()`
returns the configured locales, and `rx.i18n.source_locale()` the default one.

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

A message is either singular or plural: gettext keys catalog entries by their
msgid, so using the same text both with and without `plural` raises an error.
Give one of them a `context` (below) if you need both.

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

### Text defined at import time

A module-level constant or an enum label is created before any visitor has a
locale, so translating it right there would freeze it in the default language.
Mark it with `N_` (short for `gettext_noop`) instead: it returns the text
unchanged, but `reflex i18n extract` adds it to the catalogs. Translate the
value where it is shown, with `rx.t` in a component or `gettext` in state:

```python
from reflex_i18n import N_, gettext as _

EMPTY_CART = N_("Your cart is empty")


def cart_hint():
    return rx.text(rx.t(EMPTY_CART))


class CartState(rx.State):
    hint: str = ""

    @rx.event
    def clear(self):
        self.hint = _(EMPTY_CART)
```

### Outside an event

Event handlers and computed vars translate into their visitor's locale
automatically. Code that runs without a visitor (a background job, a scheduled
report, a message sent to someone else) has no locale until you set one with
`rx.i18n.use_locale`. `gettext` and the `format_*` helpers below follow it:

```python
import datetime

from reflex_i18n import format_date, gettext as _, use_locale


def monthly_report_title(user_locale: str, month: datetime.date) -> str:
    with use_locale(user_locale):
        return _("Report for {month}").format(month=format_date(month))
```

`use_locale` raises a `ValueError` for a locale the plugin does not list.
`rx.i18n.get_locale()` returns the locale in effect, or `None` outside any.

## Translated data

Some text is data rather than part of your app: a product name or a
description entered once per language, stored for example as a
`{locale: text}` dict. `rx.i18n.pick` shows it in the visitor's language:

```python
class ProductState(rx.State):
    description: dict[str, str] = {"en": "Sparkling water", "de": "Mineralwasser"}


def product_card():
    return rx.text(
        rx.i18n.pick(ProductState.description),
        lang=rx.i18n.pick_locale(ProductState.description),
    )
```

When there is no text in the visitor's locale, the server and the browser fall
back in the same order: a text in the same language (`de-AT` takes `de`), the
default locale, the `fallback_locale`, the other configured locales, and
finally any text there is. `rx.i18n.pick_locale` returns the language actually
shown, e.g. for the element's `lang`. The browser re-picks instantly when the
locale changes.

On the server, `pick_translation(texts)` picks for the current visitor (or for
the locale `use_locale` set), and `fallback_chain(locale)` returns the order
itself, each locale followed by its own language (`de-AT`, `de`) and spelled
the way `normalize_locale` spells stored keys. Trying the keys in that order,
e.g. in an SQL `COALESCE`, picks what `pick_translation` picks as long as the
keys are normalized languages without a region; a key like `de-CH` is found
only where the chain names it. `normalize_locale` spells a language
tag the way the plugin does, which keeps stored keys consistent.

## Formatting numbers and dates

Numbers, currencies, percentages and dates are formatted differently per locale
(`1,234.5` vs `1.234,5`, `7/18/2026` vs `18.07.2026`). There are two ways to
format, mirroring static vs dynamic content.

**In components (client-side).** `rx.i18n.number` / `currency` / `percent` /
`date` / `time` / `datetime` format a value in the browser using `Intl`, and
reformat instantly when the locale changes:

```python
import datetime


class PriceState(rx.State):
    quantity: float = 3.5
    total: float = 41.9
    tax_rate: float = 0.19
    created: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)


def price_row():
    return rx.hstack(
        rx.text(rx.i18n.number(PriceState.quantity, max_fraction_digits=2)),
        rx.text(rx.i18n.currency(PriceState.total, "EUR")),
        rx.text(rx.i18n.percent(PriceState.tax_rate, max_fraction_digits=1)),
        rx.text(rx.i18n.date(PriceState.created, length="long")),
    )
```

Curated options — `min_fraction_digits`, `max_fraction_digits`, `grouping`,
`compact`, and `length` (`"short"`/`"medium"`/`"long"`/`"full"`) — cover the
common cases; pass `options={...}` for raw
[`Intl`](https://developer.mozilla.org/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat)
options. A `None` value (or a date that does not parse) renders as empty text.

**In state (server-side).** Use the `format_*` helpers, e.g. when building a
translated string. Like `gettext`, a computed var using one reformats when the
locale changes:

```python
from reflex_i18n import gettext as _, format_currency


class CartState(rx.State):
    total: float = 0.0

    @rx.var
    def summary(self) -> str:
        return _("Total: {amount}").format(amount=format_currency(self.total, "EUR"))
```

`rx.i18n.locale` exposes the active locale as a var, e.g. to drive
`rx.moment(PriceState.created, locale=rx.i18n.locale)`.

Languages and weekdays have names in every locale too. `rx.i18n.language_name`
names a language tag (`"pt-BR"` shows as "Portugiesisch (Brasilien)" to a German
visitor) and `rx.i18n.weekday` names a weekday, counted from 0 for Monday like
`datetime.date.weekday()`, with `length="long"`, `"short"` or `"narrow"`. Their
server-side counterparts are `format_language` and `format_weekday`.

Two caveats:

- **Naive datetimes client-side** are shown in the visitor's local time zone (a
  datetime with no offset has no absolute meaning). For a fixed zone, use a
  timezone-aware datetime, pass `options={"timeZone": "..."}`, or format
  server-side with `format_datetime`. (Plain dates and times are unambiguous and
  render correctly.)
- Python's `f"{value:,}"` formatting on a numeric var stays `en-US` by design;
  use `rx.i18n.number` for locale-aware output.

## Detecting and switching the locale

On a visitor's first load, the locale is negotiated from their browser's
`Accept-Language`, falling back to `fallback_locale`, which is `default_locale`
unless you set it. Once they pick a language it is remembered in a cookie.
Pages render in `default_locale` first. For a visitor in another language the
app stays hidden from its first client render until that language's messages
have loaded, or for at most 3 seconds, after which it shows the source text.
Text prerendered into a page's HTML shows in `default_locale` until the app
hydrates.

The source language is not always the best guess for a visitor whose browser
asks for none of your locales. An app written in German that also ships English
can send everyone else to English:

```python
I18nPlugin(locales=["de", "en"], default_locale="de", fallback_locale="en")
```

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

Once a page has loaded, the browser follows the locale the server holds for it.
A backend handler can therefore pick the language itself, e.g. the one stored in
a user's profile after they log in:

```python
class AuthState(rx.State):
    @rx.event
    async def on_login(self):
        user = await load_user(self.router.session.client_token)
        return rx.i18n.set_locale(user.language)
```

`rx.i18n.language_switcher()` is a prebuilt switcher with one `<a>` per locale,
labelled with each language's own name ("English", "Deutsch").
Here it switches static and dynamic content just like `set_locale`, and becomes
a set of real crawlable links once URL routing is on (below).

Locales are BCP 47 language tags written with hyphens (`en`, `pt-BR`,
`zh-Hant`) — they double as URL segments and `Intl` tags, so the underscore
spelling is rejected.

## URL-based locales & SEO

The cookie-based default keeps every language on the same URL. That's ideal for
apps (dashboards, authenticated tools), but bad for **SEO**: search engines see
only the default language, because the locale lives in a cookie/state rather
than the URL.

For public sites, opt into **URL-based locales** by giving the plugin a routing
strategy:

```python
from reflex_i18n import I18nPlugin, PathPrefixRouting

config = rx.Config(
    app_name="mysite",
    deploy_url="https://mysite.com",  # used for absolute hreflang hrefs
    plugins=[
        I18nPlugin(
            locales=["en", "de", "fr"],
            default_locale="en",
            routing=PathPrefixRouting(),  # /de/..., /fr/...
        )
    ],
)
```

You write each page **once**; the plugin fans it out into a concrete route per
locale. With the default `PathPrefixRouting(default_at_root=True)`:

- `/pricing` serves the default locale, `/de/pricing` and `/fr/pricing` the
  others (use `default_at_root=False` to prefix every locale).
- Each route is prerendered and carries reciprocal
  `<link rel="alternate" hreflang="...">` (plus `x-default` and `canonical`) in
  its `<head>`, so all languages are discoverable and indexable.
- The locale comes from the **URL**, not a cookie — so each language URL renders
  its own content for crawlers.

Here the switcher's links become real per-locale URLs (crawlers follow them
instead of a cookie swap); you can also build your own with
`rx.i18n.locale_url`:

```python
rx.i18n.language_switcher()  # prebuilt <a> links
rx.link("Deutsch", href=rx.i18n.locale_url("de", "/pricing"))
```

For a switcher with markup of your own, `rx.i18n.alternate_url(locale)` is the
current page's URL in a locale, kept in step with the page the visitor is on:

```python
def language_menu():
    return rx.el.ul(
        *(
            rx.el.li(rx.el.a(label, href=rx.i18n.alternate_url(locale)))
            for locale, label in (("en", "English"), ("de", "Deutsch"))
        ),
        class_name="language-menu",
    )
```

Links between your pages should stay in the visitor's language.
`rx.i18n.localized_url` builds a route's URL in the locale the current page is
built in (see below), so one layout serves every locale:

```python
# /pricing on English pages, /de/pricing on German ones
rx.link(_("Pricing"), href=rx.i18n.localized_url("/pricing"))
```

### Translated paths

A page can have a path of its own in another locale, e.g. a blog post whose
slug is translated. Give the paths in the page's context; its route stays the
default locale's path:

```python
app.add_page(
    news,
    route="/neuigkeiten",
    context={"i18n_paths": {"en": "/news"}},  # served at /en/news
)
```

The `hreflang` links, the language switcher, `alternate_url`, `locale_url` and
`localized_url` all use the translated path. Only static routes can have one.

A visitor or crawler may still ask for a page's path in another locale, e.g. an
old link to `/en/neuigkeiten`. `rx.i18n.path_redirects()` lists such paths
with the address each should redirect to, for your web server's permanent
redirects (`/en/neuigkeiten` to `/en/news`, `/news` to `/neuigkeiten`). It is
filled once the app's routes are registered, e.g. in a plugin's `post_build`.

### Translating while a page is built

With URL routing every route serves exactly one locale, and its page function
runs in it: `rx.i18n.get_locale()` returns the route's locale and `gettext`
translates into it. Text translated this way is plain text in that route's
code, prerendered like any other, so a page that needs no client-side switching
can use `gettext` instead of `rx.t`:

```python
from reflex_i18n import gettext as _


def pricing():
    return rx.heading(_("Pricing"))  # "Preise" on /de/pricing
```

A `@rx.memo` component is compiled once for all locales, outside any page:
use `rx.t` inside it, or pass the translated text and `localized_url` links in
as props.

A page's head is translated the same way: a plain string `title`,
`description` and meta tag `content` is a message, translated into each
route's locale. Mark them with `N_` so `reflex i18n extract` finds them:

```python
from reflex_i18n import N_

app.add_page(
    pricing,
    title=N_("Pricing"),
    description=N_("Plans for every team"),
    meta=[{"property": "og:title", "content": N_("Pricing")}],
)
```

Notes:

- A head text given as `rx.t` resolves in the default locale (the document
  head is outside the per-route locale provider); give plain strings instead.
- `default_at_root=True` (the default) is recommended for SEO: the default
  locale keeps clean canonical URLs (`/pricing`). With `default_at_root=False`
  every locale is prefixed; visiting an unprefixed path redirects to its
  default-locale address (`/pricing` → `/en/pricing`), and its canonical link
  points there.
- App routes must not start with a configured locale (e.g. a `/de/...` page of
  your own while `de` is configured): those URLs are reserved for the generated
  locale routes, and compilation fails with a clear error.
- The sitemap (`SitemapPlugin`) lists every locale's URL of a page, each
  naming all of them as `xhtml:link` alternates, as its `hreflang` links do.
- Each locale route prerenders that language's content, `hreflang`,
  `canonical` and `<html lang>`/`dir`. Unprefixed pages of the default locale
  keep the app-wide `rx.App(html_lang=...)`, which defaults to `default_locale`.

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
# (new messages added, translations preserved, removed ones marked obsolete;
# a file with no changed message is left as it is).
reflex i18n extract

# Create a fresh catalog for a new locale.
reflex i18n init es

# Fail (non-zero exit) if any non-default locale has untranslated or fuzzy
# messages (the default locale holds the source msgids). Useful as a CI check.
reflex i18n check
```

`extract` scans the package holding the app module (`myapp` for
`myapp.myapp`, `site.web` for an `app_module_import` of `site.web.app`), so a
second app living in a subpackage of a larger one extracts its own messages
only.

A typical workflow: run `reflex i18n extract` after adding or changing strings,
fill in the `msgstr` values in each locale's `.po` file, and add
`reflex i18n check` to CI to catch missing translations.

A message that a locale shows in the source language on purpose, e.g. a legal
text you do not translate yet, carries the `read-only` flag in that locale's
catalog. `reflex i18n check` accepts it untranslated, `extract` keeps the flag,
and [Weblate](https://weblate.org) keeps such a string from being edited:

```po
#, read-only
msgid "Privacy policy"
msgstr ""
```

When its source text changes, the entry starts over without the flag, so
`check` asks again.

By default the CLI writes catalogs as `pybabel` does: lines wrapped at 76
characters and each entry's `#:` comment naming every source line using it.
For long texts this makes small edits noisy in review, as an edit above a
message changes its line numbers. Two plugin options change that:

```python
I18nPlugin(
    locales=["en", "de"],
    catalog_width=0,  # never wrap: one line per message
    catalog_locations="file",  # name source files, not lines ("none": neither)
)
```

A translation tool writing the same catalogs should use the same wrapping
(Weblate: the component's "Long lines wrapping" setting).

## Translating a library

A package that other apps install marks its text the same way: `rx.t` in
components, `gettext` in state, `N_` for constants. It does not need the apps
using it to translate. Without an `I18nPlugin`, `rx.t` renders the source text
and the `rx.i18n` formatters format in English, as the server-side `format_*`
helpers do outside any locale.

A package can ship its translations too: one `.po` file per locale in a
`locales/` directory inside the package (make sure its distribution includes
them). Manage them from the package's repository, no app needed:

```bash
reflex i18n init de --package my_lib   # create my_lib/locales/de.po
reflex i18n extract --package my_lib   # update the catalogs after changing text
reflex i18n check --package my_lib     # fail on untranslated messages (CI)
```

Extraction finds `gettext`-family calls, `N_` markers and `rx.t` calls with
literal text. Text computed at runtime is invisible to it, so mark it with `N_`
where it is defined.

An app uses a package's translations by listing the package:

```python
I18nPlugin(locales=["de", "en"], default_locale="de", catalog_packages=["my_lib"])
```

Its catalogs then translate the package's messages in the browser and on the
server, and `reflex i18n extract` leaves the package's sources out of the app's
own catalogs, also when it is a subpackage of the app's. A message the app's own
code uses stays in the app's catalogs, even if the package uses it too.

## How it works

- `rx.t` compiles to a client-side lookup. At build time Reflex generates one
  small JavaScript catalog per locale, and the browser loads **only the active
  language** on demand.
- `gettext` runs on the server against the locale resolved for the current
  client, so no translation data for other languages is sent to the browser.
- Missing translations always fall back to the source text, so an incomplete
  catalog degrades gracefully rather than showing blank strings.
