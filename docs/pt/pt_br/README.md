```diff
+ Está procurando pelo Pynecone? Este é o repositório certo. Pynecone foi renomeado para Reflex. +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ Web apps customizáveis, performáticos, em Python puro. Faça deploy em segundos. ✨**
[![Versão PyPI](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![testes](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![versões](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentação](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---
[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md)
---
## ⚙️ Instalação

Abra um terminal e execute (Requer Python 3.9+):

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

Agora, você pode modificar o código fonte em `nome_do_meu_app/nome_do_meu_app.py`. O Reflex apresenta recarregamento rápido para que você possa ver suas mudanças instantâneamente quando você salva o seu código.


## 🫧 Exemplo de App

Veja o seguinte exemplo: criar uma interface de criação de imagens por meio do DALL-E. Para fins de simplicidade, vamos apenas chamar a API da OpenAI, mas você pode substituir esta solução por qualquer modelo de aprendizado de máquina que preferir, executando localmente.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="Um encapsulador frontend para o DALL-E, mostrado no processo de criação de uma imagem." width="550" />
</div>

&nbsp;

Aqui está o código completo para criar este projeto. Isso tudo foi feito apenas em um arquivo Python!

```python
import reflex as rx
import openai

openai.api_key = "YOUR_API_KEY"

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

# Adição do estado e da página no app.
app = rx.App()
app.add_page(index, title="reflex:DALL·E")
```

## Vamos por partes.

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

O Reflex vem com [60+ componentes nativos](https://reflex.dev/docs/library) para te ajudar. Estamos adicionando ativamente mais componentes, mas também é fácil [criar seus próprios componentes](https://reflex.dev/docs/wrapping-react/overview/). 

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

O estado define todas as variáveis (chamadas de vars) que podem ser modificadas por funções no seu app.

Aqui, o estado é composto por um `prompt` e uma `image_url`, representando, respectivamente, o texto que descreve a imagem a ser gerada e a url da imagem gerada.

### **Handlers de Eventos**

```python
def get_image(self):
    """Obtenção da imagem a partir do prompt."""
    if self.prompt == "":
        return rx.window_alert("Prompt Empty")

    self.processing, self.complete = True, False
    yield
    response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
    self.image_url = response["data"][0]["url"]
    self.processing, self.complete = False, True
```

Dentro do estado, são definidas funções chamadas de Handlers de Eventos, que podem mudar as variáveis do estado. Handlers de Eventos são a forma com a qual podemos modificar o estado dentro do Reflex. Eles podem ser chamados como resposta a uma ação do usuário, como o clique de um botão ou a escrita em uma caixa de texto. Estas ações geram eventos que são processados pelos Handlers.

Nosso app DALL-E possui um Handler de Evento chamado `get_image`, que obtêm a imagem da API da OpenAI. Usar `yield` no meio de um Handler de Evento causa a atualização da UI do seu app. Caso contrário, a UI seria atualizada no fim da execução de um Handler de Evento.

### **Rotas**

Finalmente, definimos nosso app.

```python
app = rx.App()
```

Adicionamos uma página na raíz do app, apontando para o componente index. Também adicionamos um título ("DALL-E") que irá aparecer na aba no navegador.

```python
app.add_page(index, title="DALL-E")
```

Você pode criar mais páginas e adicioná-las ao seu app.

## 📑 Recursos

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Biblioteca de Componentes](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Galeria](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>





## ✅ Status

O Reflex foi lançado em Dezembro de 2022 com o nome Pynecone.

Em Julho de 2023, estamos no estágio de **Beta Público**.

-   :white_check_mark: **Alpha Público**: Qualquer um pode instalar e usar o Reflex. Podem existir alguns problemas, mas estamos trabalhando ativamente para resolvê-los.
-   :large_orange_diamond: **Beta Público**: Estável o suficiente para utilizar em projetos pessoais, com menor criticidade.
-   **Hospedagem Pública Beta**: _Opcionalmente_, implante e hospede os seus apps no Reflex!
-   **Público**: O Reflex está pronto para produção.

O Reflex agora possui novas versões e funcionalidades sendo lançadas toda semana! Lembre-se de marcar o repositório com uma :star: estrela e :eyes: acompanhe para ficar atualizado sobre o projeto.

## Contribuições

Nós somos abertos a contribuições de qualquer tamanho! Abaixo, seguem algumas boas formas de começar a contribuir para a comunidade do Reflex.

-   **Entre no nosso Discord**: Nosso [Discord](https://discord.gg/T5WSbC2YtQ) é o melhor lugar para conseguir ajuda no seu projeto Reflex e para discutir como você pode contribuir.
-   **Discussões no GitHub**: Uma boa forma de conversar sobre funcionalidades que você gostaria de ver ou coisas que ainda estão confusas/exigem ajuda.
-   **Issues no GitHub**: Excelente forma de reportar bugs. Além disso, você pode tentar resolver alguma issue existente e enviar um Pull Request.

Estamos ativamente buscando novos contribuidores, não importa o seu nível de habilidade ou experiência.

## Licença

O Reflex é um software de código aberto, sob a [Apache License 2.0](LICENSE).
