<div align="center">

<img src="../../images/cones.png">
<hr>

**✨ 使用 Python 建立高效且可自定义的网页应用程序，并在一秒内部署。**

📑 [Docs](https://pynecone.io/docs/getting-started/introduction) &nbsp; 📱 [Component Library](https://pynecone.io/docs/library) &nbsp; 🖼️ [Gallery](https://pynecone.io/docs/gallery) &nbsp; 🛸 [Deployment](https://pynecone.io/docs/hosting/deploy)

[![PyPI version](https://badge.fury.io/py/pynecone.svg)](https://badge.fury.io/py/pynecone)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/build.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/pynecone-io.svg)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)

</div>

### 不同语言的 README

---

[English](../../../README.md) | [繁體中文](../zh_tw/README.md) | [简体中文](README.md)

---

## 📦 1. 安装

Pynecone 需要以下最低要求:

-   Python 3.7+
-   [Node.js 16.8.0+](https://nodejs.org/en/) (不用担心，你不需要写任何 JavaScript!)

```
pip install pynecone
```

## 🥳 2. 建立你的第一个应用程序

安装 Pynecone 的同时也会安装 `pc` 命令行工具. 通过创建一个新项目来测试是否安装成功。

把 my_app_name 替代为你的项目名字:

```
mkdir my_app_name
cd my_app_name
pc init
```

当你第一次运行这个命令，将会自动下载与安装 [bun](https://bun.sh/)。

这个命令会初始化一个应用程序模板在一个新的文件夹。

## 🏃 3. 运行

你可以在开发者模式运行这个应用程序:

```
pc run
```

你可以看到你的应用程序运行在 http://localhost:3000。

现在在以下位置修改原始码 `my_app_name/my_app_name.py`，Pynecone 拥有快速重整所以你可以在保存程序码后马上看到更改。

## 🫧 示例

让我们来看一个例子: 建立一个使用 DALL·E 的图形用户界面，为了保持示例简单，我们只使用 OpenAI API，但是你可以将其替换成本地端的 ML 模型。

&nbsp;

<div align="center">
<img src="../images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

这是上述示例的完整程序码，只需要一个 Python 文件就可以完成!

```python
import pynecone as pc
import openai

openai.api_key = "YOUR_API_KEY"

class State(pc.State):
    """应用程序状态"""
    prompt = ""
    image_url = ""
    image_processing = False
    image_made = False

    def process_image(self):
        """设置图片处理旗标为 True 并设置还未产生图片"""
        self.image_processing = True
        self.image_made = False

    def get_image(self):
        """运用 prompt 取得的参数产生图片"""
        response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
        self.image_url = response["data"][0]["url"]
        self.image_processing = False
        self.image_made = True

def index():
    return pc.center(
        pc.vstack(
            pc.heading("DALL·E", font_size="1.5em"),
            pc.input(placeholder="Enter a prompt..", on_blur=State.set_prompt),
            pc.button(
                "产生图片",
                on_click=[State.process_image, State.get_image],
                width="100%",
            ),
            pc.divider(),
            pc.cond(
                State.image_processing,
                pc.circular_progress(is_indeterminate=True),
                pc.cond(
                     State.image_made,
                     pc.image(
                         src=State.image_url,
                         height="25em",
                         width="25em",
                    )
                )
            ),
            bg="white",
            padding="2em",
            shadow="lg",
            border_radius="lg",
        ),
        width="100%",
        height="100vh",
        bg="radial-gradient(circle at 22% 11%,rgba(62, 180, 137,.20),hsla(0,0%,100%,0) 19%)",
    )
```

# 把状态跟页面添加到应用程序。
app = pc.App(state=State)
app.add_page(index, title="Pynecone:DALL·E")
app.compile()

### **事件处理程序**

```python
    def process_image(self):
        """设置图片处理旗帜为 True 并设置还未产生图片"""
        self.image_processing = True
        self.image_made = False

    def get_image(self):
        """运用 prompt 取得的参数产生图片"""
        response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
        self.image_url = response["data"][0]["url"]
        self.image_processing = False
        self.image_made = True
```

在 State 中我们定义了事件处理程序来更改状态变量，事件处理程序是我们在 Pynecone 中修改状态的方法，可以使用它们来回应用户操作，像是点击按钮或在文字框输入这些动作都是一种事件。

我们的 DALL·E. 应用程序有两个事件处理程序 `process_image` 表示正在生成图片和 `get_image` 呼叫 OpenAI API。

### **路由**

最后定义我们的应用程序并发送状态给它。

```python
app = pc.App(state=State)
```

添加从应用程序根目录到 index 元件的路由。 我们也添加了一个标题将会显示在 预览/浏览 分页。

```python
app.add_page(index, title="Pynecone:DALL-E")
app.compile()
```

你可以藉由通过添加路由来增加更多页面。

## Pynecone 状态

Pynecone 于 2022 年 12 月推出。

截至 2023 年 3 月，我们处于 **Public Beta** 阶段。

-   :white_check_mark: **Public Alpha**: 任何人都可以安装与使用 Pynecone，或许包含问题， 但我们正在积极的解决他们。
-   :large_orange_diamond: **Public Beta**: 对于非软件产品来说足够稳定。
-   **Public Hosting Beta**: _Optionally_, 部署跟托管你的 Pynecone!
-   **Public**: 这版本的 Pynecone 是可用于软件产品的。

Pynecone 每周都有新功能和释出新版本! 确保你按下 :star: 和 :eyes: watch 这个 repository 来确保知道最新资讯。

## 贡献

我们欢迎任何大小的贡献，以下是几个好的方法来加入 Pynecone 社群。

-   **加入我们的 Discord**: 我们的 [Discord](https://discord.gg/T5WSbC2YtQ) 是帮助你加入 Pynecone 项目和讨论或贡献最棒的地方。
-   **GitHub Discussions**: 一个来讨论你想要添加的功能或是需要澄清的事情的好地方。
-   **GitHub Issues**: 报告错误的绝佳地方，另外你可以试着解决一些 issue 和送出 PR。

我们正在积极寻找贡献者，无关你的技能或经验水平。

## 授权

Pynecone 是一个开源项目且使用 [Apache License 2.0](LICENSE) 授权。
