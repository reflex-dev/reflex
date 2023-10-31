```diff
+ 寻找 Pynecone 吗？您来对了.Pynecone 已经更名为 Reflex.+
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

**✨ 使用 Python 创建高效且可自定义的网页应用程序,几秒钟内即可部署.**


[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)

</div>

---
[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md)
---
## ⚙️ 安装

打开一个终端并且运行(要求Python3.8+):

```
pip install reflex
```

## 🥳 创建您的第一个应用程序

安装 Reflex 的同时也会安装 `reflex` 命令行工具.

通过创建一个新项目来测试是否安装成功(请把 my_app_name 替代为您的项目名字):

```
mkdir my_app_name
cd my_app_name
reflex init
```

这段命令会在新文件夹初始化一个应用程序模板.

您可以在开发者模式下运行这个应用程序:
```bash
reflex run
```

您可以看到您的应用程序运行在 http://localhost:3000.

现在您可以在以下位置修改代码 `my_app_name/my_app_name.py`,Reflex 拥有快速刷新(fast refresh),所以您可以在保存代码后马上看到更改.

## 🫧 范例

让我们来看一个例子: 创建一个使用 DALL·E 进行图像生成的图形界面.为了保持范例简单,我们只使用 OpenAI API,但是您可以将其替换成本地端的 ML 模型.

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="DALL·E的前端界面, 展示了图片生成的进程" width="550" />
</div>

&nbsp;

这是这个范例的完整代码,只需要一个 Python 文件就可以完成!

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

## 让我们分解以上步骤.

### **Reflex UI**

让我们从UI开始.

```python
def index():
    return rx.center(
        ...
    )
```

这个 `index` 函数定义了应用程序的前端.

我们用不同的组件比如 `center`, `vstack`, `input`, 和 `button` 来创建前端, 组件之间可以相互嵌入,来创建复杂的布局.
并且您可以使用关键字参数来使用 CSS 的全部功能.

Reflex 拥有 [60+ 个内置组件](https://reflex.dev/docs/library) 来帮助您开始创建应用程序. 我们正在积极添加组件, 但是您也可以 [创建自己的组件](https://reflex.dev/docs/wrapping-react/overview/).

### **State**

Reflex 用 State 来渲染您的 UI.

```python
class State(rx.State):
    """The app state."""
    prompt = ""
    image_url = ""
    processing = False
    complete = False
```


State定义了所有可能会发生变化的变量(称为 vars)以及能够改变这些变量的函数.

在这个范例中,State由 prompt 和 image_url 组成.此外,State还包含有两个布尔值 processing 和 complete,用于指示何时显示循环进度指示器和图像.

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

在 State 中,我们定义了称为事件处理器(event handlers)的函数,用于改变状态变量(state vars).在Reflex中,事件处理器是我们可以修改状态的方式.它们可以作为对用户操作的响应而被调用,例如点击一个按钮或在文本框中输入.这些操作被称为事件.

我们的DALL·E应用有一个事件处理器,名为 get_image,它用于从OpenAI API获取图像.在事件处理器中使用 yield 将导致UI进行更新.否则,UI将在事件处理器结束时进行更新.

### **Routing**

最后,定义我们的应用程序.

```python
app = rx.App()
```

我们添加从应用程序根目录到 index 组件的路由.我们还添加了一个在页面预览或浏览器标签中显示的标题.

```python
app.add_page(index, title="DALL-E")
app.compile()
```

您可以通过增加更多页面来创建一个多页面的应用.

## 📑 资源

<div align="center">

📑 [文档](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [日志](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [组件库](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [展览](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [部署](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>



## ✅ Reflex 的状态

Reflex 于 2022 年 12 月以Pynecone的名称推出.

在2023年7月, 我们处于 **Public Beta** 阶段.

-   :white_check_mark: **Public Alpha**: 任何人都可以安装与使用 Reflex,或许包含问题, 但我们正在积极的解决他们.
-   :large_orange_diamond: **Public Beta**: 对于非软件产品来说足够稳定.
-   **Public Hosting Beta**: _Optionally_, 部属跟托管您的 Reflex!
-   **Public**: 这版本的 Reflex 是可用于软件产品的.

Reflex 每周都有新功能和发布新版本! 确保您按下 :star: 和 :eyes: watch 这个 repository 来确保知道最新信息.

## 贡献

我们欢迎任何大小的贡献,以下是几个好的方法来加入 Reflex 社群.

-   **加入我们的 Discord**: 我们的 [Discord](https://discord.gg/T5WSbC2YtQ) 是帮助您加入 Reflex 项目和讨论或贡献最棒的地方.
-   **GitHub Discussions**: 一个来讨论您想要添加的功能或是需要澄清的事情的好地方.
-   **GitHub Issues**: 报告错误的绝佳地方,另外您可以试着解决一些 issue 和送出 PR.

我们正在积极寻找贡献者,无关您的技能或经验水平.

## 授权

Reflex 是一个开源项目,使用 [Apache License 2.0](LICENSE) 授权.
