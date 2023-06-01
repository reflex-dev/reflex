<div align="center">

<img src="../images/cones.png">
<hr>

**✨ 使用 Python 建立高效且可自訂的網頁應用程式，並在一秒內部署。**

📑 [Docs](https://pynecone.io/docs/getting-started/introduction) &nbsp; 📱 [Component Library](https://pynecone.io/docs/library) &nbsp; 🖼️ [Gallery](https://pynecone.io/docs/gallery) &nbsp; 🛸 [Deployment](https://pynecone.io/docs/hosting/deploy)

[![PyPI version](https://badge.fury.io/py/pynecone.svg)](https://badge.fury.io/py/pynecone)
![tests](https://github.com/pynecone-io/pynecone/actions/workflows/build.yml/badge.svg)
![versions](https://img.shields.io/pypi/pyversions/pynecone-io.svg)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)

</div>

## 📦 1. 安裝

Pynecone 需要以下最低要求:

-   Python 3.7+
-   [Node.js 16.8.0+](https://nodejs.org/en/) (不用擔心，你不需要寫任何 JavaScript!)

```
pip install pynecone
```

## 🥳 2. 建立你的第一個應用程式

安裝 Pynecone 的同時也會安裝 `pc` 命令行工具. 通過創建一個新專案來測試是否安裝成功。

把 my_app_name 替代為你的專案名字:

```
mkdir my_app_name
cd my_app_name
pc init
```

當你第一次運行這個命令，將會自動下載與安裝 [bun](https://bun.sh/)。

這個命令會初始化一個應用程式模板在一個新的資料夾。

## 🏃 3. 運行

你可以在開發者模式運行這個應用程式:

```
pc run
```

你可以看到你的應用程式運行在 http://localhost:3000。

現在在以下位置修改原始碼 `my_app_name/my_app_name.py`，Pynecone 擁有快速重整所以你可以在保存程式碼後馬上看到更改。

## 🫧 範例

讓我們來看一個例子: 建立一個使用 DALL·E 的圖形使用者介面，為了保持範例簡單，我們只使用 OpenAI API，但是你可以將其替換成本地端的 ML 模型。

&nbsp;

<div align="center">
<img src="../images/dalle.gif" alt="A frontend wrapper for DALL·E, shown in the process of generating an image." width="550" />
</div>

&nbsp;

這是上述範例的完整程式碼，只需要一個 Python 檔案就可以完成!

```python
import pynecone as pc
import openai

openai.api_key = "YOUR_API_KEY"

class State(pc.State):
    """應用程式狀態"""
    prompt = ""
    image_url = ""
    image_processing = False
    image_made = False

    def process_image(self):
        """設置圖片處理旗標為 True 並設定還未產生圖片"""
        self.image_processing = True
        self.image_made = False

    def get_image(self):
        """運用 prompt 取得的參數產生圖片"""
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
                "產生圖片",
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

# 把狀態跟頁面添加到應用程式。
app = pc.App(state=State)
app.add_page(index, title="Pynecone:DALL·E")
app.compile()
```

### **Pynecone 中的圖形使用者介面**

讓我們分解以上步驟。

```python
def index():
    return pc.center(
        ...
    )
```

這個 `index` function 定義了應用程式的前端.

我們用不同的元件像是 `center`, `vstack`, `input`, 和 `button` 來建立前端， 元件之間可以相互嵌入，來建立複雜的佈局。
並且你可以使用關鍵字參數來使用 CSS 的全部功能。

Pynecone 擁有 [60+ built-in components](https://pynecone.io/docs/library) 來幫助你開始建立應用程式。
我們正在積極添加元件， 但是你也可以簡單的自己創建一些元件 [create your own components](https://pynecone.io/docs/advanced-guide/wrapping-react)。

### **狀態**

Pynecone 用 State 來渲染你的 UI。

```python
class State(pc.State):
    """應用程式狀態"""
    prompt = ""
    image_url = ""
    image_processing = False
    image_made = False
```

State 定義了應用程式中所有可以更改的變數及變更他們的 function (稱為 vars)。

這裡的狀態由 `prompt` 和 `image_url`組成， 以及布林變數 `image_processing` 和 `image_made` 來決定何時顯示進度條及圖片。

### **事件處理程序**

```python
    def process_image(self):
        """設置圖片處理旗標為 True 並設定還未產生圖片"""
        self.image_processing = True
        self.image_made = False

    def get_image(self):
        """運用 prompt 取得的參數產生圖片"""
        response = openai.Image.create(prompt=self.prompt, n=1, size="1024x1024")
        self.image_url = response["data"][0]["url"]
        self.image_processing = False
        self.image_made = True
```

在 State 中我們定義了事件處理程序來更改狀態變數，事件處理程序是我們在 Pynecone 中修改狀態的方法，可以使用它們來回應使用者操做，像是點擊按鈕或在文字框輸入這些動作都是一種事件。

我們的 DALL·E. 應用程式有兩個事件處理程序, `process_image` 表示正在生成圖片和 `get_image`, 呼叫 OpenAI API.

### **路由**

最後定義我們的應用程式並傳送狀態給它。

```python
app = pc.App(state=State)
```

添加從應用程式根目錄到 index 元件的路由。 我們也添加了一個標題將會顯示在 預覽/瀏覽 分頁.

```python
app.add_page(index, title="Pynecone:DALL-E")
app.compile()
```

你可以藉由通過添加路由來增加更多頁面。

## Pynecone 狀態

Pynecone 於 2022 年 12 月推出。

截至 2023 年 3 月，我們處於 **Public Beta** 階段。

-   :white_check_mark: **Public Alpha**: 任何人都可以安裝與使用 Pynecone，或許包含問題， 但我們正在積極的解決他們。
-   :large_orange_diamond: **Public Beta**: 對於非軟體產品來說足夠穩定。
-   **Public Hosting Beta**: _Optionally_, 部屬跟託管你的 Pynecone!
-   **Public**: Pynecone 是可用於軟體產品的.

Pynecone 每周都有新功能和釋出新版本! 確保你按下 :star: 和 :eyes: watch 這個 repository 來確保知道最新資訊.

## 貢獻

我們歡迎任何大小的貢獻，以下是幾個好的方法來加入 Pynecone 社群.

-   **加入我們的 Discord**: 我們的 [Discord](https://discord.gg/T5WSbC2YtQ) 是幫助你加入 Pynecone 專案和討論或貢獻最棒的地方。
-   **GitHub Discussions**: 一個來討論你想要添加的功能或是需要澄清的事情的好地方。
-   **GitHub Issues**: 報告錯誤的絕佳地方，另外你可以試著解決一些 issue 和送出 PR。

我們正在積極尋找貢獻者，無關你的技能或經驗水平。

## 授權

Pynecone 是一個開源專案且使用 [Apache License 2.0](LICENSE) 授權。
