```diff
+ Hûn li Pynecone-ê digerin? Hûn di depoya rast de ne. Pynecone navê xwe kir Reflex. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ Di Python-a safî de sepanên web-ê yên bikêrhatî, xwerû. Di nav çirkeyan de bicîh bikin. ✨**

[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---

[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [Kurmancî](https://github.com/reflex-dev/reflex/blob/main/docs/ku/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [Español](https://github.com/reflex-dev/reflex/blob/main/docs/es/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md)

---

## ⚙️ Sazkirin

Termînalek vekin û bimeşînin (Python 3.8+ pêdivî ye):

```bash
pip install reflex
```

## 🥳 Sepana xweya yekem biafirînin

`Dema ku hûn refleksê saz dikin, hûn amûra rêzika fermanê ya `reflex` jî saz dikin.

Ji bo ceribandina ku sazkirin serketî bû, projeyek nû biafirînin. ("my_app_name" bi navê projeyê veguherîne):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

Bi vê fermanê, ew di pelrêça ku we nû çêkiriye de serîlêdanek şablonê diafirîne.

Hûn dikarin sepana xwe di moda pêşkeftinê de dest pê bikin:

```bash
reflex run
```

Sepana we li ser http://localhost:3000 dimeşe.

Naha hûn dikarin koda çavkaniyê di riya `my_app_name/my_app_name.py` de biguherînin. Reflex xwedan taybetmendiyek nûvekirina bilez e ji ber vê yekê gava ku hûn koda xwe hilînin hûn dikarin tavilê guhertinên xwe bibînin.

## 🫧 Sepanekê mînak

Ka em li ser mînakeke derbas bikin: Ka em bi karanîna [DALL·E](https://platform.openai.com/docs/guides/images/image-generation?context=node) serîlêdanek renderkirinê binivîsin. Ji bo sadebûnê, em tenê [OpenAI API] (https://platform.openai.com/docs/api-reference/authentication) bikar tînin, lê hûn dikarin vê bi modelek fêrbûna makîneya herêmî ya ku bi rê ve dibe biguhezînin.
&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

Li vir koda bêkêmasî ye ku vê yekê biafirîne. Her tişt bi tenê yek pelê Python tê amadekirin!
```python
import reflex as rx
import openai

openai.api_key = "YOUR_API_KEY"

class State(rx.State):
    """Rewşa sepane."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """Ji promptê wêne bistîne."""
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

# Rûpel û rewşê li sepanê zêde bikin.
app = rx.App()
app.add_page(index, title="reflex:DALL·E")
```

## Werin em wê bi hûrgulî binêrin

### **Reflex UI**

Ka em bi UI (Pêşrû) dest pê bikin.

```python
def index():
    return rx.center(
        ...
    )
```

Ev fonksiyona `index` frontend-ê diyar dike.

Em hêmanên cihêreng ên wekî `center`, `vstack`, `input`, û `button` bikar tînin da ku pêşrû biafirînin. Em dikarin hêmanan di hundurê hev de hêlîn bikin da ku sêwiranên tevlihev biafirînin. Her weha hûn dikarin argumanên kilîdbêje bikar bînin da ku wan bi hêza tevahî ya CSS-ê şêwaz bikin.

Reflex [60+ hêmanên çêkirî] (https://reflex.dev/docs/library) vedihewîne da ku karê we hêsantir bike. Em bi awayekî çalak hêmanên nû lê zêde dikin û ew pir hêsan e ku [beşên xwe biafirînin] (https://reflex.dev/docs/wrapping-react/overview/).

### **Rewş (State)**
reflex rewşa pêşrûya we wekî fonksiyonekî nîşan dike.

```python
class State(rx.State):
    """Rewşa sepanê."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

Rewş (State), di nav sepaneke de hemû guhêrokan dikarin werin guhartin (ji bona wan dibêjin vars) û fonksiyona ku wan dugeherîne saz dike.

Li vir rewş ji `prompt` û `image_url` ve çêdibe. Û pêşketina çerx û ê kengî wenê were nîşankirin bêjin bikarhêner booleanên `processing` Û `complete` hene.

### **Rêvekera Bûyerê (Event Handlers)**

```python
def get_image(self):
    """Ji prompt-ê wenê bistînin."""
    if self.prompt == "":
        return rx.window_alert("Prompt Empty")

    self.processing, self.complete = True, False
    yield
    response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
    self.image_url = response["data"][0]["url"]
    self.processing, self.complete = False, True
```

Di nav rewşê de, fonksiyonên bi navê kadkarên bûyeran ku guhêrokên rewş diguhêre saz dikin. Rêvekera Bûyeran, di nav reflexê de dihêle ku em rewş biguhêrin. Ew dikarin di bersiva kiryarên bikarhêner mîna pêlkirina bişkokekê an jî  nivîsandina di qutiyeke nivîsê de de bêne gazî kirin. Ji bona wan dibêjin bûyer.

Pêkanîna meya DALL·E xwedî rêvekera bûyerê ye, `get_image`, ku wêneya hatî çêkirin ji API-ya OpenAI-ê vedigire. Bikaranîna `yield` di nîvê rêvekera bûyerê de dihêle ku UI were nûve kirin. Wekî din, UI dê di dawiya birêvebirê bûyerê de were nûve kirin.

### **Beralîkirin (Routing)**

Veca emê sepana xwe rave bikin.

```python
app = rx.App()
```

Em rûpelek ji hêmana indexê li pelrêça root ya serîlêdana xwe zêde dikin. Em sernavek jî lê zêde dikin ku dê di tabloya pêşdîtina rûpelê/gerokê de xuya bibe.

```python
app.add_page(index, title="DALL-E")
```

Hûn dikarin bi lê zêdekirina rûpelan serîlêdanek pir-rûpel biafirînin.

## 📑 Çalak

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Component Library](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Gallery](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>





## ✅ Rewş

Reflex, di berfenbara 2022-yan de bi navê Pynecone derketibû hole.
Em ji Tîrmeha 2023-an ve di qonaxa **Beta Giştî ** de ne.

- :white_check_mark: **Public Alpha**: Her kes dikare ku reflex dabixe Û serê bixebite. Belkî pirsgirêk hebin lê em li ser wan dixebitin.
- :large_orange_diamond: **Public Beta**: Ji bo dozên karanîna ne-karsaziyê têra xwe stabîl.
- **Public Hosting Beta**: _Optionally_, Bi Reflex re sepanên xwe bicîh bikin û mêvandar bikin!
- **Public**: Reflex guncaw e.

Guhertoyên nû û taybetmendiyên Reflex her hefte digihîjin! Ji bîr nekin ku :star: stêrk bidin û vê repoyê bişopînin :eyes: da ku rojane bimînin.

## Alîkarî

Em pêşwaziya beşdariyên ji her mezinahiyê dikin! Li jêr çend awayên ku hûn beşdarî civata Reflex bibin hene.

- **Dîscorda me**: [Discord'umuz](https://discord.gg/T5WSbC2YtQ), Reflex cîhê çêtirîn e ku hûn di projeya xwe de alîkariyê bistînin û nîqaş bikin ka hûn çawa dikarin beşdar bibin.
- **GitHub Discussions**: Ew rêgezek girîng e ku meriv li ser taybetmendiyên ku hûn dixwazin lê zêde bikin an tiştên ku tevlihev in ku hewceyê zelalkirinê ne biaxivin.
- **GitHub Issues**: [Issues](https://github.com/reflex-dev/reflex/issues) Ji bo raporkirina xeletiyan rêyek hêja ye. Her weha hûn dikarin biceribînin û pirsgirêkek heyî çareser bikin û PR (Daxwazên vekişandinê) bişînin.

Ne asta jêhatîbûn an ezmûna we be, em li mirovan digerin ku bi rengek çalak tevkariyê bikin. Ji bo beşdariyê, hûn dikarin rêbernameya beşdariya me bişopînin.: [CONTIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md)

## Hemî saxiya beşdaran:

<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>

## Lîsans

Reflex çalakekê azad e û di bin [Apache License 2.0](LICENSE) ve hatiye lîsanskirin.
