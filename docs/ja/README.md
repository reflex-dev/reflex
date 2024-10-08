```diff
+ PyneconeはReflexに名前を変えました。Pyneconeを探している方は、今、ご覧のページがPyneconeのリポジトリになります。 +
```

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_dark.svg#gh-light-mode-only" alt="Reflex Logo" width="300px">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/reflex_light.svg#gh-dark-mode-only" alt="Reflex Logo" width="300px">

<hr>

### **✨ 即時デプロイが可能な、Pure Python で作ったパフォーマンスと汎用性が高い Web アプリケーション ✨**

[![PyPI version](https://badge.fury.io/py/reflex.svg)](https://badge.fury.io/py/reflex)
![versions](https://img.shields.io/pypi/pyversions/reflex.svg)
[![Documentation](https://img.shields.io/badge/Documentation%20-Introduction%20-%20%23007ec6)](https://reflex.dev/docs/getting-started/introduction)
[![Discord](https://img.shields.io/discord/1029853095527727165?color=%237289da&label=Discord)](https://discord.gg/T5WSbC2YtQ)

</div>

---

[English](https://github.com/reflex-dev/reflex/blob/main/README.md) | [简体中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_cn/README.md) | [繁體中文](https://github.com/reflex-dev/reflex/blob/main/docs/zh/zh_tw/README.md) | [Türkçe](https://github.com/reflex-dev/reflex/blob/main/docs/tr/README.md) | [हिंदी](https://github.com/reflex-dev/reflex/blob/main/docs/in/README.md) | [Português (Brasil)](https://github.com/reflex-dev/reflex/blob/main/docs/pt/pt_br/README.md) | [Italiano](https://github.com/reflex-dev/reflex/blob/main/docs/it/README.md) | [Español](https://github.com/reflex-dev/reflex/blob/main/docs/es/README.md) | [한국어](https://github.com/reflex-dev/reflex/blob/main/docs/kr/README.md) | [日本語](https://github.com/reflex-dev/reflex/blob/main/docs/ja/README.md) | [Deutsch](https://github.com/reflex-dev/reflex/blob/main/docs/de/README.md) | [Persian (پارسی)](https://github.com/reflex-dev/reflex/blob/main/docs/pe/README.md)

---

# Reflex

Reflex は Python のみでフルスタック Web アプリケーションを作成できるライブラリです。

主な特徴:

- **Pure Python** - Web アプリケーションのフロントエンドとバックエンドを Python のみで実装できるため、Javascript を学ぶ必要がありません。
- **高い柔軟性** - Reflex は簡単に始められて、複雑なアプリケーションまで作成できます。
- **即時デプロイ** - ビルド後、すぐにデプロイが可能です。[単純な CLI コマンド](https://reflex.dev/docs/hosting/deploy-quick-start/)を使ったアプリケーションのデプロイや、自身のサーバーへのホストができます。

Reflex がどのように動作しているかを知るには、[アーキテクチャページ](https://reflex.dev/blog/2024-03-21-reflex-architecture/#the-reflex-architecture)をご覧ください。

## ⚙️ インストール

ターミナルを開いて以下のコマンドを実行してください。（Python 3.9 以上が必要です。）:

```bash
pip install reflex
```

## 🥳 最初のアプリケーションを作ろう

`reflex`をインストールすると、`reflex`の CLI ツールが自動でインストールされます。

新しいプロジェクトを作成して、インストールが成功しているかを確認しましょう。（`my_app_name`を自身のプロジェクト名に書き換えて実行ください。）:

```bash
mkdir my_app_name
cd my_app_name
reflex init
```

上記のコマンドを実行すると、新しいフォルダにテンプレートアプリを作成します。

下記のコマンドを実行すると、開発モードでアプリを開始します。

```bash
reflex run
```

http://localhost:3000 にアクセスしてアプリの動作を見ることができます。

`my_app_name/my_app_name.py`のソースコードを編集してみましょう！Reflex は fast refresh なので、ソースを保存した直後に変更が Web ページに反映されます。

## 🫧 実装例

実装例を見てみましょう: [DALL·E](https://platform.openai.com/docs/guides/images/image-generation?context=node)を中心とした画像生成 UI を作成しました。説明を簡単にするためにここでは[OpenAI API](https://platform.openai.com/docs/api-reference/authentication)を呼んでいますが、ローカルで動作している機械学習モデルに置き換えることも可能です。

&nbsp;

<div align="center">
<img src="https://raw.githubusercontent.com/reflex-dev/reflex/main/docs/images/dalle.gif" alt="DALL·Eのフロントエンドラッパーです。画像を生成している過程を表示しています。" width="550" />
</div>

&nbsp;

画像生成 UI のソースコードの全貌を見てみましょう。下記のように、単一の Python ファイルで作れます！

```python
import reflex as rx
import openai

openai_client = openai.OpenAI()


class State(rx.State):
    """アプリのステート"""

    prompt = ""
    image_url = ""
    processing = False
    complete = False

    def get_image(self):
        """プロンプトからイメージを取得する"""
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

# ステートとページをアプリに追加
app = rx.App()
app.add_page(index, title="Reflex:DALL-E")
```

## それぞれの実装を見てみましょう

<div align="center">
<img src="../../docs/images/dalle_colored_code_example.png" alt="DALL-E appのフロントエンドとバックエンドのパーツの違いを説明しています。" width="900" />
</div>

### **Reflex UI**

UI から見てみましょう。

```python
def index():
    return rx.center(
        ...
    )
```

`index`関数において、アプリのフロントエンドを定義しています。

フロントエンドを実装するにあたり、`center`、`vstack`、`input`、`button`など異なるコンポーネントを使用しています。コンポーネントはお互いにネストが可能であり、複雑なレイアウトを作成できます。また、keyword args を使うことで、CSS の機能をすべて使ったスタイルが可能です。

Reflex は[60 を超える内臓コンポーネント](https://reflex.dev/docs/library)があるため、すぐに始められます。私たちは、積極的にコンポーネントを追加していますが、簡単に[自身のコンポーネントを追加](https://reflex.dev/docs/wrapping-react/overview/)することも可能です。

### **ステート**

Reflex はステートの関数を用いて UI を表示します。

```python
class State(rx.State):
    """アプリのステート"""
    prompt = ""
    image_url = ""
    processing = False
    complete = False

```

ステートでは、アプリで変更が可能な全ての変数（vars と呼びます）と、vars の変更が可能な関数を定義します。

この例では、ステートを`prompt`と`image_url`で構成しています。そして、ブール型の`processing`と`complete`を用いて、ボタンを無効にするタイミング（画像生成中）や生成された画像を表示するタイミングを示しています。

### **イベントハンドラ**

```python
def get_image(self):
    """プロンプトからイメージを取得する"""
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

ステートにおいて、ステートの vars を変更できるイベントハンドラ関数を定義しています。イベントハンドラは Reflex において、ステートの vars を変更する方法です。ボタンクリックやテキストボックスの入力など、ユーザのアクションに応じてイベントハンドラが呼ばれます。

DALL·E.アプリには、OpenAI API からイメージを取得する`get_image`関数があります。イベントハンドラの最後で UI の更新がかかるため、関数の途中に`yield`を入れることで先に UI を更新しています。

### **ルーティング**

最後に、アプリを定義します。

```python
app = rx.App()
```

アプリにページを追加し、ドキュメントルートを index コンポーネントにルーティングしています。更に、ページのプレビューやブラウザタブに表示されるタイトルを記載しています。

```python
app.add_page(index, title="DALL-E")
```

ページを追加することで、マルチページアプリケーションを作成できます。

## 📑 リソース

<div align="center">

📑 [Docs](https://reflex.dev/docs/getting-started/introduction) &nbsp; | &nbsp; 🗞️ [Blog](https://reflex.dev/blog) &nbsp; | &nbsp; 📱 [Component Library](https://reflex.dev/docs/library) &nbsp; | &nbsp; 🖼️ [Gallery](https://reflex.dev/docs/gallery) &nbsp; | &nbsp; 🛸 [Deployment](https://reflex.dev/docs/hosting/deploy-quick-start) &nbsp;

</div>

## ✅ ステータス

2022 年 12 月に、Reflex は Pynecone という名前でローンチしました。

2024 年 2 月に、ホスティングサービスをアルファ版でリリースしました！アルファ版では、だれでも Reflex アプリケーションを無料でデプロイできます。今後の予定は[ロードマップ](https://github.com/reflex-dev/reflex/issues/2727)において見れます。

Reflex は毎週、新しいリリースや機能追加を行っています！最新情報を逃さないために、 :star: Star や :eyes: Watch をお願いします。

## コントリビュート

様々なサイズのコントリビュートを歓迎しています！Reflex コミュニティに入るための方法を、いくつかリストアップします。

- **Discord に参加**: [Discord](https://discord.gg/T5WSbC2YtQ)は、Reflex プロジェクトの相談や、コントリビュートについての話し合いをするための、最適な場所です。
- **GitHub Discussions**: GitHub Discussions では、追加したい機能や、複雑で解明が必要な事柄についての議論に適している場所です。
- **GitHub Issues**: [Issues](https://github.com/reflex-dev/reflex/issues)はバグの報告に適している場所です。また、課題を解決した PR のサブミットにチャレンジしていただくことも、可能です。

スキルや経験に関わらず、私たちはコントリビュータを積極的に探しています。コントリビュートするために、[CONTIBUTING.md](https://github.com/reflex-dev/reflex/blob/main/CONTRIBUTING.md)をご覧ください。

## 私たちのコントリビュータに感謝！:

<a href="https://github.com/reflex-dev/reflex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=reflex-dev/reflex" />
</a>

## ライセンス

Reflex はオープンソースであり、[Apache License 2.0](LICENSE)に基づいてライセンス供与されます。
