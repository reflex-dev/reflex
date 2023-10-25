```diff
+ ¿Buscas a Pynecone? Estas en el repositorio correcto. Pynecone ha sido renomabrado a Reflex. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ Aplicaciones de web performantes y perzonalizables en solo Python. Lanza tu aplicación en solo segundos. ✨**
[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---
[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [Español] (https://github.com/reflex-dev/reflex/blob/main/docs/es/README.md)
---
## ⚙️ Instalación

Abre un terminal y instala reflex (Requiere Python 3.7+):

```bash
pip install reflex
```

## 🥳 Crea tu primer aplicación

Al instalar `reflex` tambien se instalara la herramienta de command line `reflex`.

Comprueba que la instalación fue exitosa al crear un nuevo proyecto. (Reemplaza `my_app_name` con el nombre de tu proyecto):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

Esto inicializara la plantilla de la aplicación en tu nuevo directorio. 

You can run this app in development mode:

```bash
reflex run
```

You should see your app running at http://localhost:3000.

Now you can modify the source code in `my_app_name/my_app_name.py`. Reflex has fast refreshes so you can see your changes instantly when you save your code.


## 🫧 Ejemplo de una Aplicación

Miremos un ejemplo: crear un UI de generación de imágenes usando DALL·E. Para simplicidad, usaremos el API de OpenAI , pero también pudes usar un modelo ML local.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

Aqui esta el codigo completo para crear esto. ¡Todo esta hecho un solo archivo de Python!

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

## Repasemos esto.

### **Reflex UI**

Comenzemos con el interfaz de usario (UI).

```python
def index():
    return rx.center(
        ...
    )
```

Esta función `index` define el frontend de la aplicación.

Usamos diferentes componentes como `center`, `vstack`, `input`, y `button` para crear el frontend. Los componentes pueden ser anidados dentro de cada uno para crear un disposición complejo. Tambien puedes usar keyword args para estilizarlos con el poder completo de CSS.

Reflex viene con [mas de 60+ componentes incorporados](https://reflex.dev/docs/library) para ayudarte comenzar. Continuamos agregando mas componentes, y es facil de [crear tus propios componentes](https://reflex.dev/docs/advanced-guide/wrapping-react).

### **State**

Reflex representa tu UI com una función de tu estado (State).

```python
class State(rx.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

El estado defines all the variables (called vars) in an app that can change and the functions that change them.

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

Dentro del estado, definos funciones que se llaman 'event handlers' que cambian los 'state vars'. Event handlers son la manera que podemos modificar el 'state' en Reflex. Pueden ser activadas en respuesta a las acciones del usuario, como seleccionando un botón or escribiendo dentro de un 'text box'. Estas acciones se llaman 'events'.

Nuestra aplicación DALL·E. tiene un event handler, `get_image` que recibe esta imagen del OpenAI API. Usando `yield` en medio de un event handler causara que el UI se actualize. Por lo demás, el UI se actualizara al fin de el event handler.

### **Routing**

Al fin, vamos a definir nuestro app.

```python
app = rx.App()
```

We add a page from the root of the app to the index component. Tambien agregaremos un titulo que show up in the page preview/browser tab.

```python
app.add_page(index, title="DALL-E")
app.compile()
```

Puedes crear un app con multiples paginas al agregar mas paginas como esta.

## 📑 Recursos

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Component Library](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Gallery](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>





## ✅ Status

Reflex launched in December 2022 with the name Pynecone.

As of July 2023, we are in the **Public Beta** stage.

-   :white_check_mark: **Public Alpha**: Anyone can install and use Reflex. There may be issues, but we are working to resolve them actively.
-   :large_orange_diamond: **Public Beta**: Stable enough for non-enterprise use-cases.
-   **Public Hosting Beta**: _Optionally_, deploy and host your apps on Reflex!
-   **Public**: Reflex is production ready.

Reflex has new releases and features coming every week! Make sure to :star: star and :eyes: watch this repository to stay up to date.

## Contributing

We welcome contributions of any size! Below are some good ways to get started in the Reflex community.

-   **Join Our Discord**: Our [Discord](https://discord.gg/T5WSbC2YtQ) is the best place to get help on your Reflex project and to discuss how you can contribute.
-   **GitHub Discussions**: A great way to talk about features you want added or things that are confusing/need clarification.
-   **GitHub Issues**: These are an excellent way to report bugs. Additionally, you can try and solve an existing issue and submit a PR.

We are actively looking for contributors, no matter your skill level or experience.

## License

Reflex is open-source and licensed under the [Apache License 2.0](LICENSE).
