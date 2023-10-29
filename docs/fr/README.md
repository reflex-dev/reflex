```diff
+ Ha a Pynecone-t keresed, jó helyen jársz. A Pynecone átnevezésre került a Reflexre. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logó" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logó" width="300px">

<hr>

### **✨ Teljesítményorientált, testreszabható webalkalmazások tiszta Pythonban. Másodpercek alatt telepíthető. ✨**
[![PyPI verzió](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![tesztek](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![verziók](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Dokumentáció](https://img.shields.io/badge/Dokumentáció%20-Bemutató%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---
[Angol](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [français](https://github.com/reflex-dev/reflex/blob/main/docs/fr/README.md)
---
## ⚙️ Telepítés

Nyiss egy terminált, és futtasd (Szükséges Python 3.8+):

```bash
pip install reflex
```

## 🥳 Hozz létre az első alkalmazásodat

A `reflex` telepítése a `reflex` parancssori eszközt is telepíti.

Teszteld, hogy a telepítés sikeres volt, létrehozva egy új projektet. (Cseréld le `my_app_name`-t a projekt nevére):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

Ez a parancs egy sablon alkalmazást inicializál a könyvtáradban.

Fejlesztői módban futtathatod az alkalmazást:

```bash
reflex run
```

Látnod kell az alkalmazásodat a http://localhost:3000 címen.

Most módosíthatod a forráskódot a `my_app_name/my_app_name.py` fájlban. A Reflex gyors frissítéseket kínál, így azonnal láthatod a változásokat, amikor elmented a kódod.

## 🫧 Példa alkalmazás

Nézzünk meg egy példát: egy kép generálási felhasználói felület létrehozását DALL·E köré. Egyszerűség kedvéért csak az OpenAI API-t hívjuk meg, de ezt helyettesítheted egy helyileg futtatott gépi tanulási modelllel.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="Egy előlap DALL·E számára, amint egy kép generálásának folyamatában látható." width="550" />
</div>

&nbsp;

Itt találod a teljes kódot erre. Mindez egyetlen Python fájlban történik!

```python
import reflex as rx
import openai

openai.api_key = "AZ_API_KULCSOD"

class State(rx.State):
    """Az alkalmazás állapota."""
    prompt = ""
    image_url = ""
    feldolgozás = False
    kész = False

    def get_image(self):
        """Szerezz képet a promptból."""
        if self.prompt == "":
            return rx.window_alert("Üres bevitel")

        self.feldolgozás, self.kész = True, False
        yield
        válasz = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
        self.image_url = válasz["data"][0]["url"]
        self.feldolgozás, self.kész = False, True
        

def index():
    return rx.center(
        rx.vstack(
            rx.heading("DALL·E"),
            rx.input(placeholder="Adjon meg egy promptot", on_blur=State.set_prompt),
            rx.button(
                "Kép generálása",
                on_click=State.get_image,
                is_loading=State.feldolgozás,
                width="100%",
            ),
            rx.cond(
                State.kész,
                     rx.image(
                         src=State.image_url,
                         height="25em",
                         width="25em",
                    )
            ),
            padding="2em",
            shadow="lg",
            border_radius="lg",
        ),
        width="100%",
        height="100vh",
    )

# Add state and page to the app.
app = rx.App()
app.add_page(index, title="reflex:DALL·E")
app.compile()
```

## Szétszedjük ezt.

### **Reflex UI**

Kezdjük az UI-val.

```python
def index():
    return rx.center(
        ...
    )
```

Ez az `index` függvény meghatározza az alkalmazás frontendjét.

Különböző komponenseket használunk, mint például a `center`, `vstack`, `input` és `button`, hogy felépítsük a frontendet. A komponenseket egymásba lehet ágyazni,
hogy összetett elrendezéseket hozzunk létre. És a kulcsszavas argumentumokat használhatod a teljes CSS lehetőségekkel a stílusoláshoz.

A Reflextel [60+ beépített komponens](https://reflex.dev/docs/library) érhető el a kezdeti lépésekhez. Folyamatosan hozzáadunk további komponenseket, és könnyű [saját komponenseket létrehozni](https://reflex.dev/docs/advanced-guide/wrapping-react).

### **Állapot (State)**

A Reflex az UI-t a te állapotod függvényként reprezentálja.

```python
class State(rx.State):
    """Az alkalmazás állapota."""
    prompt = ""
    image_url = ""
    feldolgozás = False
    kész = False
```

Az állapot definiálja az alkalmazásban található változókat (más néven változókat), amelyek változhatnak, és azokat a függvényeket, amelyek megváltoztatják azokat.

Itt az állapot egy `prompt` és `image_url`. Továbbá vannak a `feldolgozás` és `kész` logikai változók, amelyek megmutatják, mikor kell körkörös előrehaladást és képet mutatni.

### **Eseménykezelők (Event Handlers)**

```python
def get_image(self):
    """Szerezz képet a promptból."""
    if self.prompt == "":
        return rx.window_alert("Üres bevitel")

    self.feldolgozás, self.kész = True, False
    yield
    válasz = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
    self.image_url = válasz["data"][0]["url"]
    self.feldolgozás, self.kész = False, True
```

Az állapoton belül olyan függvényeket definiálunk, amelyeket eseménykezelőknek nevezünk, és amelyek megváltoztatják az állapotváltozókat. Az eseménykezelők azok a módok, amelyeken keresztül módosíthatjuk az állapotot a Reflexben. Azokat hívjuk meg válaszként a felhasználói interakciókra, például a gombra kattintásra vagy szövegbevitelre. Ezeket az eseményeket nevezik.

A DALL·E alkalmazásunknak van egy eseménykezelője, a `get_image`, amely a képet szolgáltatja az OpenAI API-ból. A `yield` használata egy eseménykezelő közepén az UI frissítését eredményezi. Egyébként az UI a eseménykezelő végén frissül.

Végül is meghatározzuk az alkalmazásunkat.

```python
app = rx.App()
```

Hozzáadunk egy oldalt az alkalmazás gyökerezetéhez, amely a `index` komponenst használja. Továbbá hozzáadunk egy címet, amely a weboldal előnézetén és a böngésző lapfülön jelenik meg.

```python
app.add_page(index, title="DALL-E")
app.compile()
```

Több oldalas alkalmazást is létrehozhatsz a további oldalak hozzáadásával.

## 📑 Erőforrások

<div align="center">

📑 [Dokumentáció](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Komponens Könyvtár](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Galéria](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Bemutatás](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>

## ✅ Állapot

A Reflex 2022 decemberében indult a Pynecone nevű alkalmazással.

2023 júliusától a **Nyilvános Béta** fázisban vagyunk.

-   :white_check_mark: **Nyilvános Alfa**: Bárki telepítheti és használhatja a Reflexet. Lehetnek problémák, de aktívan dolgozunk a megoldásukon.
-   :large_orange_diamond: **Nyilvános Béta**: Stabil elég a vállalati használatra.
-   **Nyilvános Hosting Béta**: _Opcionálisan_ telepítheted és hoszthatod az alkalmazásaidat a Reflexen!
-   **Nyilvános**: A Reflex már termelésre kész.

A Reflexben minden héten új kiadások és funkciók érkeznek! Ne felejtsd el :star: megjelölni és :eyes: figyelni ezt a repository-t, hogy mindig naprakész legyél.

## Hozzájárulás

Bármekkora hozzájárulást üdvözölünk! Az alábbiakban néhány jó módja, hogyan csatlakozhatsz a Reflex közösséghez.

-   **Csatlakozz a Discordhoz**: A [Discord](https://discord.gg/T5WSbC2YtQ) a legjobb hely a Reflex projektjedhez való segítség megszerzéséhez és arról beszélgetéshez, hogyan tudsz hozzájárulni.
-   **GitHub Beszélgetések**: Kiváló módja annak, hogy beszélj olyan funkciókról, amelyeket hozzá akarsz adni, vagy olyan dolgokról, amik zavaróak / tisztázásra szorulnak.
-   **GitHub Hibajegyek**: Ezek kiváló módja a hibák bejelentésére. Ezenkívül megpróbálhatod megoldani egy már meglévő problémát és beküldheted a PR-t.

Aktívan keresünk hozzájárulókat, függetlenül a szinttől vagy a tapasztalattól.

## Licenc

A Reflex nyílt forráskódú és az [Apache License 2.0](LICENSE) alatt licencelve van.
