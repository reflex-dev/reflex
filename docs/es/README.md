```diff
+ ¿Buscando Pynecone? Estas en el repositorio correcto. Pynecone ha sido renomabrado a Reflex. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ Aplicaciones  web personalizables y eficaces en Python puro. Despliega tú aplicación en segundos. ✨**
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

Abra un terminal y ejecute (Requiere Python 3.7+):

```bash
pip install reflex
```

## 🥳 Crea tú primera aplicación

Al instalar `reflex` tambien se instala la herramienta de línea de comandos  `reflex`.

Compruebe que la instalación se ha realizado correctamente creando un nuevo proyecto. (Sustituye `my_app_name` por el nombre de tu proyecto):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

Este comando inicializa una aplicación de ejemplo (plantilla) en tu nuevo directorio. 

Puedes iniciar esta aplicación en modo de desarrollo:

```bash
reflex run
```

Debería ver su aplicación ejecutándose en http://localhost:3000.

Ahora puede modificar el código fuente en `my_app_name/my_app_name.py`. Reflex se actualiza rápidamente para que pueda ver los cambios al instante cuando guarde el código.


## 🫧 Ejemplo de una Aplicación

Veamos un ejemplo: crearemos una UI de generación de imágenes en torno a DALL-E. Para simplificar, solo llamamos a la API de OpenAI, pero podrías reeemplazar esto con un modelo ML ejecutado localmente.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

Aquí está el código completo para crear esto. ¡Todo esto se hace en un archivo de Python!

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

## Vamos a desglosarlo.

### **Reflex UI**

Empezemos por la interfaz de usuario (UI).

```python
def index():
    return rx.center(
        ...
    )
```

Esta función `index` define el frontend de la aplicación.

Utilizamos diferentes componentes como `center`, `vstack`, `input`, y `button` para construir el frontend. Los componentes pueden anidarse unos dentro de otros para crear diseños complejos. Además, puedes usar argumentos (keyword args) para darles estilo con toda la potencia de CSS.

Reflex viene con [mas de 60+ componentes incorporados](https://reflex.dev/docs/library) para ayudarle a empezar. Estamos añadiendo activamente más componentes y es fácil [crear sus propios componentes](https://reflex.dev/docs/advanced-guide/wrapping-react).

### **State**

Reflex representa su UI en función de su estado (State).

```python
class State(rx.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

El estado (State) define todas las variables (llamadas vars) de una aplicación que pueden cambiar y las funciones que las modifican.

Aquí el estado (State) se compone de `prompt` e `image_url`. También están los booleanos `processing` y `complete` para poder indicar cuándo mostrar el progreso circular y la imagen.

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

Dentro del estado (State), definimos funciones llamadas "event handlers" que cambian los 'state vars'. Event handlers, son la manera que podemos modificar el 'state' en Reflex. Pueden ser activados en respuesta a las acciones del usuario, como hacer clic en un botón o escribir en un cuadro de texto. Estas acciones se llaman eventos 'events'.

Nuestra aplicación DALL·E. tiene un controlador de eventos "event handler", `get_image` que recibe esta imagen del OpenAI API. El uso de `yield` en medio de un controlador de eventos "event handler" hará que la UI se actualice. De lo contrario, la interfaz se actualizará al final del controlador de eventos "event handler".

### **Routing**

Por último, definimos nuestra app.

```python
app = rx.App()
```

Añadimos una página desde la raíz (root) de la aplicación al componente de índice (index). También agregamos un título que se mostrará en la vista previa de la página/pestaña del navegador.

```python
app.add_page(index, title="DALL-E")
app.compile()
```

Puedes crear una aplicación multipágina añadiendo más páginas.

## 📑 Recursos

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Biblioteca de Componentes](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Galería](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Hospedaje](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>





## ✅ Estatus

Reflex se lanzó en Diciembre de 2022 con el nombre Pynecone.

A partir de julio de 2023, nos encontramos en la etapa de  **Beta Pública**.

-   :white_check_mark: **Alpha Pública**: Cualquier persona puede instalar y usar Reflex. Puede haber problemas, pero estamos trabajando activamente para resolverlos.
-   :large_orange_diamond: **Beta Pública**: Suficientemente estable para casos de uso no empresariales.
-   **Beta de Hospedaje Público**: ¡_Opcionalmente_, despliega y hospeda tus aplicaciónes en Reflex!
-   **Público**: Reflex está listo para producción.

¡Reflex tiene nuevas versiones y características que se lanzan cada semana! Aseguraté de darnos una :star: estrella y :eyes: revisa este repositorio para mantenerte actualizado.

## Contribuyendo

¡Aceptamos contribuciones de cualquier tamaño! A continuación encontrará algunas buenas formas de iniciarse en la comunidad Reflex.

-   **Únete a nuestro  Discord**: Nuestro [Discord](https://discord.gg/T5WSbC2YtQ) es el mejor lugar para obtener ayuda en su proyecto Reflex y discutir cómo puedes contribuir.
-   **Discusiones de GitHub**: Una excelente manera de hablar sobre las características que deseas agregar o las cosas que te resusltan confusas o necesitan aclaración.
-   **GitHub Issues**: Las incidencias son una forma excelente de informar de errores. Además, puedes intentar resolver un problema exixtente y enviar un PR.

Buscamos colaboradores, sin importar su nivel o experiencia.

## Licencia

Reflex es de código abierto y está licenciado bajo la [Apache License 2.0](LICENSE).
