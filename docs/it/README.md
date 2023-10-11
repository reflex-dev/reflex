```diff
+ Stai cercando Pynecone? Sei nel repository giusto. Pynecone è stato rinominato in Reflex. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ App web performanti e personalizzabili in puro Python. Pubblica in pochi secondi. ✨**
[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---
[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) |
[Italian](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md)
---
<!-- TODO -->
## ⚙️ Installazione

Apri un terminale ed esegui (Richiede Python 3.7+):

```bash
pip install reflex
```
<!-- TODO -->
## 🥳 Crea la tua prima app

Installando `reflex` si installa anche lo strumento da riga di comando `reflex`.

Verifica che l'installazione sia stata eseguita correttamente creando un nuovo progetto. (Sostituisci `nome_app` con il nome del tuo progetto):

```bash
mkdir nome_app
cd nome_app
reflex init
```

Questo comando inizializza un'app template nella tua nuova directory.

Puoi eseguire questa app in modalità sviluppo con:

```bash
reflex run
```

Dovresti vedere la tua app in esecuzione su http://localhost:3000.

Ora puoi modificare il codice sorgente in `my_app_name/my_app_name.py`. Reflex offre aggiornamenti rapidi, così puoi vedere le tue modifiche istantaneamente quando salvi il tuo codice.

<!-- TODO -->
## 🫧 Esempio di App

Let's go over an example: creating an image generation UI around DALL·E. For simplicity, we just call the OpenAI API, but you could replace this with an ML model run locally.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

Ecco il codice completo per crearlo, Tutto fatto in un unico file Python!

```python
import reflex as rx
import openai

openai.api_key = "YOUR_API_KEY"

class State(rx.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """Get the image from the prompt."""
        if self.prompt == "":
            return rx.window_alert("Prompt Empty")

        self.processing, self.complete = True, False
        yield
        response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
        self.image_url = response["data"][0]["url"]
        self.processing, self.complete = False, True
        

def index():
    return rx.center(
        rx.vstack(
            rx.heading("DALL·E"),
            rx.input(placeholder="Enter a prompt", on_blur=State.set_prompt),
            rx.button(
                "Generate Image",
                on_click=State.get_image,
                is_loading=State.processing,
                width="100%",
            ),
            rx.cond(
                State.complete,
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
<!-- TODO -->
## Analizziamolo

### **Reflex UI**

Let's start with the UI.

```python
def index():
    return rx.center(
        ...
    )
```

This `index` function defines the frontend of the app.

We use different components such as `center`, `vstack`, `input`, and `button` to build the frontend. Components can be nested within each other
to create complex layouts. And you can use keyword args to style them with the full power of CSS.

Reflex comes with [60+ built-in components](https://reflex.dev/docs/library) to help you get started. We are actively adding more components, and it's easy to [create your own components](https://reflex.dev/docs/advanced-guide/wrapping-react).

### **State**

Reflex represents your UI as a function of your state.

```python
class State(rx.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

The state defines all the variables (called vars) in an app that can change and the functions that change them.

Here the state is comprised of a `prompt` and `image_url`. There are also the booleans `processing` and `complete` to indicate when to show the circular progress and image.

### **Event Handlers**

```python
def get_image(self):
    """Get the image from the prompt."""
    if self.prompt == "":
        return rx.window_alert("Prompt Empty")

    self.processing, self.complete = True, False
    yield
    response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
    self.image_url = response["data"][0]["url"]
    self.processing, self.complete = False, True
```

Within the state, we define functions called event handlers that change the state vars. Event handlers are the way that we can modify the state in Reflex. They can be called in response to user actions, such as clicking a button or typing in a text box. These actions are called events.

Our DALL·E. app has an event handler, `get_image` to which get this image from the OpenAI API. Using `yield` in the middle of an event handler will cause the UI to update. Otherwise the UI will update at the end of the event handler.

### **Routing**

Finally, we define our app.

```python
app = rx.App()
```

We add a page from the root of the app to the index component. We also add a title that will show up in the page preview/browser tab.

```python
app.add_page(index, title="DALL-E")
app.compile()
```

You can create a multi-page app by adding more pages.

<!-- TODO -->
## 📑 Risorse

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Component Library](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Immagini](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Distribuzione](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>

<!-- TODO -->
## ✅ Stato

Reflex è stato lanciato nel dicembre 2022 con il nome Pynecone.

Da luglio 2023, siamo nella fase di Beta Pubblica.

-   :white_check_mark: **Public Alpha**: Chiunque può installare e utilizzare Reflex. Potrebbero esserci dei problemi, ma stiamo lavorando per risolverli attivamente.
-   :large_orange_diamond: **Public Beta**: Abbastanza stabile per casi d'uso non aziendali.
-   **Public Hosting Beta**: _Opzionalmente_, distribuisci e ospita le tue app su Reflex! 
-   **Public**: Reflex è pronto per la produzione. 

Reflex ha nuove versioni e funzionalità in arrivo ogni settimana! Assicurati di :star: mettere una stella e :eyes: osservare questa repository per rimanere aggiornato.

## Contribuire

Diamo il benvenuto a contributi di qualsiasi dimensione! Di seguito sono alcuni modi per iniziare nella comunità Reflex.

-   **Unisciti al nostro Discord**: Il nostro [Discord](https://discord.gg/T5WSbC2YtQ) è posto migliore per ottenere aiuto sul tuo progetto Reflex e per discutere come puoi contribuire.
-   **Discussioni su GitHub**: Un ottimo modo per parlare delle funzionalità che desideri aggiungere o di cose che creano confusione o necessitano chiarimenti.
-   **GitHub Issues**: Sono un ottimo modo per segnalare bug. Inoltre, puoi provare a risolvere un problema esistente e inviare un PR. 

Stiamo attivamente cercando collaboratori, indipendentemente dal tuo livello di abilità o esperienza.


## Licenza

Reflex è open-source e rilasciato sotto la [Licenza Apache 2.0](LICENSE).