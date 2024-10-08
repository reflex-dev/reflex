```diff
+ Suchst du nach Pynecone? Dann bist du hier in der richtigen Repository. Pynecone wurde in Reflex umbenannt. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ Performante, anpassbare Web-Apps in purem Python. Bereitstellung in Sekunden. ✨**
[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentation](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---

[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [Español](https://github.com/reflex-dev/reflex/blob/main/docs/es/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md)

---

# Reflex

Reflex ist eine Bibliothek, mit der man Full-Stack-Web-Applikationen in purem Python erstellen kann.

Wesentliche Merkmale:
* **Pures Python** - Schreibe dein Front- und Backend in Python, es gibt also keinen Grund, JavaScript zu lernen.
* **Volle Flexibilität** - Reflex ist einfach zu handhaben, kann aber auch für komplexe Anwendungen skaliert werden.
* **Sofortige Bereitstellung** - Nach dem Erstellen kannst du deine App mit einem [einzigen Befehl](https://reflex.dev/docs/hosting/deploy-quick-start/) bereitstellen oder auf deinem eigenen Server hosten.

Auf unserer [Architektur-Seite](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) erfahren Sie, wie Reflex unter der Haube funktioniert.

## ⚙️ Installation

Öffne ein Terminal und führe den folgenden Befehl aus (benötigt Python 3.9+):

```bash
pip install reflex
```

## 🥳 Erstelle deine erste App

Die Installation von `reflex` installiert auch das `reflex`-Kommandozeilen-Tool.

Teste, ob die Installation erfolgreich war, indem du ein neues Projekt erstellst. (Ersetze `my_app_name` durch deinen Projektnamen):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

Dieser Befehl initialisiert eine Vorlage in deinem neuen Verzeichnis.

Du kannst diese App im Entwicklungsmodus ausführen:

```bash
reflex run
```

Du solltest deine App unter http://localhost:3000 laufen sehen.

Nun kannst du den Quellcode in `my_app_name/my_app_name.py` ändern. Reflex hat schnelle Aktualisierungen, sodass du deine Änderungen sofort siehst, wenn du deinen Code speicherst.


## 🫧 Beispiel-App

Lass uns ein Beispiel durchgehen: die Erstellung einer Benutzeroberfläche für die Bildgenerierung mit [DALL·E](https://platform.openai.com/docs/guides/images/image-generation?context=node). Zur Vereinfachung rufen wir einfach die [OpenAI-API](https://platform.openai.com/docs/api-reference/authentication) auf, aber du könntest dies auch durch ein lokal ausgeführtes ML-Modell ersetzen.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="Eine Benutzeroberfläche für DALL·E, die im Prozess der Bildgenerierung gezeigt wird." width="550" />
</div>

&nbsp;

Hier ist der komplette Code, um dies zu erstellen. Das alles wird in einer Python-Datei gemacht!


  
```python
import reflex as rx
import openai

openai_client = openai.OpenAI()


class State(rx.State):
    """Der Zustand der App."""

    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """Hole das Bild aus dem Prompt."""
        if self.prompt == "":
            return rx.window_alert("Prompt Empty")

        self.processing, self.complete = True, False
        yield
        response = openai_client.images.generate(
            prompt=self.prompt, n=1, size="1024x1024"
        )
        self.image_url = response.data[0].url
        self.processing, self.complete = False, True


def index():
    return rx.center(
        rx.vstack(
            rx.heading("DALL-E", font_size="1.5em"),
            rx.input(
                placeholder="Enter a prompt..",
                on_blur=State.set_prompt,
                width="25em",
            ),
            rx.button(
                "Generate Image", 
                on_click=State.get_image,
                width="25em",
                loading=State.processing
            ),
            rx.cond(
                State.complete,
                rx.image(src=State.image_url, width="20em"),
            ),
            align="center",
        ),
        width="100%",
        height="100vh",
    )

# Füge Zustand und Seite zur App hinzu.
app = rx.App()
app.add_page(index, title="Reflex:DALL-E")
```





## Schauen wir uns das mal genauer an.

<div align="center">
<img src="docs/images/dalle_colored_code_example.png" alt="Erläuterung der Unterschiede zwischen Backend- und Frontend-Teilen der DALL-E-App." width="900" />
</div>


### **Reflex-UI**

Fangen wir mit der Benutzeroberfläche an.

```python
def index():
    return rx.center(
        ...
    )
```

Diese `index`-Funktion definiert das Frontend der App.

Wir verwenden verschiedene Komponenten wie `center`, `vstack`, `input` und `button`, um das Frontend zu erstellen. Komponenten können ineinander verschachtelt werden, um komplexe Layouts zu erstellen. Und du kannst Schlüsselwortargumente verwenden, um sie mit der vollen Kraft von CSS zu stylen.

Reflex wird mit [über 60 eingebauten Komponenten](https://reflex.dev/docs/library) geliefert, die dir den Einstieg erleichtern. Wir fügen aktiv weitere Komponenten hinzu, und es ist einfach, [eigene Komponenten zu erstellen](https://reflex.dev/docs/wrapping-react/overview/).

### **State**

Reflex stellt deine Benutzeroberfläche als Funktion deines Zustands dar.

```python
class State(rx.State):
    """Der Zustand der App."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

```

Der Zustand definiert alle Variablen (genannt Vars) in einer App, die sich ändern können, und die Funktionen, die sie ändern.

Hier besteht der Zustand aus einem `prompt` und einer `image_url`. Es gibt auch die Booleans `processing` und `complete`, um anzuzeigen, wann der Button deaktiviert werden soll (während der Bildgenerierung) und wann das resultierende Bild angezeigt werden soll.

### **Event-Handler**

```python
def get_image(self):
    """Hole das Bild aus dem Prompt."""
    if self.prompt == "":
        return rx.window_alert("Prompt Empty")

    self.processing, self.complete = True, False
    yield
    response = openai_client.images.generate(
        prompt=self.prompt, n=1, size="1024x1024"
    )
    self.image_url = response.data[0].url
    self.processing, self.complete = False, True
```

Innerhalb des Zustands definieren wir Funktionen, die als Event-Handler bezeichnet werden und die Zustand-Variablen ändern. Event-Handler sind die Art und Weise, wie wir den Zustand in Reflex ändern können. Sie können als Reaktion auf Benutzeraktionen aufgerufen werden, z.B. beim Klicken auf eine Schaltfläche oder bei der Eingabe in ein Textfeld. Diese Aktionen werden als Ereignisse bezeichnet.

Unsere DALL-E.-App hat einen Event-Handler, `get_image`, der dieses Bild von der OpenAI-API abruft. Die Verwendung von `yield` in der Mitte eines Event-Handlers führt zu einer Aktualisierung der Benutzeroberfläche. Andernfalls wird die Benutzeroberfläche am Ende des Ereignishandlers aktualisiert.

### **Routing**

Schließlich definieren wir unsere App.

```python
app = rx.App()
```

Wir fügen der Indexkomponente eine Seite aus dem Stammverzeichnis der Anwendung hinzu. Wir fügen auch einen Titel hinzu, der in der Seitenvorschau/Browser-Registerkarte angezeigt wird.

```python
app.add_page(index, title="DALL-E")
```

Du kannst eine mehrseitige App erstellen, indem du weitere Seiten hinzufügst.

## 📑 Ressourcen

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Komponentenbibliothek](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Galerie](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Bereitstellung](https://reflex.dev/docs/hosting/deploy-quick-start)  &nbsp;   

</div>


## ✅ Status

Reflex wurde im Dezember 2022 unter dem Namen Pynecone gestartet.

Ab Februar 2024 befindet sich unser Hosting-Service in der Alpha-Phase! In dieser Zeit kann jeder seine Apps kostenlos bereitstellen. Siehe unsere [Roadmap](https://github.com/reflex-dev/reflex/issues/2727), um zu sehen, was geplant ist.

Reflex hat wöchentliche Veröffentlichungen und neue Features! Stelle sicher, dass du dieses Repository mit einem :star: Stern markierst und :eyes: beobachtest, um auf dem Laufenden zu bleiben.

## Beitragende

Wir begrüßen Beiträge jeder Größe! Hier sind einige gute Möglichkeiten, um in der Reflex-Community zu starten.

-   **Tritt unserem Discord bei**: Unser [Discord](https://discord.gg/T5WSbC2YtQ) ist der beste Ort, um Hilfe für dein Reflex-Projekt zu bekommen und zu besprechen, wie du beitragen kannst.
-   **GitHub-Diskussionen**: Eine großartige Möglichkeit, über Funktionen zu sprechen, die du hinzugefügt haben möchtest oder Dinge, die verwirrend sind/geklärt werden müssen.
-   **GitHub-Issues**: [Issues](https://github.com/reflex-dev/reflex/issues) sind eine ausgezeichnete Möglichkeit, Bugs zu melden. Außerdem kannst du versuchen, ein bestehendes Problem zu lösen und eine PR einzureichen.

Wir suchen aktiv nach Mitwirkenden, unabhängig von deinem Erfahrungslevel oder deiner Erfahrung. Um beizutragen, sieh dir [CONTRIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md) an.


## Vielen Dank an unsere Mitwirkenden:
<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>

## Lizenz

Reflex ist Open-Source und lizenziert unter der [Apache License 2.0](LICENSE).
