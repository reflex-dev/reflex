```diff
+ 正在寻找 Pynecone？你在正确的 repo 中。Pynecone 已更名为 Reflex。 +
```

<div align="center">
<img src="../../images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="../../images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

**✨ 使用 Python 构建高效且可定制的网页应用程序，几秒钟内即可部署。✨**  

[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---
[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md)
---
## ⚙️ 安装

打开一个终端并运行（需要 Python 3.7+）：

```bash
pip install reflex
```

## 🥳 创建你的第一个应用程序

安装 Reflex 同时也会安装 `reflex` 命令行工具。

通过创建一个新项目来测试是否安装成功（将 my_app_name 作为新项目名称）：

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

此命令将在您的新文件夹中初始化一个应用程序模板。

您可以在开发者模式下运行此应用程序：

```bash
reflex run
```

您可以看到您的应用程序运行在 http://localhost:3000。

现在您可以在以下位置修改源代码 `my_app_name/my_app_name.py`，Reflex 具有快速刷新功能，保存代码后即可立即查看更改。

## 🫧 示例应用程序

让我们来看一个例子：创建一个使用 DALL·E 的图形用户界面。为了保持示例简单，我们只调用 OpenAI API，而这部分可以替换为执行本地端的 ML 模型。

&nbsp;

<div align="center">
<img src="../../images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

下方为该应用之完整代码，这一切都只需要一个 Python 文件就能实现！

```python
import reflex as rx
import openai

openai.api_key = "YOUR_API_KEY"

class State(rx.State):
    """应用程序状态"""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """通过提示词获取图片"""
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

# 将状态和页面添加到应用程序。
app = rx.App()
app.add_page(index, title="reflex:DALL·E")
app.compile()
```

## 让我们来拆解一下。
### **Reflex 用户界面**

让我们从使用界面开始。

```python
def index():
    return rx.center(
        ...
    )
```

这个 `index` 函数定义了应用程序的前端。

我们使用不同的组件，例如 `center`、`vstack`、`input` 和 `button` 来构建前端界面，这些组件可以相互嵌套以创建复杂的布局。您还可以使用关键字参数 *keyword args* 来应用完整的 CSS 样式设计这些组件的外观。

Reflex 拥有 [60+ 内建元件](https://reflex.dev/docs/library)，可帮助您开始构建应用程序。我们正在积极地添加元件，您也可以简单地[创建自己的元件](https://reflex.dev/docs/advanced-guide/wrapping-react)。

### **应用程序状态**

Reflex 使用应用程序状态中的函数来渲染您的用户界面。

```python
class State(rx.State):
    """应用程序状态"""
    prompt = ""
    image_url = ""
    image_processing = False
    image_made = False
```

应用程序状态定义了应用程序中所有可更改的变量，以及变更它们的函数（称为 vars）。

这里的状态由 `prompt` 和 `image_url` 组成，还有布尔变量 `processing` 和 `complete` 用于指示何时显示进度条和图片。

### **事件处理程序**

```python
def get_image(self):
    """通过提示词获取图片"""
    if self.prompt == "":
        return rx.window_alert("Prompt Empty")

    self.processing, self.complete = True, False
    yield
    response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
    self.image_url = response["data"][0]["url"]
    self.processing, self.complete = False, True
```

在应用程序状态中，我们定义了称为事件处理程序的函数来改变其 vars。事件处理程序是我们用来改变 Reflex 应用程序状态的方法。

当用户动作被响应时，对应的事件处理程序就会被调用。点击按钮或文本框输入都是用户动作，它们被称为事件。

我们的 DALL·E 应用程序有一个事件处理程序 `get_image`，它通过 Open AI API 获取图像。在事件处理程序中使用 `yield` 将使用户界面中途更新，若不使用的话，用户界面只能在事件处理程序结束时才更新。
### **路由**

最后，我们定义了我们的应用程序 app。

```python
app = rx.App()
```

添加从应用程序根目录（root of the app）到 index 元件的路由。我们还添加了一个标题，它将显示在预览/浏览 页签上。

```python
app.add_page(index, title="DALL-E")
app.compile()
```

您可以通过将更多页面添加到路由中来创建多页面应用程序(multi-page app)

## 📑 资源

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Component Library](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Gallery](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>



## ✅ Reflex 状态

Reflex 在 2022 年 12 月推出，当时称为 Pynecone。

截至 2023 年 7 月，我们正处于 **Public Beta** 阶段。

-   :white_check_mark: **Public Alpha**：任何人都可以安装和使用Reflex，可能会包含问题，但我们正在积极解决它们。
-   :large_orange_diamond: **Public Beta** : 对于非商业用途的情况而言，已经相当稳定。
-   **Public Hosting Beta**：_Optionally_, 用于部署和托管您的Reflex！
-   **Public**：这个版本的Reflex适用于软件产品。

Reflex 每周都会推出新功能和版本！请确保您点赞 :star: 和关注 :eyes: 这个存储库 repo 以获取最新信息。
## 贡献

我们欢迎任何规模的贡献，以下是加入 Reflex 社区的几种好方法：

-   **加入我们的 Discord 群**: 我们的 [Discord](https://discord.gg/T5WSbC2YtQ) 是帮助您加入Reflex项目、讨论或贡献的最佳地方。
-   **GitHub Discussions**: 一个地方来讨论您想要添加的功能或需要澄清的事情。
-   **GitHub Issues**: 报告错误的绝佳地方，此外您可以尝试解决一些 issue 并提交 PR（Pull Request）。

我们积极寻找贡献者，与您的技能水平或经验无关。

## 授权

Reflex 是一个开源项目，使用 [Apache License 2.0](LICENSE) 授权。