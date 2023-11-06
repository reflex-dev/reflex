```diff
+ ¿Buscas a Pynecone? Estas en el repositorio correcto. Pynecone ha sido renomabrado a Reflex. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ Aplicaciones  web potentes y perzonalizables utilizando solo Python. Lanza tu aplicación en segundos. ✨**
[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---
[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [Español](https://github.com/reflex-dev/reflex/blob/main/docs/es/README.md)
---
## ⚙️ Instalación

Abre un terminal e instala reflex (Requiere Python 3.7+):

```bash
pip install reflex
```

## 🥳 Crea tu primer aplicación

Al instalar `reflex` tambien se instalará la herramienta de linea de comandos  `reflex`.

Comprueba que la instalación fué exitosa creando un nuevo proyecto. (Reemplaza `my_app_name` con el nombre de tu proyecto):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

Esto inicializará la plantilla de la aplicación en tu nuevo directorio. 

Puedes iniciar la aplicación en modo desarrollador:

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

El estado (state) define todas las variables (vars) en una aplicación que pueden cambiar y las funciones que las cambian.

Aquí el estado se compone de un `prompt` y de un `image_url`. También están los booleanos `processing` y `complete` para poder indicar cuándo mostrar el progreso circular y la imagen.

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

Agregamos una página desde la raíz (root) de la aplicación hasta al componente de índice. También agregaremos un título que aparece en la pestaña de vista previa de la página o en la pestaña del navegador web.

```python
app.add_page(index, title="DALL-E")
app.compile()
```

Puedes crear un app con multiples paginas al agregar mas paginas como esta.

## 📑 Recursos

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Biblioteca de Componentes](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Galería](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Hospedaje](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>





## ✅ Estatus

Reflex lanzo en Diciembre 2022 con el nombre Pynecone.

Desde Julio 2023, estamos en el estatus de **Beta Publica**.

-   :white_check_mark: **Alfa Publico**: Cualquiera puede instalar y utilizar Reflex. Puede que haya problemas, pero estamos trabajando para resolverlos.
-   :large_orange_diamond: **Beta Publica**: Suficientemente estable para casos de uso no empresariales.
-   **Betea Publica de Alojamiento**: _Opcionalmente_, lanza y hospeda tus aplicaciónes en Reflex!
-   **Publico**: Reflex está listo para la producción.

¡Reflex tiene nuevos lanzamientos y funciones cada semana! Asedurate de darnos una :star: estrella y :eyes: revisa este repositorio para estar al día.

## Contribuyendo

¡Agradecemos contribuciones de cualquier tamaño! Abajo hay algunas buenas formas de comenzar en la comunidad Reflex.

-   **Únete a nuestro  Discord**: Nuestro [Discord](https://discord.gg/T5WSbC2YtQ) es el mejor lugar para obtener ayuda en su proyecto Reflex y discutir cómo puedes contribuir.
-   **Discusiones de GitHub**: Una excelente manera de hablar sobre las características que deseas agregar o cosas que son confusas o que necesitan aclaración.
-   **GitHub Issues**: These are an excellent way to report bugs. Additionally, you can try and solve an existing issue and submit a PR.

Buscamos colaboradores, sin importar su nivel de habilidad o experiencia.

## Licencia

Reflex es de código abierto y tiene la licencia [Apache License 2.0](LICENSE).
