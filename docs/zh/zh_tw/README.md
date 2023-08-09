```diff
+ 正在尋找 Pynecone？ 你在正確的 repo 中。 Pynecone 已更名為 Reflex。 +
```

<div align="center">
<img src="../../images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="../../images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

**✨ 使用 Python 建立高效且可自訂的網頁應用程式，幾秒鐘內即可部署。✨**  

[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/integration.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentaiton](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)
</div>

---
[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md)
---
## ⚙️ 安裝

開啟一個終端機並且執行 (需要 Python 3.7+):

```bash
pip install reflex
```

## 🥳 建立你的第一個應用程式

安裝 Reflex 的同時也會安裝 `reflex` 命令行工具。

通過創建一個新專案來測試是否安裝成功。(把 my_app_name 作為新專案名稱):

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

此命令會初始化一個應用程式模板在你的新資料夾中。

你可以在開發者模式運行這個應用程式:

```bash
reflex run
```

你可以看到你的應用程式運行在 http://localhost:3000。

現在在以下位置修改原始碼 `my_app_name/my_app_name.py`，Reflex 擁有快速刷新功能，存儲程式碼後便可立即看到改變。

## 🫧 範例應用程式

讓我們來看一個例子: 建立一個使用 DALL·E 的圖形使用者介面，為了保持範例簡單，我們只呼叫 OpenAI API，而這部份可以置換掉，改為執行成本地端的 ML 模型。

&nbsp;

<div align="center">
<img src="../../images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

下方為該應用之完整程式碼，這一切都只需要一個 Python 檔案就能作到!

```python
import reflex as rx
import openai

openai.api_key = "YOUR_API_KEY"

class State(rx.State):
    """應用程式狀態"""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """透過提示詞取得圖片"""
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

# 把狀態跟頁面添加到應用程式。
app = rx.App()
app.add_page(index, title="reflex:DALL·E")
app.compile()
```

## 讓我們來拆解一下。
### **Reflex 使用者介面**

讓我們從使用介面開始。

```python
def index():
    return rx.center(
        ...
    )
```

這個 `index` 函式定義了應用程式的前端.

我們用不同的元件像是 `center`, `vstack`, `input`, 和 `button` 來建立前端，元件之間可互相套入以建立出複雜的版面配置。並且您可使用關鍵字引數 *keyword args* 運行 CSS 全部功能來設計這些元件們的樣式。

Reflex 擁有 [60+ 內建元件](https://reflex.dev/docs/library) 來幫助你開始建立應用程式。我們正積極添加元件，你也可以簡單地 [創建自己所屬的元件](https://reflex.dev/docs/advanced-guide/wrapping-react)。

### **應用程式狀態**

Reflex 使用應用程式狀態中的函式來渲染你的 UI。

```python
class State(rx.State):
    """應用程式狀態"""
    prompt = ""
    image_url = ""
    image_processing = False
    image_made = False
```

應用程式狀態定義了應用程式中所有可以更改的變數及變更他們的函式 (稱為 vars)。

這裡的狀態由 `prompt` 和 `image_url`組成， 以及布林變數 `processing` 和 `complete` 來指示何時顯示進度條及圖片。

### **事件處理程序**

```python
def get_image(self):
    """透過提示詞取得圖片"""
    if self.prompt == "":
        return rx.window_alert("Prompt Empty")

    self.processing, self.complete = True, False
    yield
    response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
    self.image_url = response["data"][0]["url"]
    self.processing, self.complete = False, True
```

在應用程式狀態中，我們定義稱之為事件處理程序的函式來改變其 vars. 事件處理程序是我們用來改變 Reflex 應用程式狀態的方法。

當使用者動作被響應時，對應的事件處理程序就會被呼叫。點擊按鈕或是文字框輸入都是使用者動作，它們被稱之為事件。

我們的 DALL·E. 應用程式有一個事件處理程序 `get_image`，它透過 Open AI API 取得圖片。在事件處理程序中使用 `yield` 將讓使用者介面中途更新，若不使用的話，使用介面只能在事件處理程序結束時才更新。

### **路由**

最後，我們定義我們的應用程式 app。

```python
app = rx.App()
```

添加從應用程式根目錄(root of the app) 到 index 元件的路由。 我們也添加了一個標題將會顯示在 預覽/瀏覽 分頁。

```python
app.add_page(index, title="DALL-E")
app.compile()
```

你可以添加更多頁面至路由藉此來建立多頁面應用程式(multi-page app)

## 📑 資源

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; |  &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; |  &nbsp; 📱 [Component Library](https://reflex.dev/docs/library) &nbsp; |  &nbsp; 🖼️ [Gallery](https://reflex.dev/docs/gallery) &nbsp; |  &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy)  &nbsp;   

</div>



## Reflex 狀態

Reflex 於 2022 年 12 月推出，當時名為 Pynecone。

截至 2023 年 7 月，我們處於 **Public Beta** 階段。

-   :white_check_mark: **Public Alpha**: 任何人都可以安裝與使用 Reflex，或許包含問題， 但我們正在積極的解決他們。
-   :large_orange_diamond: **Public Beta**: 對於不涉及商業目的使用情境來說足夠穩定。
-   **Public Hosting Beta**: _Optionally_, 部屬跟託管你的 Reflex!
-   **Public**: 這版本的 Reflex 是可用於軟體產品的。

Reflex 每周都有新功能和釋出新版本! 確保你按下 :star: 和 :eyes: watch 這個 repository 來確保知道最新資訊。

## 貢獻

我們歡迎任何大小的貢獻，以下是幾個好的方法來加入 Reflex 社群。

-   **加入我們的 Discord**: 我們的 [Discord](https://discord.gg/T5WSbC2YtQ) 是幫助你加入 Reflex 專案和討論或貢獻最棒的地方。
-   **GitHub Discussions**: 一個來討論你想要添加的功能或是需要澄清的事情的好地方。
-   **GitHub Issues**: 報告錯誤的絕佳地方，另外你可以試著解決一些 issue 和送出 PR。

我們正在積極尋找貢獻者，無關你的技能水平或經驗。

## 授權

Reflex 是一個開源專案且使用 [Apache License 2.0](LICENSE) 授權。
