<div align="center">
<img src="/docs/images/reflex.svg" alt="Reflex Logo" width="300px">
<hr>

### **✨ Web apps customizáveis, performáticos, em Python puro. Faça deploy em segundos. ✨**

[![Versão PyPI](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versões](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentação](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![PyPI Downloads](https://static.pepy.tech/badge/reflex)](https://pepy.tech/projects/reflex)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)

</div>

---

[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [Español](https://github.com/reflex-dev/reflex/blob/main/docs/es/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md) | [Tiếng Việt](https://github.com/reflex-dev/reflex/blob/main/docs/vi/README.md)

---

# Reflex

Reflex é uma biblioteca para construir aplicações web full-stack em Python puro.

Principais características:

- **Python Puro** - Escreva o frontend e o backend da sua aplicação inteiramente em Python, sem necessidade de aprender Javascript.
- **Flexibilidade Total** - O Reflex é fácil de começar a usar, mas também pode escalar para aplicações complexas.
- **Deploy Instantâneo** - Após a construção, faça o deploy da sua aplicação com um [único comando](https://reflex.dev/docs/hosting/deploy-quick-start/) ou hospede-a em seu próprio servidor.

Veja nossa [página de arquitetura](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture) para aprender como o Reflex funciona internamente.

## ⚙️ Instalação

Abra um terminal e execute (Requer Python 3.10+):

```bash
pip install reflex
```

## 🥳 Crie o seu primeiro app

Instalar `reflex` também instala a ferramenta de linha de comando `reflex`.

Crie um novo projeto para verificar se a instalação foi bem sucedida. (Mude `nome_do_meu_app` com o nome do seu projeto):

```bash
mkdir nome_do_meu_app
cd nome_do_meu_app
reflex init
```

Este comando inicializa um app base no seu novo diretório.

Você pode executar este app em modo desenvolvimento:

```bash
reflex run
```

Você deve conseguir verificar seu app sendo executado em http://localhost:3000.

Agora, você pode modificar o código fonte em `nome_do_meu_app/nome_do_meu_app.py`. O Reflex apresenta recarregamento rápido para que você possa ver suas mudanças instantaneamente quando você salva o seu código.

## 🫧 Exemplo de App

Veja o seguinte exemplo: criar uma interface de criação de imagens por meio do [DALL·E](https://platform.openai.com/docs/guides/images/image-generation?context=node). Para fins de simplicidade, vamos apenas chamar a [API da OpenAI](https://platform.openai.com/docs/api-reference/authentication), mas você pode substituir esta solução por um modelo de ML executado localmente.

&nbsp;

<div align="center">
<img src="/docs/images/dalle.gif" alt="Um encapsulador frontend para o DALL-E, mostrado no processo de criação de uma imagem." width="550" />
</div>

&nbsp;

Aqui está o código completo para criar este projeto. Isso tudo foi feito apenas em um arquivo Python!

```python
import reflex as rx
import openai

openai_client = openai.OpenAI()


class State(rx.State):
    """Estado da aplicação."""

    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """Obtenção da imagem a partir do prompt."""
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

# Adição do estado e da página no app.
app = rx.App()
app.add_page(index, title="Reflex:DALL-E")
```

## Vamos por partes.

<div align="center">
<img src="/docs/images/dalle_colored_code_example.png" alt="Explicando as diferenças entre as partes de backend e frontend do app DALL-E." width="900" />
</div>

### **Reflex UI**

Vamos começar com a UI (Interface de Usuário)

```python
def index():
    return rx.center(
        ...
    )
```

Esta função `index` define o frontend do app.

Usamos diferentes componentes, como `center`, `vstack`, `input` e `button`, para construir o frontend. Componentes podem ser aninhados um no do outro
para criar layouts mais complexos. E você pode usar argumentos de chave-valor para estilizá-los com todo o poder do CSS.

O Reflex vem com [60+ componentes nativos](https://reflex.dev/docs/library) para te ajudar a começar. Estamos adicionando ativamente mais componentes, e é fácil [criar seus próprios componentes](https://reflex.dev/docs/wrapping-react/overview/).

### **Estado**

O Reflex representa a sua UI como uma função do seu estado.

```python
class State(rx.State):
    """Estado da aplicação."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

```

O estado define todas as variáveis (chamadas de vars) em um app que podem mudar e as funções que as alteram.

Aqui, o estado é composto por um `prompt` e uma `image_url`. Há também os booleanos `processing` e `complete` para indicar quando desabilitar o botão (durante a geração da imagem) e quando mostrar a imagem resultante.

### **Handlers de Eventos**

```python
def get_image(self):
    """Obtenção da imagem a partir do prompt."""
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

Dentro do estado, são definidas funções chamadas de Handlers de Eventos, que podem mudar as variáveis do estado. Handlers de Eventos são a forma com a qual podemos modificar o estado dentro do Reflex. Eles podem ser chamados como resposta a uma ação do usuário, como o clique de um botão ou a escrita em uma caixa de texto. Estas ações são chamadas de eventos.

Nosso app DALL-E possui um Handler de Evento chamado `get_image`, que obtêm a imagem da API da OpenAI. Usar `yield` no meio de um Handler de Evento causa a atualização da UI do seu app. Caso contrário, a UI seria atualizada no fim da execução de um Handler de Evento.

### **Rotas**

Finalmente, definimos nosso app.

```python
app = rx.App()
```

Adicionamos uma página na raíz do app, apontando para o componente index. Também adicionamos um título que irá aparecer na visualização da página/aba do navegador.

```python
app.add_page(index, title="DALL-E")
```

Você pode criar um app com múltiplas páginas adicionando mais páginas.

## 📑 Recursos

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; | &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; | &nbsp; 📱 [Biblioteca de Componentes](https://reflex.dev/docs/library) &nbsp; | &nbsp; 🖼️ [Templates](https://reflex.dev/templates/) &nbsp; | &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy-quick-start) &nbsp;

</div>

## ✅ Status

O Reflex foi lançado em Dezembro de 2022 com o nome Pynecone.

A partir de 2025, o [Reflex Cloud](https://cloud.reflex.dev) foi lançado para fornecer a melhor experiência de hospedagem para apps Reflex. Continuaremos a desenvolvê-lo e implementar mais recursos.

O Reflex tem novas versões e recursos chegando toda semana! Certifique-se de marcar com :star: estrela e :eyes: observar este repositório para se manter atualizado.

## Contribuições

Nós somos abertos a contribuições de qualquer tamanho! Abaixo, seguem algumas boas formas de começar a contribuir para a comunidade do Reflex.

- **Entre no nosso Discord**: Nosso [Discord](https://discord.gg/T5WSbC2YtQ) é o melhor lugar para conseguir ajuda no seu projeto Reflex e para discutir como você pode contribuir.
- **Discussões no GitHub**: Uma boa forma de conversar sobre funcionalidades que você gostaria de ver ou coisas que ainda estão confusas/exigem ajuda.
- **Issues no GitHub**: [Issues](https://github.com/reflex-dev/reflex/issues) são uma excelente forma de reportar bugs. Além disso, você pode tentar resolver alguma issue existente e enviar um PR.

Estamos ativamente buscando novos contribuidores, não importa o seu nível de habilidade ou experiência. Para contribuir, confira [CONTRIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md).

## Todo Agradecimento aos Nossos Contribuidores:

<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>

## Licença

O Reflex é de código aberto e licenciado sob a [Apache License 2.0](/LICENSE).
