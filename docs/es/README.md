```diff
+ ¿Buscando Pynecone? Estás en el repositorio correcto. Pynecone ha sido renombrado a Reflex. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ Aplicaciones web personalizables y eficaces en Python puro. Despliega tu aplicación en segundos. ✨**
[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![Pruebas](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![Versiones](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentación](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---

[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [Español](https://github.com/reflex-dev/reflex/blob/main/docs/es/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md)

---

# Reflex

Reflex es una biblioteca para construir aplicaciones web full-stack en Python puro.

Características clave:
* **Python puro** - Escribe el frontend y backend de tu aplicación en Python, sin necesidad de aprender JavaScript.
* **Flexibilidad total** - Reflex es fácil para empezar, pero también puede escalar a aplicaciones complejas.
* **Despliegue instantáneo** - Después de construir, despliega tu aplicación con un [solo comando](https://reflex.dev/docs/hosting/deploy-quick-start/) u hospédala en tu propio servidor.

Consulta nuestra [página de arquitectura](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) para aprender cómo funciona Reflex en detalle.

## ⚙️ Instalación

Abra un terminal y ejecute (Requiere Python 3.9+):

```bash
pip install reflex
```

## 🥳 Crea tu primera aplicación

Al instalar `reflex` también se instala la herramienta de línea de comandos `reflex`.

Compruebe que la instalación se ha realizado correctamente creando un nuevo proyecto. (Sustituye `my_app_name` por el nombre de tu proyecto):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

Este comando inicializa una plantilla en tu nuevo directorio.

Puedes iniciar esta aplicación en modo de desarrollo:

```bash
reflex run
```

Debería ver su aplicación ejecutándose en http://localhost:3000.

Ahora puede modificar el código fuente en `my_app_name/my_app_name.py`. Reflex se actualiza rápidamente para que pueda ver los cambios al instante cuando guarde el código.


## 🫧 Ejemplo de una Aplicación

Veamos un ejemplo: crearemos una UI de generación de imágenes en torno a [DALL·E](https://platform.openai.com/docs/guides/images/image-generation?context=node). Para simplificar, solo llamamos a la [API de OpenAI](https://platform.openai.com/docs/api-reference/authentication), pero podrías reemplazar esto con un modelo ML ejecutado localmente.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="Un envoltorio frontend para DALL·E, mostrado en el proceso de generar una imagen." width="550" />
</div>

&nbsp;

Aquí está el código completo para crear esto. ¡Todo esto se hace en un archivo de Python!

```python
import reflex as rx
import openai

openai_client = openai.OpenAI()

class State(rx.State):
    """El estado de la aplicación"""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """Obtiene la imagen desde la consulta."""
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

# Agrega el estado y la pagina a la aplicación
app = rx.App()
app.add_page(index, title="Reflex:DALL-E")
```

## Vamos a analizarlo.

<div align="center">
<img src="https://github.com/reflex-dev/reflex/blob/main/docs/images/dalle_colored_code_example.png?raw=true" alt="Explicando las diferencias entre las partes del backend y frontend de la aplicación DALL-E." width="900" />
</div>

### **Reflex UI**

Empezemos por la interfaz de usuario (UI).

```python
def index():
    return rx.center(
        ...
    )
```

Esta función `index` define el frontend de la aplicación.

Utilizamos diferentes componentes como `center`, `vstack`, `input`, y `button` para construir el frontend. Los componentes pueden anidarse unos dentro de otros para crear diseños complejos. Además, puedes usar argumentos de tipo keyword para darles estilo con toda la potencia de CSS.

Reflex viene con [mas de 60 componentes incorporados](https://reflex.dev/docs/library) para ayudarle a empezar. Estamos añadiendo activamente más componentes y es fácil [crear sus propios componentes](https://reflex.dev/docs/wrapping-react/overview/).

### **Estado**

Reflex representa su UI como una función de su estado (State).

```python
class State(rx.State):
    """El estado de la aplicación"""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```

El estado (State) define todas las variables (llamadas vars) de una aplicación que pueden cambiar y las funciones que las modifican.

Aquí el estado se compone de `prompt` e `image_url`. También están los booleanos `processing` y `complete` para indicar cuando se deshabilite el botón (durante la generación de la imagen) y cuando se muestre la imagen resultante.

### **Manejadores de Evento**

```python
def get_image(self):
    """Obtiene la imagen desde la consulta."""
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

Dentro del estado, definimos funciones llamadas manejadores de eventos que cambian las variables de estado. Los Manejadores de Evento son la manera que podemos modificar el estado en Reflex. Pueden ser activados en respuesta a las acciones del usuario, como hacer clic en un botón o escribir en un cuadro de texto. Estas acciones se llaman eventos.

Nuestra aplicación DALL·E tiene un manipulador de eventos, `get_image` que recibe esta imagen del OpenAI API. El uso de `yield` en medio de un manipulador de eventos hará que la UI se actualice. De lo contrario, la interfaz se actualizará al final del manejador de eventos.

### **Enrutamiento**

Por último, definimos nuestra app.

```python
app = rx.App()
```

Añadimos una página desde la raíz (root) de la aplicación al componente de índice (index). También agregamos un título que se mostrará en la vista previa de la página/pestaña del navegador.

```python
app.add_page(index, title="DALL-E")
```

Puedes crear una aplicación multipágina añadiendo más páginas.

## 📑 Recursos

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Librería de componentes](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Galería](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Despliegue](https://reflex.dev/docs/hosting/deploy-quick-start)  &nbsp;   

</div>


## ✅ Estado

Reflex se lanzó en diciembre de 2022 con el nombre de Pynecone.

¡Desde febrero de 2024, nuestro servicio de alojamiento está en fase alfa! Durante este tiempo, cualquiera puede implementar sus aplicaciones de forma gratuita. Consulta nuestra [hoja de ruta](https://github.com/reflex-dev/reflex/issues/2727) para ver qué está planeado.

¡Reflex tiene nuevas versiones y características cada semana! Asegúrate de :star: marcar como favorito y :eyes: seguir este repositorio para mantenerte actualizado.

## Contribuciones

¡Aceptamos contribuciones de cualquier tamaño! A continuación encontrará algunas buenas formas de iniciarse en la comunidad Reflex.

-   **Únete a nuestro  Discord**: Nuestro [Discord](https://discord.gg/T5WSbC2YtQ) es el mejor lugar para obtener ayuda en su proyecto Reflex y discutir cómo puedes contribuir.
-   **Discusiones de GitHub**: Una excelente manera de hablar sobre las características que deseas agregar o las cosas que te resultan confusas o necesitan aclaración.
-   **GitHub Issues**: Las incidencias son una forma excelente de informar de errores. Además, puedes intentar resolver un problema existente y enviar un PR.

Buscamos colaboradores, sin importar su nivel o experiencia. Para contribuir consulta [CONTIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md)

## Licencia

Reflex es de código abierto y está licenciado bajo la [Apache License 2.0](LICENSE).
