```diff
+ Stai cercando Pynecone? Sei nella repository giusto. Pynecone è stato rinominato in Reflex. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ App web performanti e personalizzabili in puro Python. Distribuisci in pochi secondi. ✨**
[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---
[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) |
[Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md)
---

## ⚙️ Installazione

Apri un terminale ed esegui (Richiede Python 3.9+):

```bash
pip install reflex
```

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

Ora puoi modificare il codice sorgente in `nome_app/nome_app.py`. Reflex offre aggiornamenti rapidi, così puoi vedere le tue modifiche istantaneamente quando salvi il tuo codice.

## 🫧 Esempio App

Esaminiamo un esempio: creare un'interfaccia utente per la generazione di immagini attorno a DALL·E. Per semplicità, chiamiamo semplicemente l'API OpenAI, ma potresti sostituirla con un modello ML eseguito localmente.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="Un wrapper frontend per DALL·E, mostrato nel processo di generazione di un'immagine." width="550" />
</div>

&nbsp;

Ecco il codice completo per crearlo, Tutto fatto in un unico file Python!

```python
import reflex as rx
import openai

openai.api_key = "TUA_API_KEY"

class State(rx.State):
    """Lo stato dell'app."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """Ottieni l'immagine dal prompt."""
        if self.prompt == "":
            return rx.window_alert("Prompt Vuoto")

        self.processing, self.complete = True, False
        yield
        response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
        self.image_url = response["data"][0]["url"]
        self.processing, self.complete = False, True
        
def index():
    return rx.center(
        rx.vstack(
            rx.heading("DALL·E"),
            rx.input(placeholder="Prompt Vuoto", on_blur=State.set_prompt),
            rx.button(
                "Genera Immagine",
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

# Aggiungi stato e pagina all'app.
app = rx.App()
app.add_page(index, title="reflex:DALL·E")
```

## Analizziamolo

### **Reflex UI**

Cominciamo con l'UI.

```python
def index():
    return rx.center(
        ...
    )
```

Questo `index` definisce il frontend dell'app.

Utilizziamo diversi componenti come `center`, `vstack`, `input`, e `button` per costruire il frontend. I componenti possono essere annidati gli uni negli altri per creare layout complessi. Puoi utilizzare argomenti chiave per stilizzarli con tutta la potenza di CSS.

Reflex offre [più di 60 componenti integrati](https://reflex.dev/docs/library) per aiutarti a iniziare. Stiamo attivamente aggiungendo più componenti ed è facile [creare i tuoi componenti](https://reflex.dev/docs/wrapping-react/overview/).

### **Stato (State)**

Reflex rappresenta la tua UI come una funzione del tuo stato.

```python
class State(rx.State):
    """Lo stato dell'app."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

Lo stato definisce tutte le variabili (chiamate vars) in un'app che possono cambiare e le funzioni che le cambiano.

Qui lo stato è composto da un `prompt` e `image_url`. Ci sono anche i booleani `processing` e `complete` per indicare quando mostrare l'andamento circolare e l'immagine.

### **Gestori di Eventi (Event Handlers)**

```python
def get_image(self):
    """Ottieni l'immagine dal prompt."""
    if self.prompt == "":
        return rx.window_alert("Prompt Vuoto")

    self.processing, self.complete = True, False
    yield
    response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
    self.image_url = response["data"][0]["url"]
    self.processing, self.complete = False, True
```

Dentro lo stato, definiamo funzioni chiamate gestori di eventi che cambiano le vars dello stato. I gestori di eventi sono il modo in cui possiamo modificare lo stato in Reflex. Possono essere chiamati in risposta alle azioni dell'utente, come fare clic su un pulsante o digitare in una casella di testo. Queste azioni vengono chiamate eventi.

La nostra app DALL·E ha un gestore di eventi, `get_image` con cui ottiene questa immagine dall'API OpenAI. Utilizzando `yield`  nel mezzo di un gestore di eventi farà sì che l'UI venga aggiornata. Altrimenti, l'UI verrà aggiornata alla fine del gestore di eventi.

### **Instradamento (Routing)**

Infine, definiamo la nostra app.

```python
app = rx.App()
```

Possiamo aggiungere una pagina dalla radice dell'app al componente dell'indice.Aggiungiamo anche un titolo che apparirà nell'anteprima della pagina/scheda del browser

```python
app.add_page(index, title="DALL-E")
```

Puoi creare un'app multi-pagina aggiungendo altre pagine.

## 📑 Risorse

<div align="center">

📑 [Documentazione](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Libreria Componenti](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Immagini](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Distribuzione](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>

## ✅ Stato

Reflex è stato lanciato nel dicembre 2022 con il nome Pynecone.

Da luglio 2023, siamo nella fase di Beta Pubblica.

-   :white_check_mark: **Alfa Pubblica**: Chiunque può installare e utilizzare Reflex. Potrebbero esserci dei problemi, ma stiamo lavorando per risolverli attivamente.
-   :large_orange_diamond: **Beta Pubblica**: Abbastanza stabile per casi d'uso non aziendali.
-   **Beta Hosting Pubblico**: _Opzionalmente_, distribuisci e ospita le tue app su Reflex! 
-   **Pubblico**: Reflex è pronto per la produzione. 

Reflex ha nuove versioni e funzionalità in arrivo ogni settimana! Assicurati di :star: mettere una stella e :eyes: osservare questa repository per rimanere aggiornato.

## Contribuire

Diamo il benvenuto a contributi di qualsiasi dimensione! Di seguito sono alcuni modi per iniziare nella comunità Reflex.

-   **Unisciti al nostro Discord**: Il nostro [Discord](https://discord.gg/T5WSbC2YtQ) è posto migliore per ottenere aiuto sul tuo progetto Reflex e per discutere come puoi contribuire.
-   **Discussioni su GitHub**: Un ottimo modo per parlare delle funzionalità che desideri aggiungere o di cose che creano confusione o necessitano chiarimenti.
-   **GitHub Issues**: Sono un ottimo modo per segnalare bug. Inoltre, puoi provare a risolvere un problema esistente e inviare un PR. 

Stiamo attivamente cercando collaboratori, indipendentemente dal tuo livello di abilità o esperienza.


## Licenza

Reflex è open-source e rilasciato sotto la [Licenza Apache 2.0](LICENSE).
